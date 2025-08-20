"""
Analyst Subgraphs Implementation

This module defines a subgraph for each analyst agent defined in
`analysts_config.py`. Each analyst is modeled as its own LangGraph
subgraph, which takes the extracted bill text as input and produces
a JSON-like analysis output (score + justification).
"""

from langgraph.graph import StateGraph, END
from src.state import AgentState
from src.agents.configs.analysts_config import ANALYST_DEFINITIONS
import logging
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser

logger = logging.getLogger(__name__)


def make_analyst_node(analyst_key: str):
    """
    Factory to create an analyst node function based on its config.
    """

    config = ANALYST_DEFINITIONS[analyst_key]

    def analyst_fn(state: AgentState) -> AgentState:
        bill_id = state.get("bill_id", "unknown")
        logger.info(f"[ANALYST:{analyst_key}] Starting analysis for bill {bill_id}")

        bill_extracts = state.get("bill_extracts", "")
        if not bill_extracts:
            logger.warning(
                f"[ANALYST:{analyst_key}] No bill_extracts found in state for bill {bill_id}"
            )
            state[f"{analyst_key}_analysis"] = {"error": "No bill extracts provided"}
            return state

        logger.info(
            f"[ANALYST:{analyst_key}] Processing bill {bill_id} with {len(bill_extracts)} characters"
        )

        # Choose instructions: revision or task
        if state.get("feedback") and analyst_key in state["feedback"]:
            instructions = (
                config["revision_instructions"].format(
                    feedback=state["feedback"][analyst_key]
                )
                + "\n"
                + config["scoring_rubric"]
            )
        else:
            instructions = config["task_instructions"] + "\n" + config["scoring_rubric"]

        # Build prompt from config
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    config["persona"] + "\n" + config["scope"] + "\n" + instructions,
                ),
                ("human", "{bill_extracts}"),
            ]
        )

        # Define parser
        parser = JsonOutputParser()

        # Build chain
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        chain = prompt | llm | parser

        try:
            logger.info(f"[ANALYST:{analyst_key}] Calling LLM for bill {bill_id}")
            result = chain.invoke({"bill_extracts": bill_extracts})
            logger.info(
                f"[ANALYST:{analyst_key}] LLM call completed for bill {bill_id}"
            )

            # Initialize analyst_results if it doesn't exist
            if "analyst_results" not in state:
                state["analyst_results"] = {}
            # Add this analyst's result to the analyst_results dictionary
            state["analyst_results"][analyst_key] = result
            # Keep the old field for backward compatibility
            state[f"{analyst_key}_analysis"] = result

            # Log the score and justification length
            score = result.get("score", "unknown")
            justification = result.get("justification", "")
            justification_length = len(justification) if justification else 0
            logger.info(
                f"[ANALYST:{analyst_key}] Assigned score {score} with justification of {justification_length} characters for bill {bill_id}"
            )
        except Exception as e:
            logger.error(f"[ANALYST:{analyst_key}] Failed for bill {bill_id}: {e}")
            if "analyst_results" not in state:
                state["analyst_results"] = {}
            state["analyst_results"][analyst_key] = {"error": str(e)}
            state[f"{analyst_key}_analysis"] = {"error": str(e)}
            logger.error(
                f"[ANALYST:{analyst_key}] State update: {analyst_key}_analysis -> error {e}"
            )

        logger.info(f"[ANALYST:{analyst_key}] Completed analysis for bill {bill_id}")
        return state

    return analyst_fn


def build_analyst_subgraph(analyst_key: str) -> StateGraph:
    """
    Build a LangGraph subgraph for a specific analyst.

    Args:
        analyst_key (str): The key in ANALYST_DEFINITIONS.

    Returns:
        StateGraph: A LangGraph subgraph for the analyst.
    """
    graph = StateGraph(AgentState)
    graph.add_node(analyst_key, make_analyst_node(analyst_key))
    graph.set_entry_point(analyst_key)
    graph.add_edge(analyst_key, END)
    return graph


# Convenience: build all analyst subgraphs
ANALYST_SUBGRAPHS = {
    key: build_analyst_subgraph(key) for key in ANALYST_DEFINITIONS.keys()
}
