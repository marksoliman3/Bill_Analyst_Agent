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


def revision_router(state: AgentState) -> dict:
    """
    Route to the next analyst in the analysts_needing_revision list,
    or back to the judge when all analysts have been processed.

    Args:
        state (AgentState): The current agent state.

    Returns:
        dict: A dictionary with updates to the state, or the original state if no updates are needed.
    """
    bill_id = state.get("bill_id", "unknown")
    logger.info(f"[REVISION_ROUTER] Processing bill {bill_id}")

    # Create a copy of the state to modify
    updated_state = state.copy() if isinstance(state, dict) else {}

    # Get the list of analysts needing revision
    analysts_needing_revision = state.get("analysts_needing_revision", [])
    logger.info(f"[REVISION_ROUTER] Analysts needing revision: {analysts_needing_revision}")

    # If there are no analysts needing revision, route back to the judge
    if not analysts_needing_revision:
        logger.info(f"[REVISION_ROUTER] No analysts needing revision, routing to judge")
        # Return the state without modifications
        return updated_state

    # Get the current analyst being processed
    current_analyst = state.get("current_revision_analyst")
    logger.info(f"[REVISION_ROUTER] Current analyst: {current_analyst}")

    # If there's no current analyst, route to the first one in the list
    if not current_analyst:
        next_analyst = analysts_needing_revision[0]
        updated_state["current_revision_analyst"] = next_analyst
        logger.info(f"[REVISION_ROUTER] Routing to first analyst: {next_analyst}")
        return updated_state

    # If there is a current analyst, remove it from the list and route to the next one
    try:
        current_index = analysts_needing_revision.index(current_analyst)
        # Remove the current analyst from the list
        analysts_needing_revision_copy = analysts_needing_revision.copy()
        analysts_needing_revision_copy.pop(current_index)
        updated_state["analysts_needing_revision"] = analysts_needing_revision_copy
        logger.info(f"[REVISION_ROUTER] Removed {current_analyst} from the list")

        # If there are more analysts, route to the next one
        if analysts_needing_revision_copy:
            next_analyst = analysts_needing_revision_copy[0]
            updated_state["current_revision_analyst"] = next_analyst
            logger.info(f"[REVISION_ROUTER] Routing to next analyst: {next_analyst}")
            return updated_state
        else:
            # If there are no more analysts, clear the current_revision_analyst and route back to the judge
            updated_state["current_revision_analyst"] = None
            
            # Update the judgement to indicate we're done with revisions
            judgement = state.get("judgement", {})
            if isinstance(judgement, dict):
                updated_judgement = judgement.copy()
                updated_judgement["next_step"] = "PASS_TO_FINALIZE"
                updated_state["judgement"] = updated_judgement
            
            logger.info(f"[REVISION_ROUTER] All analysts processed, routing to judge")
            return updated_state
    except ValueError:
        # If the current analyst is not in the list, this is an error
        logger.error(f"[REVISION_ROUTER] Current analyst {current_analyst} not found in the list")
        # Route back to the judge to handle this error
        updated_state["current_revision_analyst"] = None
        return updated_state


def revision_router_edge(state: AgentState) -> str:
    """
    Conditional edge function for routing to the next node.
    This function is used in add_conditional_edges.

    Args:
        state (AgentState): The current agent state.

    Returns:
        str: The name of the next node to route to.
    """
    bill_id = state.get("bill_id", "unknown")
    
    # Get the list of analysts needing revision
    analysts_needing_revision = state.get("analysts_needing_revision", [])
    
    # If there are no analysts needing revision, route back to the judge
    if not analysts_needing_revision:
        return "judge"

    # Get the current analyst being processed
    current_analyst = state.get("current_revision_analyst")
    
    # If there's no current analyst, route to the first one in the list
    if not current_analyst:
        next_analyst = analysts_needing_revision[0]
        return f"analyst_{next_analyst}"

    # If there is a current analyst, check if there are more analysts
    try:
        current_index = analysts_needing_revision.index(current_analyst)
        # If there are more analysts, route to the next one
        if current_index < len(analysts_needing_revision) - 1:
            next_analyst = analysts_needing_revision[current_index + 1]
            return f"analyst_{next_analyst}"
        else:
            # If there are no more analysts, route back to the judge
            return "judge"
    except ValueError:
        # If the current analyst is not in the list, this is an error
        # Route back to the judge to handle this error
        return "judge"


def build_revision_router_node():
    """
    Build the revision router node.

    Returns:
        function: The revision router function.
    """
    return revision_router
