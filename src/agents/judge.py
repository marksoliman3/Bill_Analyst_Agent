"""
Judge Subgraph Implementation

This module defines the Judge agent subgraph, responsible for reviewing
analyst outputs against the bill text, rubric, and scope. It uses LangGraph
to define a workflow that takes analyst results and produces a judgement
(decision, feedback, and routing step).
"""

from langgraph.graph import StateGraph, END
from src.state import AgentState
from src.agents.configs.nonanalysts_config import OTHER_AGENTS_DEFINITIONS
import logging
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser

logger = logging.getLogger(__name__)

JUDGE_CONFIG = OTHER_AGENTS_DEFINITIONS["judge"]


def judge_analysis(state: AgentState) -> AgentState:
    """
    Review an analyst's output and produce a judgement.

    Args:
        state (AgentState): The current agent state containing analyst outputs.

    Returns:
        AgentState: Updated state with a judgement.
    """
    bill_id = state.get("bill_id", "unknown")
    logger.info(f"[JUDGE] Starting judicial review for bill {bill_id}")

    # Collect inputs
    bill_text = state.get("bill_text", "")

    # First try to get analyst outputs from the analyst_results field
    if (
        "analyst_results" in state
        and isinstance(state["analyst_results"], dict)
        and state["analyst_results"]
    ):
        analyst_outputs = state["analyst_results"]
        logger.info(
            f"[JUDGE] Found {len(analyst_outputs)} analyst outputs for bill {bill_id}"
        )
    else:
        # Fallback to the old method for backward compatibility
        analyst_outputs = {k: v for k, v in state.items() if k.endswith("_analysis")}
        logger.info(
            f"[JUDGE] Using fallback method, found {len(analyst_outputs)} analyst outputs for bill {bill_id}"
        )

    if not analyst_outputs:
        logger.warning(f"[JUDGE] No analyst outputs found for bill {bill_id}")
        state["judgement"] = {
            "decision": "FAIL_BILL",
            "feedback": "No analyst outputs available.",
            "next_step": "FAIL_BILL",
        }
        logger.info(f"[JUDGE] Failing bill {bill_id} due to missing analyst outputs")
        return state

    # Build prompt from config
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                JUDGE_CONFIG["persona"] + "\n" + JUDGE_CONFIG["task_instructions"],
            ),
            ("human", "Bill text:\n{bill_text}\n\nAnalyst outputs:\n{analyst_outputs}"),
        ]
    )

    # Define parser
    parser = JsonOutputParser()

    # Get format instructions from the parser
    format_instructions = parser.get_format_instructions()

    # Escape curly braces in format instructions
    escaped_format_instructions = format_instructions.replace("{", "{{").replace(
        "}", "}}"
    )

    # Update prompt to include format instructions
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                JUDGE_CONFIG["persona"]
                + "\n"
                + JUDGE_CONFIG["task_instructions"]
                + "\n\n"
                + escaped_format_instructions,
            ),
            ("human", "Bill text:\n{bill_text}\n\nAnalyst outputs:\n{analyst_outputs}"),
        ]
    )

    # Build chain
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    chain = prompt | llm | parser

    try:
        logger.info(f"[JUDGE] Calling LLM for bill {bill_id}")
        result = chain.invoke(
            {"bill_text": bill_text, "analyst_outputs": analyst_outputs}
        )
        logger.info(f"[JUDGE] LLM call completed for bill {bill_id}")

        state["judgement"] = result
        decision = result.get("decision", "UNKNOWN")
        next_step = result.get("next_step", "UNKNOWN")
        logger.info(
            f"[JUDGE] Decision: {decision}, Next step: {next_step} for bill {bill_id}"
        )

        # Store feedback in state for targeted analyst if available
        if "target_analyst" in result and "feedback" in result:
            if "feedback" not in state or state["feedback"] is None:
                state["feedback"] = {}
            state["feedback"][result["target_analyst"]] = result["feedback"]
            logger.info(
                f"Feedback for {result['target_analyst']}: {result['feedback']}"
            )

            # Track retry attempts per analyst
            if "retry_attempts" not in state or state["retry_attempts"] is None:
                state["retry_attempts"] = {}
            current_attempts = (
                state["retry_attempts"].get(result["target_analyst"], 0) + 1
            )
            state["retry_attempts"][result["target_analyst"]] = current_attempts
            logger.info(
                f"Retry attempts for {result['target_analyst']}: {current_attempts}"
            )

            # Check against max retries
            from src.config import MAX_RETRY_ATTEMPTS

            if current_attempts >= MAX_RETRY_ATTEMPTS:
                # Stop looping, accept last analyst score
                result["next_step"] = "PASS_TO_FINALIZE"
                state["judgement"] = result
                logger.info(
                    f"Max retries reached for {result['target_analyst']}. Accepting last score."
                )
    except Exception as e:
        logger.error(f"[JUDGE] Failed for bill {bill_id}: {e}")
        state["judgement"] = {"error": str(e)}

    logger.info(f"[JUDGE] Completed judicial review for bill {bill_id}")
    return state


def build_judge_subgraph() -> StateGraph:
    """
    Build the Judge subgraph using LangGraph.

    Returns:
        StateGraph: A LangGraph subgraph for judgement.
    """
    graph = StateGraph(AgentState)
    graph.add_node("judge", judge_analysis)
    graph.set_entry_point("judge")
    graph.add_edge("judge", END)
    return graph
