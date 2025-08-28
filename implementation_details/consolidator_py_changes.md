# Implementation Details for src/agents/consolidator.py

## Current Implementation

The current `consolidator.py` file defines the Consolidator agent subgraph, which aggregates the final outputs of all agents into a single coherent result. The key function is `consolidate_results`, which processes the state and creates a consolidated report:

```python
def consolidate_results(state: AgentState) -> AgentState:
    """
    Aggregate all agent outputs into a final consolidated result.

    Args:
        state (AgentState): The current agent state containing outputs
                            from Extractor, Summarizer, Analysts, and Judge.

    Returns:
        AgentState: Updated state with a consolidated report.
    """
    bill_id = state.get("bill_id", "unknown")
    logger.info(f"[CONSOLIDATOR] Starting consolidation for bill {bill_id}")

    # Get judgement from state
    judgement = state.get("judgement")
    
    # Log the judgement for debugging
    logger.info(f"[CONSOLIDATOR] Judgement from state: {judgement}")
    
    # Ensure judgement is a dictionary with the required fields
    if not judgement or not isinstance(judgement, dict):
        logger.warning(f"[CONSOLIDATOR] Judgement is not a dictionary or is empty: {judgement}")
        # Create a default judgement
        judgement = {
            "decision": "UNKNOWN",
            "feedback": None,
            "next_step": "UNKNOWN"
        }
    
    consolidated = {
        "bill_extracts": state.get("bill_extracts"),
        "summary": state.get("summary"),
        "analyst_results": {},
        "judgement": judgement,
    }

    logger.info(f"[CONSOLIDATOR] Collecting outputs for bill {bill_id}")

    # Use the analyst_results field if it exists
    if "analyst_results" in state and isinstance(state["analyst_results"], dict):
        # Add attempt counts to each analyst result
        for analyst_key, result in state["analyst_results"].items():
            if isinstance(result, dict):
                attempts = state.get("retry_attempts", {}).get(analyst_key, 1)
                result_with_attempts = result.copy()
                result_with_attempts["attempts"] = attempts
                consolidated["analyst_results"][analyst_key] = result_with_attempts
    else:
        # Fallback to the old method for backward compatibility
        for k, v in state.items():
            if k.endswith("_analysis") and isinstance(v, dict):
                analyst_key = k.replace("_analysis", "")
                attempts = state.get("retry_attempts", {}).get(analyst_key, 1)
                v_with_attempts = v.copy()
                v_with_attempts["attempts"] = attempts
                consolidated["analyst_results"][analyst_key] = v_with_attempts

    state["consolidated_report"] = consolidated
    logger.info(f"[CONSOLIDATOR] Created consolidated report for bill {bill_id}")
    
    # Log the consolidated report for debugging
    logger.info(f"[CONSOLIDATOR] Consolidated report: {consolidated}")

    # Count the number of analysts
    num_analysts = len(consolidated["analyst_results"])
    logger.info(
        f"[CONSOLIDATOR] Consolidated {num_analysts} analyst results for bill {bill_id}"
    )

    logger.info(f"[CONSOLIDATOR] Completed consolidation for bill {bill_id}")
    return state
```

## Proposed Changes

We need to update the `consolidate_results` function to include information about the multi-analyst revision process in the consolidated report:

1. Add the `analysts_needing_revision` list to the consolidated report
2. Add the `current_revision_analyst` to the consolidated report
3. Add logging for the multi-analyst revision process

Here's the updated code:

```python
def consolidate_results(state: AgentState) -> AgentState:
    """
    Aggregate all agent outputs into a final consolidated result.

    Args:
        state (AgentState): The current agent state containing outputs
                            from Extractor, Summarizer, Analysts, and Judge.

    Returns:
        AgentState: Updated state with a consolidated report.
    """
    bill_id = state.get("bill_id", "unknown")
    logger.info(f"[CONSOLIDATOR] Starting consolidation for bill {bill_id}")

    # Get judgement from state
    judgement = state.get("judgement")
    
    # Log the judgement for debugging
    logger.info(f"[CONSOLIDATOR] Judgement from state: {judgement}")
    
    # Ensure judgement is a dictionary with the required fields
    if not judgement or not isinstance(judgement, dict):
        logger.warning(f"[CONSOLIDATOR] Judgement is not a dictionary or is empty: {judgement}")
        # Create a default judgement
        judgement = {
            "decision": "UNKNOWN",
            "feedback": None,
            "next_step": "UNKNOWN"
        }
    
    # Get multi-analyst revision information
    analysts_needing_revision = state.get("analysts_needing_revision", [])
    current_revision_analyst = state.get("current_revision_analyst")
    
    # Log multi-analyst revision information
    if analysts_needing_revision:
        logger.info(f"[CONSOLIDATOR] Analysts needing revision: {analysts_needing_revision}")
    if current_revision_analyst:
        logger.info(f"[CONSOLIDATOR] Current revision analyst: {current_revision_analyst}")
    
    consolidated = {
        "bill_extracts": state.get("bill_extracts"),
        "summary": state.get("summary"),
        "analyst_results": {},
        "judgement": judgement,
        "multi_analyst_revision": {
            "analysts_needing_revision": analysts_needing_revision,
            "current_revision_analyst": current_revision_analyst
        }
    }

    logger.info(f"[CONSOLIDATOR] Collecting outputs for bill {bill_id}")

    # Use the analyst_results field if it exists
    if "analyst_results" in state and isinstance(state["analyst_results"], dict):
        # Add attempt counts to each analyst result
        for analyst_key, result in state["analyst_results"].items():
            if isinstance(result, dict):
                attempts = state.get("retry_attempts", {}).get(analyst_key, 1)
                result_with_attempts = result.copy()
                result_with_attempts["attempts"] = attempts
                consolidated["analyst_results"][analyst_key] = result_with_attempts
    else:
        # Fallback to the old method for backward compatibility
        for k, v in state.items():
            if k.endswith("_analysis") and isinstance(v, dict):
                analyst_key = k.replace("_analysis", "")
                attempts = state.get("retry_attempts", {}).get(analyst_key, 1)
                v_with_attempts = v.copy()
                v_with_attempts["attempts"] = attempts
                consolidated["analyst_results"][analyst_key] = v_with_attempts

    state["consolidated_report"] = consolidated
    logger.info(f"[CONSOLIDATOR] Created consolidated report for bill {bill_id}")
    
    # Log the consolidated report for debugging
    logger.info(f"[CONSOLIDATOR] Consolidated report: {consolidated}")

    # Count the number of analysts
    num_analysts = len(consolidated["analyst_results"])
    logger.info(
        f"[CONSOLIDATOR] Consolidated {num_analysts} analyst results for bill {bill_id}"
    )

    logger.info(f"[CONSOLIDATOR] Completed consolidation for bill {bill_id}")
    return state
```

## Implementation Steps

1. Update the `consolidate_results` function to get and log multi-analyst revision information:
   ```python
   # Get multi-analyst revision information
   analysts_needing_revision = state.get("analysts_needing_revision", [])
   current_revision_analyst = state.get("current_revision_analyst")
   
   # Log multi-analyst revision information
   if analysts_needing_revision:
       logger.info(f"[CONSOLIDATOR] Analysts needing revision: {analysts_needing_revision}")
   if current_revision_analyst:
       logger.info(f"[CONSOLIDATOR] Current revision analyst: {current_revision_analyst}")
   ```

2. Add multi-analyst revision information to the consolidated report:
   ```python
   consolidated = {
       "bill_extracts": state.get("bill_extracts"),
       "summary": state.get("summary"),
       "analyst_results": {},
       "judgement": judgement,
       "multi_analyst_revision": {
           "analysts_needing_revision": analysts_needing_revision,
           "current_revision_analyst": current_revision_analyst
       }
   }
   ```

## Considerations

- The updated code maintains backward compatibility by still supporting the single-analyst revision case.
- The multi-analyst revision case is handled by adding a new `multi_analyst_revision` field to the consolidated report.
- We add logging to indicate when a bill has analysts needing revision, which will be helpful for debugging.
- The consolidated report now includes information about the multi-analyst revision process, which can be useful for downstream analysis.
