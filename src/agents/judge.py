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
from langchain_core.output_parsers import JsonOutputParser, PydanticOutputParser
from src.state import JudgeOutput

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
        judgement = {
            "decision": "FAIL_BILL",
            "feedback": "No analyst outputs available.",
            "next_step": "FAIL_BILL",
        }
        state["judgement"] = judgement
        
        # Also update individual fields for backward compatibility
        state["judge_feedback"] = judgement["feedback"]
        state["next_step"] = judgement["next_step"]
        
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

    # Define parser using Pydantic model for structured output
    parser = PydanticOutputParser(pydantic_object=JudgeOutput)

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
                + "The available analysts are: " + ", ".join(analyst_outputs.keys()) + "."
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
        # Check if any analyst has reached the maximum number of retry attempts
        from src.config import MAX_RETRY_ATTEMPTS
        
        for analyst_key, attempts in state.get("retry_attempts", {}).items():
            if attempts >= MAX_RETRY_ATTEMPTS:
                logger.info(f"[JUDGE] Analyst {analyst_key} has reached the maximum number of retry attempts ({MAX_RETRY_ATTEMPTS})")
                # Skip the LLM call and automatically pass the bill to finalization
                judgement = {
                    "decision": "AGREE",
                    "feedback": None,
                    "next_step": "PASS_TO_FINALIZE",
                }
                state["judgement"] = judgement
                
                # Also update individual fields for backward compatibility
                state["judge_feedback"] = judgement["feedback"]
                state["next_step"] = judgement["next_step"]
                
                logger.info(f"[JUDGE] Automatically passing bill {bill_id} to finalization due to max retries")
                return state
        
        logger.info(f"[JUDGE] Calling LLM for bill {bill_id}")
        result = chain.invoke(
            {"bill_text": bill_text, "analyst_outputs": analyst_outputs}
        )
        logger.info(f"[JUDGE] LLM call completed for bill {bill_id}")

        # Extract decision, feedback, and next_step from result
        # Handle both dictionary and Pydantic object
        if hasattr(result, "dict"):
            # It's a Pydantic object, convert to dict
            result_dict = result.dict()
            if "judgement" in result_dict and isinstance(result_dict["judgement"], dict):
                # It's already a nested structure
                judgement = result_dict.get("judgement", {})
            else:
                # It's a flat structure, create a nested one
                judgement = {
                    "decision": result_dict.get("decision", "UNKNOWN"),
                    "feedback": result_dict.get("feedback", None),
                    "next_step": result_dict.get("next_step", "UNKNOWN")
                }
        else:
            # It's already a dictionary
            if "judgement" in result and isinstance(result["judgement"], dict):
                # It's already a nested structure
                judgement = result.get("judgement", {})
            else:
                # It's a flat structure, create a nested one
                judgement = {
                    "decision": result.get("decision", "UNKNOWN"),
                    "feedback": result.get("feedback", None),
                    "next_step": result.get("next_step", "UNKNOWN")
                }
        
        # Log the extracted judgement for debugging
        logger.info(f"[JUDGE] Extracted judgement: {judgement}")
        
        # Ensure judgement has the required fields
        if not judgement or not isinstance(judgement, dict):
            judgement = {
                "decision": "UNKNOWN",
                "feedback": None,
                "next_step": "UNKNOWN"
            }
        
        # Extract decision, feedback, and next_step for logging
        decision = judgement.get("decision", "UNKNOWN")
        feedback = judgement.get("feedback", None)
        next_step = judgement.get("next_step", "UNKNOWN")
        
        # Ensure judgement is a dictionary with the required fields
        if not isinstance(judgement, dict):
            logger.warning(f"[JUDGE] Judgement is not a dictionary: {judgement}")
            judgement = {
                "decision": "UNKNOWN",
                "feedback": None,
                "next_step": "UNKNOWN"
            }
        
        # Ensure all required fields are present
        if "decision" not in judgement:
            judgement["decision"] = "UNKNOWN"
        if "feedback" not in judgement:
            judgement["feedback"] = None
        if "next_step" not in judgement:
            judgement["next_step"] = "UNKNOWN"
        
        # Update judgement in state
        state["judgement"] = judgement
        
        # Also update individual fields for backward compatibility
        state["judge_feedback"] = feedback
        state["next_step"] = next_step
        
        # Log the state update for debugging
        logger.info(f"[JUDGE] Updated state with judgement: {state['judgement']}")
        
        logger.info(
            f"[JUDGE] Decision: {decision}, Next step: {next_step} for bill {bill_id}"
        )

        # Extract target analyst from next_step if it's in the format PASS_TO_ANALYST_[analyst_name]
        target_analyst = None
        if next_step.startswith("PASS_TO_ANALYST_"):
            target_analyst = next_step.replace("PASS_TO_ANALYST_", "")
            logger.info(f"Extracted target analyst from next_step: {target_analyst}")
        
        # Store feedback in state for targeted analyst if available
        if target_analyst and feedback:
            if "feedback" not in state or state["feedback"] is None:
                state["feedback"] = {}
            state["feedback"][target_analyst] = feedback
            logger.info(
                f"Feedback for {target_analyst}: {feedback}"
            )

            # Track retry attempts per analyst
            if "retry_attempts" not in state or state["retry_attempts"] is None:
                state["retry_attempts"] = {}
            current_attempts = (
                state["retry_attempts"].get(target_analyst, 0) + 1
            )
            state["retry_attempts"][target_analyst] = current_attempts
            logger.info(
                f"Retry attempts for {target_analyst}: {current_attempts}"
            )

            # Check against max retries
            from src.config import MAX_RETRY_ATTEMPTS

            if current_attempts >= MAX_RETRY_ATTEMPTS:
                # Stop looping, accept last analyst score
                judgement["next_step"] = "PASS_TO_FINALIZE"
                state["judgement"] = judgement
                
                # Also update individual fields for backward compatibility
                state["judge_feedback"] = judgement["feedback"]
                state["next_step"] = judgement["next_step"]
                
                logger.info(
                    f"Max retries reached for {target_analyst}. Accepting last score."
                )
    except Exception as e:
        logger.error(f"[JUDGE] Failed for bill {bill_id}: {e}")
        judgement = {"error": str(e)}
        state["judgement"] = judgement
        
        # Also update individual fields for backward compatibility
        state["judge_feedback"] = None
        state["next_step"] = "FAIL_BILL"

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
