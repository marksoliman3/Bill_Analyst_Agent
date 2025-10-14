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

    # Entry point: Extractor
    graph.set_entry_point("extractor")

    # After extraction, run summarizer
    graph.add_edge("extractor", "summarizer")

    # After summarizer, run analysts sequentially using conditional edges
    analyst_keys = list(ANALYST_SUBGRAPHS.keys())
    if analyst_keys:
        # Connect summarizer to first analyst
        graph.add_edge("summarizer", f"analyst_{analyst_keys[0]}")
        
        # We'll use conditional edges for analyst-to-analyst and analyst-to-judge routing
        # to handle both the normal flow and the multi-analyst revision flow
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
        analyst_keys = ["product_safety", "property_rights", "market_structure", "specific_use", "societal_impact", "institutional_processes", "funding_economic"]
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
                # Route directly to the first analyst needing revision
                state["analysts_needing_revision"] = analysts_needing_revision
                return f"analyst_{analysts_needing_revision[0]}"
            else:
                logger.info(f"[GRAPH] No analysts need revision based on analyst-specific format")
                return "PASS_TO_FINALIZE"
        
        # Get next_step from judgement
        next_step = judgement.get("next_step", "PASS_TO_FINALIZE")
        logger.info(f"[GRAPH] Using next_step from judgement: {next_step}")
        
        # If next_step is MULTI_ANALYST_REVISION, route directly to the first analyst needing revision
        if next_step == "MULTI_ANALYST_REVISION":
            analysts_needing_revision = judgement.get("analysts_needing_revision", [])
            if analysts_needing_revision:
                logger.info(f"[GRAPH] Routing directly to first analyst needing revision: {analysts_needing_revision[0]}")
                return f"analyst_{analysts_needing_revision[0]}"
            else:
                logger.warning(f"[GRAPH] MULTI_ANALYST_REVISION specified but no analysts_needing_revision found, defaulting to PASS_TO_FINALIZE")
                return "PASS_TO_FINALIZE"
        
        # Validate next_step is one of the expected values
        if next_step not in ["PASS_TO_FINALIZE", "FAIL_BILL"]:
            logger.warning(f"[GRAPH] Unexpected next_step value: {next_step}, defaulting to PASS_TO_FINALIZE")
            return "PASS_TO_FINALIZE"
        
        return next_step

    # Add conditional edges from judge with direct routing to analysts
    graph.add_conditional_edges(
        "judge",
        judge_router,
        {
            "PASS_TO_FINALIZE": "consolidator",
            "FAIL_BILL": END,
            **{f"analyst_{key}": f"analyst_{key}" for key in analyst_keys},
        },
    )
    
    # Add conditional edges from analysts to handle both normal flow and multi-analyst revision routing
    for key in ANALYST_SUBGRAPHS.keys():
        # Define a router function for this analyst
        def analyst_router(state: AgentState, analyst_key=key) -> str:
            # Get the list of analysts needing revision
            analysts_needing_revision = state.get("analysts_needing_revision", [])
            
            # Track processed analysts to prevent infinite loops
            processed_analysts = state.get("processed_analysts", [])
            
            # If we're in multi-analyst revision mode and this analyst is in the list
            if analysts_needing_revision and analyst_key in analysts_needing_revision:
                # Log that we're processing this analyst as part of a multi-analyst revision
                logger.info(f"[GRAPH] Processing analyst_{analyst_key} as part of multi-analyst revision")
                
                # Add this analyst to the processed list to prevent it from being processed again in this cycle
                if analyst_key not in processed_analysts:
                    processed_analysts.append(analyst_key)
                    state["processed_analysts"] = processed_analysts
                    logger.info(f"[GRAPH] Added {analyst_key} to processed_analysts: {processed_analysts}")
                
                # Remove this analyst from the list
                updated_list = [a for a in analysts_needing_revision if a != analyst_key]
                state["analysts_needing_revision"] = updated_list
                logger.info(f"[GRAPH] Updated analysts_needing_revision: {updated_list}")
                
                # If there are more analysts in the list, route to the next one
                if updated_list:
                    # Find the next analyst that hasn't been processed yet
                    next_analysts = [a for a in updated_list if a not in processed_analysts]
                    if next_analysts:
                        next_analyst = next_analysts[0]
                        logger.info(f"[GRAPH] Routing from analyst_{analyst_key} to next analyst needing revision: {next_analyst}")
                        return f"analyst_{next_analyst}"
                    else:
                        # If all analysts have been processed, route back to judge
                        logger.info(f"[GRAPH] All analysts have been processed, routing from analyst_{analyst_key} to judge")
                        # Reset the processed_analysts list for the next revision cycle
                        state["processed_analysts"] = []
                        return "judge"
                else:
                    # If no more analysts need revision, route back to judge
                    logger.info(f"[GRAPH] All revisions complete, routing from analyst_{analyst_key} to judge")
                    # Reset the processed_analysts list for the next revision cycle
                    state["processed_analysts"] = []
                    return "judge"
            
            # If we're not in multi-analyst revision mode or this analyst is not in the list,
            # follow the normal flow
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
        
        # Create a dictionary of possible destinations for this analyst
        destinations = {"judge": "judge"}
        
        # In normal flow, this analyst can only route to the next analyst in sequence or to judge
        if key != analyst_keys[-1]:
            next_index = analyst_keys.index(key) + 1
            next_analyst = analyst_keys[next_index]
            destinations[f"analyst_{next_analyst}"] = f"analyst_{next_analyst}"
        
        # In multi-analyst revision flow, this analyst can route to any analyst in the analysts_needing_revision list
        # We need to add all possible analysts as destinations
        for next_key in analyst_keys:
            if next_key != key:  # Don't add self as destination
                destinations[f"analyst_{next_key}"] = f"analyst_{next_key}"
        
        # Add the conditional edge with the restricted destinations
        graph.add_conditional_edges(
            f"analyst_{key}",
            analyst_router,
            destinations,
        )

    # End after consolidation
    graph.add_edge("consolidator", END)

    return graph
