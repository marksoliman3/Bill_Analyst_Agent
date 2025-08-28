# Implementation Details for src/graph.py

## Current Implementation

The current `graph.py` file defines the main graph orchestration, which wires together all agent subgraphs (Extractor, Summarizer, Analysts, Judge, and Consolidator) into a single workflow. The key components are:

1. The `build_full_graph` function, which creates and configures the StateGraph
2. The `judge_router` function, which determines the next node based on the judge's decision
3. The conditional edges from the judge to various nodes based on the next_step

Currently, the graph only supports routing to a single analyst for revision:

```python
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
```

## Proposed Changes

We need to update the `graph.py` file to integrate the revision router and handle the multi-analyst revision process:

1. Import the revision router
2. Add the revision router node to the graph
3. Update the conditional edges from the judge to include the "MULTI_ANALYST_REVISION" next_step
4. Add conditional edges from the revision router to all possible analyst nodes and the judge
5. Add edges from each analyst back to the revision router

Here's the updated code:

```python
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
from src.agents.revision_router import build_revision_router_node
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
    revision_router = build_revision_router_node()
    graph.add_node("revision_router", revision_router)

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
        # Log the state for debugging
        logger.info(f"[GRAPH] Judge router state: {state}")
        
        # Get the next_step from the judgement
        judgement = state.get("judgement")
        logger.info(f"[GRAPH] Judge router judgement: {judgement}")
        
        # Check if judgement is None or empty
        if not judgement or not isinstance(judgement, dict):
            logger.warning(f"[GRAPH] Judgement is not a dictionary or is empty: {judgement}")
            # Try to get next_step from individual fields for backward compatibility
            next_step = state.get("next_step", "PASS_TO_FINALIZE")
            logger.info(f"[GRAPH] Using next_step from state: {next_step}")
        else:
            # Get next_step from judgement
            next_step = judgement.get("next_step", "PASS_TO_FINALIZE")
            logger.info(f"[GRAPH] Using next_step from judgement: {next_step}")
        
        # If judge output is aggregated per analyst, handle accordingly
        if (
            isinstance(judgement, dict)
            and "decision" not in judgement
        ):
            # pick first routing for simplicity in placeholder
            for analyst, result in judgement.items():
                if isinstance(result, dict) and "next_step" in result:
                    next_step = result.get("next_step", "PASS_TO_FINALIZE")
                    logger.info(f"[GRAPH] Using next_step from analyst result: {next_step}")
                    break
        
        # If next_step is just PASS_TO_ANALYST without specifying which analyst,
        # default to the first analyst in the list
        if next_step == "PASS_TO_ANALYST" and analyst_keys:
            # This is a fallback in case the judge.py file didn't specify a target analyst
            logger.info(f"[GRAPH] No specific analyst specified for PASS_TO_ANALYST, defaulting to {analyst_keys[0]}")
            return f"PASS_TO_ANALYST_{analyst_keys[0]}"
            
        return next_step

    # Add conditional edges from judge
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

    # Add conditional edges from revision router
    graph.add_conditional_edges(
        "revision_router",
        revision_router,
        {
            "analyst_market_structure": "analyst_market_structure",
            "analyst_product_safety": "analyst_product_safety",
            "analyst_property_rights": "analyst_property_rights",
            "analyst_societal_impact": "analyst_societal_impact",
            "judge": "judge",
        },
    )

    # Add edges from analysts to revision router when in multi-analyst revision mode
    for key in ANALYST_SUBGRAPHS.keys():
        # Add a conditional edge from each analyst
        def analyst_router(state: AgentState, analyst_key=key) -> str:
            # If we're in multi-analyst revision mode, route to the revision router
            if state.get("analysts_needing_revision") and state.get("current_revision_analyst") == analyst_key:
                logger.info(f"[GRAPH] Routing from analyst_{analyst_key} to revision_router")
                return "revision_router"
            # Otherwise, follow the normal flow
            if analyst_key == analyst_keys[-1]:
                logger.info(f"[GRAPH] Routing from analyst_{analyst_key} to judge (normal flow)")
                return "judge"
            else:
                next_analyst = analyst_keys[analyst_keys.index(analyst_key) + 1]
                logger.info(f"[GRAPH] Routing from analyst_{analyst_key} to analyst_{next_analyst} (normal flow)")
                return f"analyst_{next_analyst}"

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
```

## Implementation Steps

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

3. Update the conditional edges from the judge to include the "MULTI_ANALYST_REVISION" next_step:
   ```python
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

4. Add conditional edges from the revision router to all possible analyst nodes and the judge:
   ```python
   # Add conditional edges from revision router
   graph.add_conditional_edges(
       "revision_router",
       revision_router,
       {
           "analyst_market_structure": "analyst_market_structure",
           "analyst_product_safety": "analyst_product_safety",
           "analyst_property_rights": "analyst_property_rights",
           "analyst_societal_impact": "analyst_societal_impact",
           "judge": "judge",
       },
   )
   ```

5. Add conditional edges from each analyst to handle routing based on whether we're in multi-analyst revision mode:
   ```python
   # Add edges from analysts to revision router when in multi-analyst revision mode
   for key in ANALYST_SUBGRAPHS.keys():
       # Add a conditional edge from each analyst
       def analyst_router(state: AgentState, analyst_key=key) -> str:
           # If we're in multi-analyst revision mode, route to the revision router
           if state.get("analysts_needing_revision") and state.get("current_revision_analyst") == analyst_key:
               logger.info(f"[GRAPH] Routing from analyst_{analyst_key} to revision_router")
               return "revision_router"
           # Otherwise, follow the normal flow
           if analyst_key == analyst_keys[-1]:
               logger.info(f"[GRAPH] Routing from analyst_{analyst_key} to judge (normal flow)")
               return "judge"
           else:
               next_analyst = analyst_keys[analyst_keys.index(analyst_key) + 1]
               logger.info(f"[GRAPH] Routing from analyst_{analyst_key} to analyst_{next_analyst} (normal flow)")
               return f"analyst_{next_analyst}"

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
   ```

## Considerations

- The updated graph maintains backward compatibility by still supporting the single-analyst revision case.
- The multi-analyst revision case is handled by routing to the revision router when the next_step is "MULTI_ANALYST_REVISION".
- The revision router handles the transition between analysts during the revision process.
- We add conditional edges from each analyst to handle routing based on whether we're in multi-analyst revision mode.
- The analyst_router function checks if we're in multi-analyst revision mode by checking if the analysts_needing_revision list exists and if the current_revision_analyst matches the analyst being processed.
