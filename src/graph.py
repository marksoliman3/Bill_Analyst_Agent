"""
Graph Orchestration

This module wires together all agent subgraphs (Extractor, Summarizer,
Analysts, Judge, and Consolidator) into a single Graph of Graphs workflow.
"""

from langgraph.graph import StateGraph, END
from src.state import AgentState
from src.agents.extractor import build_extractor_subgraph
from src.agents.summarizer import build_summarizer_subgraph
from src.agents.analysts import ANALYST_SUBGRAPHS
from src.agents.judge import build_judge_subgraph
from src.agents.consolidator import build_consolidator_subgraph
from src.agents.revision_router import build_revision_router_node, revision_router_edge
import logging

# Get logger for this module
logger = logging.getLogger(__name__)


def build_full_graph() -> StateGraph:
    """
    Build the full Graph of Graphs workflow.

    Returns:
        StateGraph: The orchestrated workflow graph.
    """
    graph = StateGraph(AgentState)

    # Subgraphs
    extractor = build_extractor_subgraph()
    summarizer = build_summarizer_subgraph()
    judge = build_judge_subgraph()
    consolidator = build_consolidator_subgraph()

    # Add nodes for subgraphs
    graph.add_node("extractor", extractor.compile())
    graph.add_node("summarizer", summarizer.compile())

    for key, subgraph in ANALYST_SUBGRAPHS.items():
        graph.add_node(f"analyst_{key}", subgraph.compile())

    graph.add_node("judge", judge.compile())
    graph.add_node("consolidator", consolidator.compile())
    
    # Add revision router node
    revision_router_fn = build_revision_router_node()
    graph.add_node("revision_router", revision_router_fn)

    # Entry point: Extractor
    graph.set_entry_point("extractor")

    # After extraction, run summarizer
    graph.add_edge("extractor", "summarizer")

    # After summarizer, run analysts sequentially
    analyst_keys = list(ANALYST_SUBGRAPHS.keys())
    if analyst_keys:
        # Connect summarizer to first analyst
        graph.add_edge("summarizer", f"analyst_{analyst_keys[0]}")

        # Connect analysts in sequence - this is the default flow
        # We'll add conditional edges later for the multi-analyst revision flow
        for i in range(len(analyst_keys) - 1):
            graph.add_edge(
                f"analyst_{analyst_keys[i]}", f"analyst_{analyst_keys[i + 1]}"
            )

        # Connect last analyst to judge - this is the default flow
        # We'll add conditional edges later for the multi-analyst revision flow
        graph.add_edge(f"analyst_{analyst_keys[-1]}", "judge")
    else:
        # If no analysts, connect summarizer directly to judge
        graph.add_edge("summarizer", "judge")

    # Conditional routing from judge
    def judge_router(state: AgentState) -> str:
        # Log the state for debugging
        logger.info(f"[GRAPH] Judge router state: {state}")
        
        # Get the next_step from the judgement
        judgement = state.get("judgement")
        logger.info(f"[GRAPH] Judge router judgement: {judgement}")
        
        # Check if judgement is None or empty
        if not judgement or not isinstance(judgement, dict):
            logger.warning(f"[GRAPH] Judgement is not a dictionary or is empty: {judgement}")
            # Default to PASS_TO_FINALIZE
            return "PASS_TO_FINALIZE"
        
        # Check if judgement is in the analyst-specific format
        analyst_keys = ["market_structure", "product_safety", "property_rights", "societal_impact"]
        if (
            any(key in judgement for key in analyst_keys) 
            and "decision" not in judgement
            and "next_step" not in judgement
        ):
            logger.warning(f"[GRAPH] Judgement is in analyst-specific format: {judgement}")
            # Determine if any analysts need revision
            analysts_needing_revision = [
                key for key, value in judgement.items() 
                if key in analyst_keys and value in ["REVISION", "REVISE"]
            ]
            if analysts_needing_revision:
                logger.info(f"[GRAPH] Detected analysts needing revision from analyst-specific format: {analysts_needing_revision}")
                return "MULTI_ANALYST_REVISION"
            else:
                logger.info(f"[GRAPH] No analysts need revision based on analyst-specific format")
                return "PASS_TO_FINALIZE"
        
        # Get next_step from judgement
        next_step = judgement.get("next_step", "PASS_TO_FINALIZE")
        logger.info(f"[GRAPH] Using next_step from judgement: {next_step}")
        
        # Validate next_step is one of the expected values
        if next_step not in ["MULTI_ANALYST_REVISION", "PASS_TO_FINALIZE", "FAIL_BILL"]:
            logger.warning(f"[GRAPH] Unexpected next_step value: {next_step}, defaulting to PASS_TO_FINALIZE")
            return "PASS_TO_FINALIZE"
        
        return next_step

    graph.add_conditional_edges(
        "judge",
        judge_router,
        {
            "MULTI_ANALYST_REVISION": "revision_router",
            "PASS_TO_FINALIZE": "consolidator",
            "FAIL_BILL": END,
        },
    )
    
    # Add conditional edges from revision router using the edge-specific function
    graph.add_conditional_edges(
        "revision_router",
        revision_router_edge,
        {
            "analyst_market_structure": "analyst_market_structure",
            "analyst_product_safety": "analyst_product_safety",
            "analyst_property_rights": "analyst_property_rights",
            "analyst_societal_impact": "analyst_societal_impact",
            "judge": "judge",
        },
    )
    
    # Add conditional edges from analysts to handle multi-analyst revision routing
    for key in ANALYST_SUBGRAPHS.keys():
        # Define a router function for this analyst
        def analyst_router(state: AgentState, analyst_key=key) -> str:
            # If we're in multi-analyst revision mode, route to the revision router
            if state.get("analysts_needing_revision") and state.get("current_revision_analyst") == analyst_key:
                logger.info(f"[GRAPH] Routing from analyst_{analyst_key} to revision_router (multi-analyst revision)")
                return "revision_router"
            
            # Otherwise, follow the normal flow
            if analyst_key == analyst_keys[-1]:
                # Last analyst in the sequence goes to judge
                logger.info(f"[GRAPH] Routing from analyst_{analyst_key} to judge (normal flow)")
                return "judge"
            else:
                # Find the next analyst in the sequence
                next_index = analyst_keys.index(analyst_key) + 1
                next_analyst = analyst_keys[next_index]
                logger.info(f"[GRAPH] Routing from analyst_{analyst_key} to analyst_{next_analyst} (normal flow)")
                return f"analyst_{next_analyst}"
        
        # Create a unique function for each analyst to avoid closure issues
        analyst_router.__name__ = f"analyst_router_{key}"
        
        # Add the conditional edge
        graph.add_conditional_edges(
            f"analyst_{key}",
            analyst_router,
            {
                "revision_router": "revision_router",
                "judge": "judge",
                **{f"analyst_{next_key}": f"analyst_{next_key}" for next_key in analyst_keys},
            },
        )

    # End after consolidation
    graph.add_edge("consolidator", END)

    return graph
