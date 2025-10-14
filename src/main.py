from src.config import INPUT_CSV_PATH, OUTPUT_CSV_PATH, MAX_RETRY_ATTEMPTS
from src.tools.file_io_tools import read_bill_data, write_analysis_results
from src.state import AgentState
import pandas as pd
import logging

# Get logger for this module
logger = logging.getLogger(__name__)


def main():
    logger.info("Starting bill analysis application")

    # Load input data
    logger.info(f"Loading bill data from {INPUT_CSV_PATH}")
    bills_df = read_bill_data(INPUT_CSV_PATH)
    logger.info(f"Loaded {len(bills_df)} bills for processing")

    # Initialize results list
    results = []
    # Keep track of original bill data
    original_bill_data = []

    for index, bill in bills_df.iterrows():
        bill_id = bill["Bill_Number"] if "Bill_Number" in bill else f"Bill-{index}"
        logger.info(f"Processing bill {bill_id} ({index+1}/{len(bills_df)})")

        # Store original bill data
        original_bill_data.append(bill.to_dict())

        # Create a properly structured state dictionary
        state = {
            "bill_id": (
                bill["Bill_Number"] if "Bill_Number" in bill else ""
            ),  # Updated to use standard pandas syntax
            "bill_text": (
                bill["Bill_Text"] if "Bill_Text" in bill else ""
            ),  # Updated to use standard pandas syntax
            "retry_attempts": {},
            "status": "processing",
            "analyst_results": {},  # Initialize analyst_results as an empty dict
            "analysts_needing_revision": [],  # Initialize analysts_needing_revision as an empty list
            "processed_analysts": [],  # Initialize processed_analysts as an empty list to track which analysts have been processed in a revision cycle
        }

        # Run the full orchestrated graph
        from src.graph import build_full_graph

        logger.info(f"Building and compiling graph for bill {bill_id}")
        graph = build_full_graph().compile()

        logger.info(f"Starting graph execution for bill {bill_id}")
        final_state = graph.invoke(state)
        logger.info(f"Completed graph execution for bill {bill_id}")

        # Check if the bill was successfully processed
        # We know the bill reached the consolidator because the graph is set up to always run the consolidator
        # after the judge, so we just need to check the judge's decision
        judgement = final_state.get("judgement", {})
        
        # Log the judgement to help with debugging
        logger.info(f"Judgement for bill {bill_id}: {judgement}")
        
        # Check if judgement is None or empty
        if not judgement or not isinstance(judgement, dict):
            logger.warning(f"Judgement is not a dictionary or is empty: {judgement}")
            # If judgement is None or empty, check the consolidated_report
            consolidated_report = final_state.get("consolidated_report", {})
            if consolidated_report and "judgement" in consolidated_report and isinstance(consolidated_report["judgement"], dict):
                judgement = consolidated_report["judgement"]
                logger.info(f"Using judgement from consolidated_report: {judgement}")
            else:
                # If judgement is still None or empty, create a default judgement
                logger.warning(f"Judgement is still not a dictionary or is empty after checking consolidated_report: {judgement}")
                judgement = {
                    "decision": "REVISE",
                    "next_step": "PASS_TO_FINALIZE",
                    "analysts_needing_revision": [],
                    "feedback_by_analyst": {}
                }
                logger.info(f"Using default judgement: {judgement}")
        
        # Extract next_step from judgement
        next_step = ""
        if isinstance(judgement, dict):
            next_step = judgement.get("next_step", "")
            logger.info(f"Next step from judgement: {next_step}")
        else:
            logger.warning(f"Judgement is not a dictionary: {judgement}")
            next_step = "PASS_TO_FINALIZE"
            logger.info(f"Using default next_step: {next_step}")
        
        # Check retry_attempts to see if any analyst has been asked to revise
        retry_attempts = final_state.get("retry_attempts", {})
        
        # Check for multi-analyst revision
        analysts_needing_revision = final_state.get("analysts_needing_revision", [])
        if analysts_needing_revision:
            logger.info(f"Bill {bill_id} has analysts needing revision: {analysts_needing_revision}")
        
        if next_step == "PASS_TO_FINALIZE":
            status = "completed"
            logger.info(f"Bill {bill_id} processing completed successfully")
        elif next_step == "MULTI_ANALYST_REVISION" or retry_attempts or analysts_needing_revision:
            # If the judge's decision was to pass to multiple analysts, or if there are retry attempts,
            # or if there are analysts needing revision, it means the bill needs revision
            status = "needs_revision"
            
            if next_step == "MULTI_ANALYST_REVISION":
                logger.info(f"Bill {bill_id} needs revision: judge requested changes from multiple analysts")
            
            # Log retry attempts
            if retry_attempts:
                logger.info(f"Retry attempts recorded: {retry_attempts}")
            else:
                logger.info(f"No retry attempts recorded yet")
            
            # Log analysts needing revision
            if analysts_needing_revision:
                logger.info(f"Analysts needing revision: {analysts_needing_revision}")
        elif next_step == "FAIL_BILL":
            # If the judge's decision was to fail the bill
            status = "failed"
            logger.info(f"Bill {bill_id} processing failed: judge decision was FAIL_BILL")
        else:
            # If the judge's decision was not recognized
            status = "failed"
            logger.info(f"Bill {bill_id} processing failed: unrecognized next_step '{next_step}'")
        
        # Update the status in the final state
        final_state["status"] = status
        
        # Create a cleaned version of the state with only the needed fields
        cleaned_state = {
            "bill_id": final_state.get("bill_id", ""),
            "bill_extracts": final_state.get("bill_extracts", ""),
            "summary": final_state.get("summary", ""),
            "analyst_results": final_state.get("analyst_results", {}),
            "retry_attempts": final_state.get("retry_attempts", {}),
            "status": status
        }
        
        # Only append the cleaned state to results
        results.append(cleaned_state)

    # Convert results to DataFrame
    logger.info(f"Processed {len(results)} bills, preparing results for output")
    results_df = pd.DataFrame(results)
    
    # Create DataFrame from original bill data
    original_df = pd.DataFrame(original_bill_data)
    
    # Reset indices to ensure proper alignment
    original_df = original_df.reset_index(drop=True)
    results_df = results_df.reset_index(drop=True)
    
    # Ensure bill_id is present in both DataFrames for merging
    if 'bill_id' not in results_df.columns and 'Bill_Number' in original_df.columns:
        results_df['bill_id'] = results_df.apply(lambda row: row.get('bill_id', ''), axis=1)
    
    # Columns to keep from the results DataFrame
    analysis_columns = ['bill_extracts', 'summary', 'analyst_results', 'retry_attempts', 'status']
    # Only keep columns that exist in the results DataFrame
    existing_analysis_columns = [col for col in analysis_columns if col in results_df.columns]
    
    logger.info(f"Original DataFrame shape: {original_df.shape}")
    logger.info(f"Results DataFrame shape: {results_df.shape}")
    logger.info(f"Original bill IDs: {list(original_df['Bill_Number'] if 'Bill_Number' in original_df.columns else [])}")
    logger.info(f"Result bill IDs: {list(results_df['bill_id'] if 'bill_id' in results_df.columns else [])}")
    
    # Use proper merge operation instead of column-by-column copying
    merged_df = pd.merge(
        original_df, 
        results_df[existing_analysis_columns + ['bill_id']], 
        left_on='Bill_Number',  # Column in original_df to match on
        right_on='bill_id',     # Column in results_df to match on
        how='left'              # Keep all rows from original_df
    )
    
    # Remove duplicate bill_id column if it exists
    if 'bill_id_y' in merged_df.columns:
        merged_df = merged_df.drop(columns=['bill_id_y'])
    if 'bill_id_x' in merged_df.columns and 'bill_id' not in merged_df.columns:
        merged_df = merged_df.rename(columns={'bill_id_x': 'bill_id'})
        
    logger.info(f"Merged DataFrame shape: {merged_df.shape}")
    
    # Helper function to safely extract scores
    def extract_score(analyst_results, key):
        """
        Safely extract a score from analyst results with robust error handling.
        
        Args:
            analyst_results: The dictionary of analyst results
            key: The analyst key to extract score for
            
        Returns:
            int or None: The extracted score, or None if not available
        """
        try:
            # Check if analyst_results is a dictionary and contains the key
            if not isinstance(analyst_results, dict):
                return None
                
            # Get the analyst's result
            analyst_result = analyst_results.get(key, {})
            if not isinstance(analyst_result, dict):
                return None
                
            # Extract and validate the score
            score = analyst_result.get('score')
            
            # Ensure score is an integer
            if score is not None:
                try:
                    return int(score)
                except (ValueError, TypeError):
                    # If score can't be converted to int, log and return None
                    logger.warning(f"Non-integer score found for {key}: {score}")
                    return None
            return None
        except Exception as e:
            # Catch any unexpected errors during extraction
            logger.error(f"Error extracting score for {key}: {e}")
            return None
    
    # Extract individual scores from analyst_results
    analyst_keys = ["product_safety", "property_rights", "market_structure", "specific_use", 
                    "societal_impact", "institutional_processes", "funding_economic"]
    score_columns = [f"{key}_score" for key in analyst_keys]
    
    # Create columns for individual scores
    for i, key in enumerate(analyst_keys):
        column_name = score_columns[i]
        # Use the helper function to safely extract scores
        merged_df[column_name] = merged_df.apply(
            lambda row: extract_score(row.get('analyst_results'), key)
            if 'analyst_results' in row else None, 
            axis=1
        )
        
        # Log the column creation
        logger.info(f"Created {column_name} column with extraction from analyst_results")
    
    logger.info(f"Final DataFrame includes original columns plus: {existing_analysis_columns} and individual score columns")
    write_analysis_results(OUTPUT_CSV_PATH, merged_df)
    logger.info("Bill analysis application completed successfully")


if __name__ == "__main__":
    main()
