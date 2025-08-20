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
        }

        # Run the full orchestrated graph
        from src.graph import build_full_graph

        logger.info(f"Building and compiling graph for bill {bill_id}")
        graph = build_full_graph().compile()

        logger.info(f"Starting graph execution for bill {bill_id}")
        final_state = graph.invoke(state)
        logger.info(f"Completed graph execution for bill {bill_id}")

        # Collect consolidated report if available
        status = "completed" if "consolidated_report" in final_state else "failed"
        state["status"] = status
        logger.info(f"Bill {bill_id} processing {status}")

        results.append(final_state)

    # Convert results to DataFrame and save
    logger.info(f"Processed {len(results)} bills, saving results to {OUTPUT_CSV_PATH}")
    results_df = pd.DataFrame(results)
    write_analysis_results(OUTPUT_CSV_PATH, results_df)
    logger.info("Bill analysis application completed successfully")


if __name__ == "__main__":
    main()
