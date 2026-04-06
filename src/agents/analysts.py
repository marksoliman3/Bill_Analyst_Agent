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
from typing import Any, Dict, Callable
import json
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

logger = logging.getLogger(__name__)

# Define which exceptions should trigger a retry
def is_retryable_error(exception):
    """
    Determine if an exception should trigger a retry.
    Specifically targets OpenAI server-side errors (500s).
    """
    logger.info(f"Checking if exception is retryable: {str(exception)}")
    
    # Check if it's an exception with a response attribute (like openai.APIError)
    if hasattr(exception, 'response') and exception.response:
        if exception.response.status_code >= 500:
            logger.warning(f"Retryable server error detected: {exception.response.status_code}")
            return True
    
    # Check error message for common server error indicators
    error_str = str(exception).lower()
    if any(indicator in error_str for indicator in ['server error', 'timeout', 'rate limit', 'overloaded']):
        logger.warning(f"Retryable error detected from error message: {error_str}")
        return True
        
    return False

# Create a retry decorator for LLM calls
@retry(
    retry=retry_if_exception(is_retryable_error),
    stop=stop_after_attempt(3),  # Try 3 times max
    wait=wait_exponential(multiplier=1, min=2, max=10),  # Start with 2s, then 4s, then 8s
    reraise=True,  # Reraise the last exception if all retries fail
    before_sleep=lambda retry_state: logger.warning(
        f"Retrying LLM call after error. Attempt {retry_state.attempt_number} of 3. "
        f"Waiting {retry_state.next_action.sleep} seconds..."
    )
)
def call_llm_with_retry(chain, inputs):
    """Call the LLM with retry logic for transient errors."""
    logger.info(f"Calling LLM with retry logic, inputs: {str(inputs)[:100]}...")
    return chain.invoke(inputs)


def sanitize_for_json(text: str) -> str:
    """
    Sanitize the text to ensure it can be properly parsed as JSON.
    Escapes apostrophes and other problematic characters.
    
    Args:
        text (str): The text to sanitize
        
    Returns:
        str: Sanitized text that can be safely parsed as JSON
    """
    # Handle apostrophes in strings
    text = text.replace("'", "\\'")
    # Handle other potentially problematic characters
    text = text.replace('\n', '\\n')
    text = text.replace('\r', '\\r')
    text = text.replace('\t', '\\t')
    # Log that we're sanitizing the text
    logger.debug(f"Sanitized text for JSON parsing: {text[:100]}...")
    return text


class SanitizedJsonOutputParser(JsonOutputParser):
    """
    A JSON output parser that sanitizes the text before parsing.
    Also validates and enforces the score to be only 0, 0.5, or 1.
    """
    
    def parse(self, text: str) -> Dict[str, Any]:
        """
        Parse the text into a JSON object, sanitizing it first.
        
        Args:
            text (str): The text to parse
            
        Returns:
            Dict[str, Any]: The parsed JSON object with validated score
        """
        sanitized_text = sanitize_for_json(text)
        try:
            result = super().parse(sanitized_text)
            # Validate and normalize score to ensure it's exactly 0, 0.5, or 1
            if "score" in result:
                score_value = result["score"]
                # Convert to float if it's a string but looks like a number
                if isinstance(score_value, str):
                    try:
                        score_value = float(score_value)
                        result["score"] = score_value
                    except ValueError:
                        logger.warning(f"Non-numeric score found: {score_value}, defaulting to 0")
                        result["score"] = 0
                
                # Ensure score is one of the valid values
                if result["score"] not in [0, 0.5, 1]:
                    # Find the closest valid score
                    valid_scores = [0, 0.5, 1]
                    closest = min(valid_scores, key=lambda x: abs(x - float(result["score"])))
                    logger.warning(f"Invalid score {result['score']} coerced to nearest valid value: {closest}")
                    result["score"] = closest
            return result
        except Exception as e:
            logger.warning(f"JSON parsing failed even after sanitization: {e}")
            # If parsing still fails, try a more direct approach with json.loads
            try:
                # Find JSON-like content using a simple heuristic
                start_idx = text.find('{')
                end_idx = text.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    json_text = text[start_idx:end_idx+1]
                    sanitized_json = sanitize_for_json(json_text)
                    result = json.loads(sanitized_json)
                    
                    # Apply the same score validation as above
                    if "score" in result:
                        score_value = result["score"]
                        if isinstance(score_value, str):
                            try:
                                score_value = float(score_value)
                                result["score"] = score_value
                            except ValueError:
                                logger.warning(f"Non-numeric score found in fallback parsing: {score_value}, defaulting to 0")
                                result["score"] = 0
                                
                        # Ensure score is one of the valid values
                        if result["score"] not in [0, 0.5, 1]:
                            valid_scores = [0, 0.5, 1]
                            closest = min(valid_scores, key=lambda x: abs(x - float(result["score"])))
                            logger.warning(f"Invalid score {result['score']} in fallback parsing coerced to nearest valid value: {closest}")
                            result["score"] = closest
                    return result
                else:
                    raise ValueError("Could not find JSON-like content")
            except Exception as inner_e:
                logger.error(f"All JSON parsing attempts failed: {inner_e}")
                raise e  # Re-raise the original exception


def make_analyst_node(analyst_key: str):
    """
    Factory to create an analyst node function based on its config.
    """

    config = ANALYST_DEFINITIONS[analyst_key]

    def analyst_fn(state: AgentState) -> AgentState:
        bill_id = state.get("bill_id", "unknown")
        logger.info(f"[ANALYST:{analyst_key}] Starting analysis for bill {bill_id}")

        # Check if this is part of a multi-analyst revision
        is_revision = False
        analysts_needing_revision = state.get("analysts_needing_revision", [])
        if analysts_needing_revision and analyst_key in analysts_needing_revision:
            logger.info(f"[ANALYST:{analyst_key}] This is part of a multi-analyst revision")
            is_revision = True

        bill_extracts = state.get("bill_extracts", "")
        if not bill_extracts:
            logger.warning(
                f"[ANALYST:{analyst_key}] No bill_extracts found in state for bill {bill_id}"
            )
            # Initialize analyst_results if it doesn't exist
            if "analyst_results" not in state:
                state["analyst_results"] = {}
            state["analyst_results"][analyst_key] = {"error": "No bill extracts provided"}
            return state

        logger.info(
            f"[ANALYST:{analyst_key}] Processing bill {bill_id} with {len(bill_extracts)} characters"
        )

        # Choose instructions: revision or task
        if (
            state.get("judgement") 
            and isinstance(state["judgement"], dict) 
            and "feedback_by_analyst" in state["judgement"] 
            and analyst_key in state["judgement"]["feedback_by_analyst"]
        ):
            # Get feedback from the judgement's feedback_by_analyst field (single source of truth)
            feedback = state["judgement"]["feedback_by_analyst"][analyst_key]
            # Add temporary logging for debugging
            logger.info(f"[ANALYST:{analyst_key}] [DEBUG] Found feedback in judgement's feedback_by_analyst: {feedback}")
            
            instructions = (
                config["revision_instructions"].format(
                    feedback=feedback
                )
                + "\n"
                + config["scoring_rubric"]
            )
            logger.info(f"[ANALYST:{analyst_key}] Using revision instructions with feedback from judgement")
        else:
            # No feedback found in the single source of truth
            if state.get("feedback") and analyst_key in state["feedback"]:
                # Add temporary logging to show we're ignoring the old feedback field
                logger.info(f"[ANALYST:{analyst_key}] [DEBUG] Ignoring deprecated feedback in state.feedback")
                
            instructions = config["task_instructions"] + "\n" + config["scoring_rubric"]
            logger.info(f"[ANALYST:{analyst_key}] Using standard task instructions")

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

        # Define parser with sanitization
        parser = SanitizedJsonOutputParser()

        # Build chain with improved configuration
        llm = ChatOpenAI(
            model="gpt-5-nano", 
            temperature=0,
            request_timeout=60,  # 60-second timeout to prevent hanging requests
            max_retries=2        # Built-in retries for network issues
        )
        chain = prompt | llm | parser

        try:
            logger.info(f"[ANALYST:{analyst_key}] Calling LLM for bill {bill_id}")
            # Use the retry wrapper instead of calling directly
            result = call_llm_with_retry(chain, {"bill_extracts": bill_extracts})
            logger.info(
                f"[ANALYST:{analyst_key}] LLM call completed for bill {bill_id}"
            )

            # Initialize analyst_results if it doesn't exist
            if "analyst_results" not in state:
                state["analyst_results"] = {}
            # Add this analyst's result to the analyst_results dictionary
            state["analyst_results"][analyst_key] = result

            # Log the score and justification length
            score = result.get("score", "unknown")
            justification = result.get("justification", "")
            justification_length = len(justification) if justification else 0
            logger.info(
                f"[ANALYST:{analyst_key}] Assigned score {score} with justification of {justification_length} characters for bill {bill_id}"
            )
            
            # If this is part of a multi-analyst revision, log that the revision is complete
            if is_revision:
                logger.info(f"[ANALYST:{analyst_key}] Completed revision as part of multi-analyst revision")
        except Exception as e:
            logger.error(f"[ANALYST:{analyst_key}] Failed for bill {bill_id}: {e}")
            if "analyst_results" not in state:
                state["analyst_results"] = {}
            state["analyst_results"][analyst_key] = {
                "error": str(e),
                # No fallback score so empty entries will show in the final output
                "justification": f"Error during analysis: {str(e)}"
            }
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
