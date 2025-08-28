# Implementation Details for src/main.py

## Current Implementation

The current `main.py` file defines the main application flow, which loads the input data, processes each bill through the graph, and writes the results to the output file. The key function is `main`, which initializes the state for each bill and invokes the graph:

```python
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
```

## Proposed Changes

We need to update the `main` function to initialize the new state fields for multi-analyst revision:

1. Initialize `analysts_needing_revision` as an empty list
2. Initialize `current_revision_analyst` as None
3. Add logging for the multi-analyst revision process

Here's the updated code:

```python
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
    "current_revision_analyst": None,  # Initialize current_revision_analyst as None
}
```

We also need to update the status checking logic to handle the multi-analyst revision case:

```python
# Check if the bill was successfully processed
# We know the bill reached the consolidator because the graph is set up to always run the consolidator
# after the judge, so we just need to check the judge's decision
judgement = final_state.get("judgement", {})

# Log the judgement to help with debugging
logger.info(f"Judgement for bill {bill_id}: {judgement}")

# Log the judgement for debugging
logger.info(f"Judgement from state: {judgement}")

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
            "decision": "UNKNOWN",
            "feedback": None,
            "next_step": "UNKNOWN"
        }
        logger.info(f"Using default judgement: {judgement}")

# Extract next_step from judgement
next_step = ""
if isinstance(judgement, dict):
    next_step = judgement.get("next_step", "")
    logger.info(f"Next step from judgement: {next_step}")
else:
    logger.warning(f"Judgement is not a dictionary: {judgement}")
    next_step = "UNKNOWN"
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
elif next_step == "MULTI_ANALYST_REVISION" or next_step.startswith("PASS_TO_ANALYST") or retry_attempts or analysts_needing_revision:
    # If the judge's decision was to pass to multiple analysts, or to a single analyst, or if there are retry attempts,
    # or if there are analysts needing revision, it means the bill needs revision
    status = "needs_revision"
    
    if next_step == "MULTI_ANALYST_REVISION":
        logger.info(f"Bill {bill_id} needs revision: judge requested changes from multiple analysts")
    elif next_step.startswith("PASS_TO_ANALYST"):
        logger.info(f"Bill {bill_id} needs revision: judge requested changes from a single analyst")
    
    # Log retry attempts
    if retry_attempts:
        logger.info(f"Retry attempts recorded: {retry_attempts}")
    else:
        logger.info(f"No retry attempts recorded yet")
    
    # Log analysts needing revision
    if analysts_needing_revision:
        logger.info(f"Analysts needing revision: {analysts_needing_revision}")
else:
    # If the judge's decision was not to finalize or pass to an analyst, it means the bill failed
    status = "failed"
    logger.info(f"Bill {bill_id} processing failed: judge decision was {next_step}")

# Update the status in the final state
final_state["status"] = status
```

## Implementation Steps

1. Update the state initialization to include the new fields:
   ```python
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
       "current_revision_analyst": None,  # Initialize current_revision_analyst as None
   }
   ```

2. Update the status checking logic to handle the multi-analyst revision case:
   ```python
   # Check for multi-analyst revision
   analysts_needing_revision = final_state.get("analysts_needing_revision", [])
   if analysts_needing_revision:
       logger.info(f"Bill {bill_id} has analysts needing revision: {analysts_needing_revision}")

   if next_step == "PASS_TO_FINALIZE":
       status = "completed"
       logger.info(f"Bill {bill_id} processing completed successfully")
   elif next_step == "MULTI_ANALYST_REVISION" or next_step.startswith("PASS_TO_ANALYST") or retry_attempts or analysts_needing_revision:
       # If the judge's decision was to pass to multiple analysts, or to a single analyst, or if there are retry attempts,
       # or if there are analysts needing revision, it means the bill needs revision
       status = "needs_revision"
       
       if next_step == "MULTI_ANALYST_REVISION":
           logger.info(f"Bill {bill_id} needs revision: judge requested changes from multiple analysts")
       elif next_step.startswith("PASS_TO_ANALYST"):
           logger.info(f"Bill {bill_id} needs revision: judge requested changes from a single analyst")
       
       # Log retry attempts
       if retry_attempts:
           logger.info(f"Retry attempts recorded: {retry_attempts}")
       else:
           logger.info(f"No retry attempts recorded yet")
       
       # Log analysts needing revision
       if analysts_needing_revision:
           logger.info(f"Analysts needing revision: {analysts_needing_revision}")
   else:
       # If the judge's decision was not to finalize or pass to an analyst, it means the bill failed
       status = "failed"
       logger.info(f"Bill {bill_id} processing failed: judge decision was {next_step}")
   ```

## Considerations

- The updated code maintains backward compatibility by still supporting the single-analyst revision case.
- The multi-analyst revision case is handled by checking for the "MULTI_ANALYST_REVISION" next_step and the analysts_needing_revision list.
- We add logging to indicate when a bill has analysts needing revision, which will be helpful for debugging.
- The status checking logic is updated to handle the multi-analyst revision case, setting the status to "needs_revision" if there are analysts needing revision.
