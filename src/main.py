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
        # Prioritize the consolidated results
        consolidated_results = final_state.get("consolidated_report", {}).get("analyst_results", {})
        cleaned_state = {
            "bill_id": final_state.get("bill_id", ""),
            "bill_extracts": final_state.get("bill_extracts", ""),
            "summary": final_state.get("summary", ""),
            "analyst_results": consolidated_results or final_state.get("analyst_results", {}),
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
    
    # Ensure bill_id is present in both DataFrames for merging
    if 'bill_id' not in results_df.columns and 'Bill_Number' in original_df.columns:
        results_df['bill_id'] = original_df['Bill_Number']
    
    # Columns to keep from the results DataFrame
    analysis_columns = ['bill_extracts', 'summary', 'analyst_results', 'retry_attempts', 'status']
    # Only keep columns that exist in the results DataFrame
    existing_analysis_columns = [col for col in analysis_columns if col in results_df.columns]
    
    # Create a new DataFrame with all original columns plus analysis columns
    merged_df = pd.DataFrame()
    
    # Add all original columns
    for col in original_df.columns:
        merged_df[col] = original_df[col]
    
    # Add analysis columns
    for col in existing_analysis_columns:
        if col in results_df.columns:
            merged_df[col] = results_df[col]
    
    # Helper function to safely extract scores (returns None when missing or errored)
    def extract_score(analyst_results, key):
        """
        Safely extract a score from analyst results with robust error handling.
        Ensures the score is one of the valid values: 0, 0.5, or 1.
        Returns None when scores are missing or errored so failures surface as empty cells.

        Args:
            analyst_results: The dictionary of analyst results
            key: The analyst key to extract score for

        Returns:
            float or None: The extracted score (0, 0.5, or 1), or None if missing/errored
        """
        try:
            # Check if analyst_results is a dictionary and contains the key
            if not isinstance(analyst_results, dict):
                logger.warning(f"analyst_results is not a dictionary for {key}")
                return None
                
            # Get the analyst's result
            analyst_result = analyst_results.get(key, {})
            if not isinstance(analyst_result, dict):
                logger.warning(f"Result for {key} is not a dictionary")
                return None
            
            # Check if there was an error in the analyst processing
            if "error" in analyst_result:
                logger.warning(f"Error found in analyst {key}: {analyst_result['error']}")
                return None
                
            # Extract the score
            score = analyst_result.get('score')
            
            # Ensure score is a float and one of the valid values
            if score is not None:
                try:
                    # Convert to float in case it's a string or integer
                    score_float = float(score)
                    
                    # Validate that score is one of the allowed values
                    valid_scores = [0, 0.5, 1]
                    if score_float not in valid_scores:
                        # Find the closest valid score
                        closest = min(valid_scores, key=lambda x: abs(x - score_float))
                        logger.warning(f"Invalid score {score_float} for {key} coerced to nearest valid value: {closest}")
                        return closest
                    return score_float
                except (ValueError, TypeError):
                    # If score can't be converted to float, log and return None
                    logger.warning(f"Non-numeric score found for {key}: {score}")
                    return None
            
            # If score is None or not found, return None
            logger.warning(f"No score found for {key}")
            return None
        except Exception as e:
            # Catch any unexpected errors during extraction and return None
            logger.error(f"Error extracting score for {key}: {e}")
            return None
    
    # Extract individual scores from analyst_results
    analyst_keys = ["product_safety", "property_rights", "market_structure", "specific_use", 
                    "societal_risks", "institutional_processes", "funding_economic"]
    score_columns = [f"{key}_score" for key in analyst_keys]
    
    # Create columns for individual scores
    for i, key in enumerate(analyst_keys):
        column_name = score_columns[i]
        # Use the helper function to safely extract scores
        merged_df[column_name] = merged_df.apply(
            lambda row: extract_score(row.get('analyst_results'), key)
            if 'analyst_results' in row else None, # Return None if analyst_results not in row 
            axis=1
        )
        
        # Log the column creation
        logger.info(f"Created {column_name} column with extraction from analyst_results")
    
    logger.info(f"Final DataFrame includes original columns plus: {existing_analysis_columns} and individual score columns")
    write_analysis_results(OUTPUT_CSV_PATH, merged_df)
    logger.info("Bill analysis application completed successfully")


if __name__ == "__main__":
    main()