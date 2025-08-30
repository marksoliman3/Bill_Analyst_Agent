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
from langchain_core.output_parsers import PydanticOutputParser
from src.state import JudgeOutput
from src.config import MAX_RETRY_ATTEMPTS

logger = logging.getLogger(__name__)

JUDGE_CONFIG = OTHER_AGENTS_DEFINITIONS["judge"]


def judge_analysis(state: AgentState) -> AgentState:
    """
    Review analyst outputs and produce a judgement.

    Args:
        state (AgentState): The current agent state containing analyst outputs.

    Returns:
        AgentState: Updated state with a judgement.
    """
    bill_id = state.get("bill_id", "unknown")
    logger.info(f"[JUDGE] Starting judicial review for bill {bill_id}")

    # Create a copy of the state to avoid mutations
    updated_state = state.copy() if isinstance(state, dict) else {}

    # Collect inputs
    bill_text = state.get("bill_text", "")

    # Get analyst outputs from the analyst_results field
    if (
        "analyst_results" in state
        and isinstance(state["analyst_results"], dict)
        and state["analyst_results"]
    ):
        analyst_outputs = state["analyst_results"]
        logger.info(f"[JUDGE] Found {len(analyst_outputs)} analyst outputs for bill {bill_id}")
    else:
        logger.warning(f"[JUDGE] No analyst outputs found for bill {bill_id}")
        updated_state["judgement"] = {
            "decision": "REVISE",
            "next_step": "FAIL_BILL",
            "analysts_needing_revision": [],
            "feedback_by_analyst": {}
        }
        logger.info(f"[JUDGE] Failing bill {bill_id} due to missing analyst outputs")
        return updated_state

    # Check if any analyst has reached the maximum number of retry attempts
    retry_attempts = state.get("retry_attempts", {})
    for analyst_key, attempts in retry_attempts.items():
        if attempts >= MAX_RETRY_ATTEMPTS:
            logger.info(f"[JUDGE] Analyst {analyst_key} has reached the maximum number of retry attempts ({MAX_RETRY_ATTEMPTS})")
            # Skip the LLM call and automatically pass the bill to finalization
            updated_state["judgement"] = {
                "decision": "AGREE",
                "next_step": "PASS_TO_FINALIZE",
                "analysts_needing_revision": [],
                "feedback_by_analyst": {}
            }
            logger.info(f"[JUDGE] Automatically passing bill {bill_id} to finalization due to max retries")
            return updated_state

    # Define parser using PydanticOutputParser for type safety and validation
    parser = PydanticOutputParser(pydantic_object=JudgeOutput)

    # Build prompt with task instructions and available analysts
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                JUDGE_CONFIG["persona"]
                + "\n"
                + JUDGE_CONFIG["task_instructions"]
                + "\n\n"
                + "The available analysts are: " + ", ".join(analyst_outputs.keys()) + "."
            ),
            ("human", "Bill text:\n{bill_text}\n\nAnalyst outputs:\n{analyst_outputs}")
        ]
    )

    # Build chain
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    chain = prompt | llm | parser

    try:
        # Call the LLM
        logger.info(f"[JUDGE] Calling LLM for bill {bill_id}")
        result = chain.invoke({"bill_text": bill_text, "analyst_outputs": analyst_outputs})
        logger.info(f"[JUDGE] LLM call completed for bill {bill_id}")

        # Extract judgement from the Pydantic model
        judgement = result.judgement.dict()
        logger.info(f"[JUDGE] Judgement: {judgement}")

        # Update state with judgement
        updated_state["judgement"] = judgement
        
        # Process multi-analyst revision if needed
        if judgement["next_step"] == "MULTI_ANALYST_REVISION":
            analysts_needing_revision = judgement["analysts_needing_revision"]
            logger.info(f"[JUDGE] Multiple analysts need revision: {analysts_needing_revision}")
            
            # Store the list in state (create a new list to avoid mutations)
            updated_state["analysts_needing_revision"] = analysts_needing_revision.copy()
            
            # Reset the processed_analysts list for the new revision cycle
            updated_state["processed_analysts"] = []
            logger.info(f"[JUDGE] Reset processed_analysts list for new revision cycle")
            
            # Get feedback for each analyst
            feedback_by_analyst = judgement["feedback_by_analyst"]
            
            # Add temporary logging for debugging the feedback mechanism
            logger.info(f"[JUDGE] [DEBUG] Feedback by analyst from judgement: {feedback_by_analyst}")
            
            # Only update retry attempts, not feedback (using single source of truth)
            updated_retry_attempts = state.get("retry_attempts", {}).copy() if state.get("retry_attempts") else {}
            
            # Process each analyst needing revision
            filtered_analysts = []
            
            for analyst in analysts_needing_revision:
                # Add temporary logging for each analyst's feedback
                if analyst in feedback_by_analyst:
                    logger.info(f"[JUDGE] [DEBUG] Feedback for {analyst}: {feedback_by_analyst[analyst]}")
                
                # Update retry attempts
                current_attempts = updated_retry_attempts.get(analyst, 0) + 1
                updated_retry_attempts[analyst] = current_attempts
                
                # Only include analysts that haven't reached max retries
                if current_attempts < MAX_RETRY_ATTEMPTS:
                    filtered_analysts.append(analyst)
                else:
                    logger.info(f"[JUDGE] Max retries reached for {analyst}. Removing from revision list.")
            
            # Update state with retry attempts only (no feedback - using single source of truth)
            updated_state["retry_attempts"] = updated_retry_attempts
            logger.info(f"[JUDGE] [DEBUG] Using judgement's feedback_by_analyst as single source of truth")
            
            # If all analysts have reached max retries, pass to finalize
            if not filtered_analysts:
                logger.info("[JUDGE] All analysts have reached max retries. Passing to finalize.")
                updated_judgement = judgement.copy()
                updated_judgement["next_step"] = "PASS_TO_FINALIZE"
                updated_judgement["analysts_needing_revision"] = []
                updated_state["judgement"] = updated_judgement
                updated_state["analysts_needing_revision"] = []
            else:
                # Otherwise, update the filtered list
                updated_state["analysts_needing_revision"] = filtered_analysts
            
    except Exception as e:
        logger.error(f"[JUDGE] Failed for bill {bill_id}: {e}")
        updated_state["judgement"] = {
            "decision": "REVISE",
            "next_step": "FAIL_BILL",
            "analysts_needing_revision": [],
            "feedback_by_analyst": {"error": str(e)}
        }

    logger.info(f"[JUDGE] Completed judicial review for bill {bill_id}")
    return updated_state


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
