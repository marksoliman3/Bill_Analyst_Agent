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

    for index, bill in bills_df.iterrows():
        bill_id = bill["Bill_Number"] if "Bill_Number" in bill else f"Bill-{index}"
        logger.info(f"Processing bill {bill_id} ({index+1}/{len(bills_df)})")

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
        
        results.append(final_state)

    # Convert results to DataFrame and save
    logger.info(f"Processed {len(results)} bills, saving results to {OUTPUT_CSV_PATH}")
    results_df = pd.DataFrame(results)
    write_analysis_results(OUTPUT_CSV_PATH, results_df)
    logger.info("Bill analysis application completed successfully")


if __name__ == "__main__":
    main()
