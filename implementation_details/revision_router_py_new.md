# Implementation Details for src/agents/revision_router.py (New File)

## Purpose

The `revision_router.py` file will be a new module that handles the transition between analysts during the multi-analyst revision process. It will:

1. Route to the first analyst in the analysts_needing_revision list
2. After each analyst completes, route to the next one in the list
3. When all analysts have been processed, route back to the judge

## Implementation

Here's the complete implementation for the new `revision_router.py` file:

```python
"""
Revision Router Implementation

This module defines the revision router, which handles the transition between
analysts during the multi-analyst revision process. It routes to each analyst
in the analysts_needing_revision list in sequence, and then back to the judge
when all analysts have been processed.
"""

from langgraph.graph import StateGraph, END
from src.state import AgentState
import logging

# Get logger for this module
logger = logging.getLogger(__name__)


def revision_router(state: AgentState) -> str:
    """
    Route to the next analyst in the analysts_needing_revision list,
    or back to the judge when all analysts have been processed.

    Args:
        state (AgentState): The current agent state.

    Returns:
        str: The name of the next node to route to.
    """
    bill_id = state.get("bill_id", "unknown")
    logger.info(f"[REVISION_ROUTER] Processing bill {bill_id}")

    # Get the list of analysts needing revision
    analysts_needing_revision = state.get("analysts_needing_revision", [])
    logger.info(f"[REVISION_ROUTER] Analysts needing revision: {analysts_needing_revision}")

    # If there are no analysts needing revision, route back to the judge
    if not analysts_needing_revision:
        logger.info(f"[REVISION_ROUTER] No analysts needing revision, routing to judge")
        return "judge"

    # Get the current analyst being processed
    current_analyst = state.get("current_revision_analyst")
    logger.info(f"[REVISION_ROUTER] Current analyst: {current_analyst}")

    # If there's no current analyst, route to the first one in the list
    if not current_analyst:
        next_analyst = analysts_needing_revision[0]
        state["current_revision_analyst"] = next_analyst
        logger.info(f"[REVISION_ROUTER] Routing to first analyst: {next_analyst}")
        return f"analyst_{next_analyst}"

    # If there is a current analyst, remove it from the list and route to the next one
    try:
        current_index = analysts_needing_revision.index(current_analyst)
        # Remove the current analyst from the list
        analysts_needing_revision.pop(current_index)
        state["analysts_needing_revision"] = analysts_needing_revision
        logger.info(f"[REVISION_ROUTER] Removed {current_analyst} from the list")

        # If there are more analysts, route to the next one
        if analysts_needing_revision:
            next_analyst = analysts_needing_revision[0]
            state["current_revision_analyst"] = next_analyst
            logger.info(f"[REVISION_ROUTER] Routing to next analyst: {next_analyst}")
            return f"analyst_{next_analyst}"
        else:
            # If there are no more analysts, clear the current_revision_analyst and route back to the judge
            state["current_revision_analyst"] = None
            logger.info(f"[REVISION_ROUTER] All analysts processed, routing to judge")
            return "judge"
    except ValueError:
        # If the current analyst is not in the list, this is an error
        logger.error(f"[REVISION_ROUTER] Current analyst {current_analyst} not found in the list")
        # Route back to the judge to handle this error
        state["current_revision_analyst"] = None
        return "judge"


def build_revision_router_node():
    """
    Build the revision router node.

    Returns:
        function: The revision router function.
    """
    return revision_router
```

## Integration with Graph

To integrate the revision router with the main graph in `graph.py`, we need to:

1. Import the revision router:
   ```python
   from src.agents.revision_router import build_revision_router_node
   ```

2. Add the revision router node to the graph:
   ```python
   # Add revision router node
   revision_router = build_revision_router_node()
   graph.add_node("revision_router", revision_router)
   ```

3. Add a conditional edge from the revision router to all possible analyst nodes and the judge:
   ```python
   # Add conditional edges from revision router
   graph.add_conditional_edges(
       "revision_router",
       lambda state: revision_router(state),
       {
           "analyst_market_structure": "analyst_market_structure",
           "analyst_product_safety": "analyst_product_safety",
           "analyst_property_rights": "analyst_property_rights",
           "analyst_societal_impact": "analyst_societal_impact",
           "judge": "judge",
       },
   )
   ```

4. Add edges from each analyst back to the revision router:
   ```python
   # Add edges from analysts to revision router
   for key in ANALYST_SUBGRAPHS.keys():
       graph.add_edge(f"analyst_{key}", "revision_router")
   ```

5. Update the judge_router function to handle the "MULTI_ANALYST_REVISION" next_step:
   ```python
   # Add "MULTI_ANALYST_REVISION" to the conditional edges
   graph.add_conditional_edges(
       "judge",
       judge_router,
       {
           "PASS_TO_ANALYST_market_structure": "analyst_market_structure",
           "PASS_TO_ANALYST_product_safety": "analyst_product_safety",
           "PASS_TO_ANALYST_property_rights": "analyst_property_rights",
           "PASS_TO_ANALYST_societal_impact": "analyst_societal_impact",
           "MULTI_ANALYST_REVISION": "revision_router",
           "PASS_TO_FINALIZE": "consolidator",
           "FAIL_BILL": END,
       },
   )
   ```

## Considerations

- The revision router is a simple function that routes to the next analyst in the list or back to the judge when all analysts have been processed.
- It maintains the state by updating the `current_revision_analyst` field and removing processed analysts from the `analysts_needing_revision` list.
- It handles error cases, such as when the current analyst is not found in the list.
- The integration with the main graph requires adding the revision router node, adding conditional edges from the revision router to all possible analyst nodes and the judge, and adding edges from each analyst back to the revision router.
- The judge_router function needs to be updated to handle the "MULTI_ANALYST_REVISION" next_step.
