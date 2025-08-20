"""
Summarizer Subgraph Implementation

This module defines the Summarizer agent subgraph, responsible for producing
concise summaries directly from the raw bill text. It uses LangGraph to define
a workflow that takes raw bill text and outputs a summary string stored in the AgentState.
"""

from langgraph.graph import StateGraph, END
from src.state import AgentState
from src.agents.configs.nonanalysts_config import OTHER_AGENTS_DEFINITIONS
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser, PydanticOutputParser
from src.state import SummaryOutput
import logging

logger = logging.getLogger(__name__)


def summarize_bill_text(state: AgentState) -> AgentState:
    """
    Generate a summary from the raw bill text.

    Args:
        state (AgentState): The current agent state containing raw bill text.

    Returns:
        AgentState: Updated state with a summary string.
    """
    bill_id = state.get("bill_id", "unknown")
    logger.info(f"[SUMMARIZER] Starting summarization for bill {bill_id}")

    raw_text = state.get("bill_text", "")
    if not raw_text:
        logger.warning(
            f"[SUMMARIZER] No bill_text found in state for summarization of bill {bill_id}"
        )
        state["summary"] = "No bill text provided for summarization."
        return state

    logger.info(
        f"[SUMMARIZER] Processing bill {bill_id} with {len(raw_text)} characters"
    )

    # Define parser using Pydantic model for structured output
    parser = PydanticOutputParser(pydantic_object=SummaryOutput)

    # Get format instructions from the parser
    format_instructions = parser.get_format_instructions()

    # Build prompt from config with format instructions
    config = OTHER_AGENTS_DEFINITIONS["summarizer"]
    # Escape curly braces in format_instructions by replacing { with {{ and } with }}
    escaped_format_instructions = format_instructions.replace("{", "{{").replace(
        "}", "}}"
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                config["persona"]
                + "\n"
                + config["task_instructions"]
                + "\n\n"
                + escaped_format_instructions,
            ),
            ("human", "{bill_text}"),
        ]
    )

    # Build chain
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    chain = prompt | llm | parser

    try:
        logger.info(f"[SUMMARIZER] Calling LLM for bill {bill_id}")
        result = chain.invoke({"bill_text": raw_text})
        logger.info(f"[SUMMARIZER] LLM call completed for bill {bill_id}")

        # Extract the summary field from the Pydantic model
        state["summary"] = result.summary
        summary_length = len(result.summary)
        logger.info(
            f"[SUMMARIZER] Generated summary of {summary_length} characters for bill {bill_id}"
        )
    except Exception as e:
        logger.error(f"[SUMMARIZER] Failed for bill {bill_id}: {e}")
        state["summary"] = f"Error: {e}"
        logger.error(f"[SUMMARIZER] State update: summary -> error {e}")

    logger.info(f"[SUMMARIZER] Completed summarization for bill {bill_id}")
    return state


def build_summarizer_subgraph() -> StateGraph:
    """
    Build the Summarizer subgraph using LangGraph.

    Returns:
        StateGraph: A LangGraph subgraph for summarization.
    """
    graph = StateGraph(AgentState)
    graph.add_node("summarize", summarize_bill_text)
    graph.set_entry_point("summarize")
    graph.add_edge("summarize", END)
    return graph
