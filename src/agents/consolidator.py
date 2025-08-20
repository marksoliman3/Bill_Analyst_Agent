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

    consolidated = {
        "bill_extracts": state.get("bill_extracts"),
        "summary": state.get("summary"),
        "analyst_results": {},
        "judgement": state.get("judgement"),
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
