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


def extract_json_from_text(text: str) -> str:
    """
    Extract the JSON object from LLM output text by finding the outermost { } boundaries.
    Handles cases where the LLM wraps JSON in markdown fences, preamble text, etc.

    Args:
        text (str): Raw LLM output that may contain JSON wrapped in other text

    Returns:
        str: The extracted JSON string

    Raises:
        ValueError: If no JSON-like content can be found
    """
    # Strip markdown code fences if present
    import re
    fenced = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if fenced:
        return fenced.group(1)

    # Find the outermost { } boundaries
    start_idx = text.find('{')
    end_idx = text.rfind('}')
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        return text[start_idx:end_idx + 1]

    raise ValueError("Could not find JSON-like content in LLM output")


def validate_score(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize the score field in an analyst result.
    Ensures score is exactly 0, 0.5, or 1. Removes invalid scores.

    Args:
        result: Parsed analyst result dict

    Returns:
        The result dict with validated score
    """
    if "score" not in result:
        return result

    score_value = result["score"]

    # Convert string scores to float
    if isinstance(score_value, str):
        try:
            score_value = float(score_value)
            result["score"] = score_value
        except ValueError:
            logger.warning(f"Non-numeric score found: {score_value} — removing score so it surfaces as empty")
            del result["score"]
            return result

    # Coerce to nearest valid value if needed
    valid_scores = [0, 0.5, 1]
    if result["score"] not in valid_scores:
        closest = min(valid_scores, key=lambda x: abs(x - float(result["score"])))
        logger.warning(f"Invalid score {result['score']} coerced to nearest valid value: {closest}")
        result["score"] = closest

    return result


class SanitizedJsonOutputParser(JsonOutputParser):
    """
    A JSON output parser that extracts JSON from LLM output robustly.
    Handles markdown fences, preamble text, and other wrapping.
    Also validates and enforces the score to be only 0, 0.5, or 1.
    """

    def parse(self, text: str) -> Dict[str, Any]:
        """
        Parse the text into a JSON object by first extracting JSON content,
        then falling back to the parent parser if extraction fails.

        Args:
            text (str): The raw LLM output text

        Returns:
            Dict[str, Any]: The parsed JSON object with validated score
        """
        # Primary path: extract JSON from the text and parse directly
        try:
            json_str = extract_json_from_text(text)
            result = json.loads(json_str)
            logger.debug(f"Successfully parsed JSON via direct extraction")
            return validate_score(result)
        except (ValueError, json.JSONDecodeError) as extraction_err:
            logger.debug(f"Direct JSON extraction failed: {extraction_err}")

        # Fallback: try the parent LangChain parser on the raw text
        try:
            result = super().parse(text)
            logger.debug(f"Successfully parsed JSON via LangChain parent parser")
            return validate_score(result)
        except Exception as e:
            logger.error(f"All JSON parsing attempts failed for text: {text[:200]}...")
            raise e


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

        # Retry loop: retries on parse failures to give the LLM another chance
        max_parse_attempts = 3
        last_error = None
        result = None

        for attempt in range(1, max_parse_attempts + 1):
            try:
                logger.info(f"[ANALYST:{analyst_key}] Calling LLM for bill {bill_id} (attempt {attempt}/{max_parse_attempts})")
                # Use the retry wrapper (handles API-level errors like 500s/timeouts)
                raw_result = call_llm_with_retry(chain, {"bill_extracts": bill_extracts})

                # Guard against None/empty responses (Fix 3)
                if raw_result is None:
                    raise ValueError("LLM returned None response")
                if isinstance(raw_result, dict) and "score" not in raw_result and "justification" not in raw_result:
                    raise ValueError(f"LLM returned response with no score or justification: {raw_result}")

                result = raw_result
                logger.info(f"[ANALYST:{analyst_key}] LLM call completed for bill {bill_id}")
                break  # Success — exit retry loop

            except Exception as e:
                last_error = e
                if attempt < max_parse_attempts:
                    logger.warning(
                        f"[ANALYST:{analyst_key}] Attempt {attempt}/{max_parse_attempts} failed for bill {bill_id}: {e}. Retrying..."
                    )
                else:
                    logger.error(
                        f"[ANALYST:{analyst_key}] All {max_parse_attempts} attempts failed for bill {bill_id}: {e}"
                    )

        if result is not None:
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
        else:
            logger.error(f"[ANALYST:{analyst_key}] Failed for bill {bill_id}: {last_error}")
            if "analyst_results" not in state:
                state["analyst_results"] = {}
            state["analyst_results"][analyst_key] = {
                "error": str(last_error),
                "justification": f"Error during analysis: {str(last_error)}"
            }

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
