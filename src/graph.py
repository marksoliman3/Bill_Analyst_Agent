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

    # After summarizer, run analysts sequentially
    analyst_keys = list(ANALYST_SUBGRAPHS.keys())
    if analyst_keys:
        # Connect summarizer to first analyst
        graph.add_edge("summarizer", f"analyst_{analyst_keys[0]}")

        # Connect analysts in sequence
        for i in range(len(analyst_keys) - 1):
            graph.add_edge(
                f"analyst_{analyst_keys[i]}", f"analyst_{analyst_keys[i + 1]}"
            )

        # Connect last analyst to judge
        graph.add_edge(f"analyst_{analyst_keys[-1]}", "judge")
    else:
        # If no analysts, connect summarizer directly to judge
        graph.add_edge("summarizer", "judge")

    # Conditional routing from judge
    def judge_router(state: AgentState) -> str:
        next_step = state.get("judgement", {}).get("next_step", "PASS_TO_FINALIZE")
        # If judge output is aggregated per analyst, handle accordingly
        if (
            isinstance(state.get("judgement"), dict)
            and "decision" not in state["judgement"]
        ):
            # pick first routing for simplicity in placeholder
            for analyst, result in state["judgement"].items():
                return result.get("next_step", "PASS_TO_FINALIZE")
        return next_step

    graph.add_conditional_edges(
        "judge",
        judge_router,
        {
            "PASS_TO_ANALYST_market_structure": "analyst_market_structure",
            "PASS_TO_ANALYST_product_safety": "analyst_product_safety",
            "PASS_TO_ANALYST_property_rights": "analyst_property_rights",
            "PASS_TO_ANALYST_societal_impact": "analyst_societal_impact",
            "PASS_TO_FINALIZE": "consolidator",
            "FAIL_BILL": END,
        },
    )

    # End after consolidation
    graph.add_edge("consolidator", END)

    return graph
