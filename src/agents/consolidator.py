"""
Consolidator Subgraph Implementation

This module defines the Consolidator agent subgraph, responsible for
aggregating the final outputs of all agents (Extractor, Summarizer,
Analysts, and Judge) into a single coherent result. The Judge handles
evaluation and routing only, while the Consolidator focuses on packaging
the final state for downstream use.
"""

from langgraph.graph import StateGraph, END
from src.state import AgentState
import logging

logger = logging.getLogger(__name__)


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
    
    # Check if judgement is in the analyst-specific format
    analyst_keys = ["product_safety", "ai_inputs_ip", "market_structure", "specific_use", "societal_risks", "institutional_processes", "ai_advancement"]
    if (
        isinstance(judgement, dict) 
        and any(key in judgement for key in analyst_keys) 
        and "decision" not in judgement
        and "next_step" not in judgement
    ):
        logger.warning(f"[CONSOLIDATOR] Judgement is in analyst-specific format: {judgement}")
        # Convert to simplified schema
        analysts_needing_revision = [
            key for key, value in judgement.items() 
            if key in analyst_keys and value in ["REVISION", "REVISE"]
        ]
        decision = "REVISE" if analysts_needing_revision else "AGREE"
        next_step = "MULTI_ANALYST_REVISION" if analysts_needing_revision else "PASS_TO_FINALIZE"
        judgement = {
            "decision": decision,
            "next_step": next_step,
            "analysts_needing_revision": analysts_needing_revision,
            "feedback_by_analyst": {}
        }
        logger.info(f"[CONSOLIDATOR] Converted judgement to simplified schema: {judgement}")
    
    # Ensure judgement is a dictionary with the required fields
    if not judgement or not isinstance(judgement, dict):
        logger.warning(f"[CONSOLIDATOR] Judgement is not a dictionary or is empty: {judgement}")
        # Create a default judgement
        judgement = {
            "decision": "REVISE",
            "next_step": "PASS_TO_FINALIZE",
            "analysts_needing_revision": [],
            "feedback_by_analyst": {}
        }
    
    # Ensure all required fields are present
    if "decision" not in judgement:
        judgement["decision"] = "REVISE"
    if "next_step" not in judgement:
        judgement["next_step"] = "PASS_TO_FINALIZE"
    if "analysts_needing_revision" not in judgement:
        judgement["analysts_needing_revision"] = []
    if "feedback_by_analyst" not in judgement:
        judgement["feedback_by_analyst"] = {}
    
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

    # Use the analyst_results field
    if "analyst_results" in state and isinstance(state["analyst_results"], dict):
        # Add attempt counts to each analyst result and standardize field names
        for analyst_key, result in state["analyst_results"].items():
            if isinstance(result, dict):
                attempts = state.get("retry_attempts", {}).get(analyst_key, 1)
                result_with_attempts = result.copy()
                result_with_attempts["attempts"] = attempts
                
                # Standardize field names: ensure all analysts use the same field name for score
                if "relevance_score" in result_with_attempts and "score" not in result_with_attempts:
                    result_with_attempts["score"] = result_with_attempts.pop("relevance_score")
                elif "score" in result_with_attempts and "relevance_score" not in result_with_attempts:
                    # Already using the correct field name, no change needed
                    pass
                
                consolidated["analyst_results"][analyst_key] = result_with_attempts
    
    # Log any missing analyst results or scores (no fallback — empty cells are more honest)
    for analyst_key in analyst_keys:
        if analyst_key not in consolidated["analyst_results"]:
            logger.warning(f"[CONSOLIDATOR] Missing result for analyst {analyst_key} — score will be empty in output")
        elif "score" not in consolidated["analyst_results"][analyst_key]:
            logger.warning(f"[CONSOLIDATOR] Missing score for analyst {analyst_key} — score will be empty in output")

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


def build_consolidator_subgraph() -> StateGraph:
    """
    Build the Consolidator subgraph using LangGraph.

    Returns:
        StateGraph: A LangGraph subgraph for consolidation.
    """
    graph = StateGraph(AgentState)
    graph.add_node("consolidate", consolidate_results)
    graph.set_entry_point("consolidate")
    graph.add_edge("consolidate", END)
    return graph