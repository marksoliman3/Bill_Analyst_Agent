"""
Extractor Subgraph Implementation

This module defines the Extractor agent subgraph, responsible for parsing
bill text into a structured representation. It uses LangGraph to define
a simple workflow that takes raw text and outputs structured data
conforming to the AgentState model.
"""

from typing import Dict, Any
from langgraph.graph import StateGraph, END
from src.state import AgentState
from src.agents.configs.nonanalysts_config import OTHER_AGENTS_DEFINITIONS
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser, PydanticOutputParser
from src.state import ExtractOutput
import logging

logger = logging.getLogger(__name__)


def extract_bill_text(state: AgentState) -> AgentState:
    """
    Extract structured information from raw bill text.

    Args:
        state (AgentState): The current agent state containing raw bill text.

    Returns:
        AgentState: Updated state with extracted structured data.
    """
    bill_id = state.get("bill_id", "unknown")
    logger.info(f"[EXTRACTOR] Starting extraction for bill {bill_id}")

    raw_text = state.get("bill_text", "")
    if not raw_text:
        logger.warning(
            f"[EXTRACTOR] No bill_text found in state for extraction of bill {bill_id}"
        )
        # Use bill_extracts instead of extracted to match AgentState definition
        state["bill_extracts"] = "No bill text provided"
        return state

    logger.info(
        f"[EXTRACTOR] Processing bill {bill_id} with {len(raw_text)} characters"
    )

    # Define parser using Pydantic model for structured output
    parser = PydanticOutputParser(pydantic_object=ExtractOutput)

    # Get format instructions from the parser
    format_instructions = parser.get_format_instructions()

    # Build prompt from config with format instructions
    config = OTHER_AGENTS_DEFINITIONS["extractor"]
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
        logger.info(f"[EXTRACTOR] Calling LLM for bill {bill_id}")
        result = chain.invoke({"bill_text": raw_text})
        logger.info(f"[EXTRACTOR] LLM call completed for bill {bill_id}")

        # Extract the bill_extracts field from the Pydantic model
        extracted_text = result.bill_extracts
        
        # Minimum extraction guarantee
        if not extracted_text or len(extracted_text) < 50:
            logger.warning(f"[EXTRACTOR] Empty or minimal extraction for bill {bill_id}. Providing fallback extraction.")
            
            # Extract bill title, intro and first section as a fallback
            import re
            
            # Try to get bill title and first section
            title_pattern = r"^(.*?(?:BILL|ACT).*?)(?:\n\n|$)"
            title_match = re.search(title_pattern, raw_text, re.DOTALL | re.IGNORECASE)
            
            section_pattern = r"(?:Section 1\..*?)(?:\n\nSection 2\.|\Z)"
            section_match = re.search(section_pattern, raw_text, re.DOTALL)
            
            # Build fallback text
            fallback_text = ""
            
            if title_match:
                fallback_text += title_match.group(0) + "\n\n"
            
            if section_match:
                fallback_text += section_match.group(0)
            
            # If we couldn't extract structured content, use first 500 characters
            if len(fallback_text) < 50:
                fallback_text = raw_text[:min(500, len(raw_text))]
            
            # Add a note for downstream agents
            fallback_text += "\n\n[NOTE: Limited relevant content found in this bill. Providing minimal extraction for analysis.]"
            
            extracted_text = fallback_text
            logger.info(f"[EXTRACTOR] Used fallback extraction, resulting in {len(extracted_text)} characters")
        
        state["bill_extracts"] = extracted_text
        extract_length = len(extracted_text)
        logger.info(
            f"[EXTRACTOR] Extracted {extract_length} characters for bill {bill_id}"
        )
    except Exception as e:
        logger.error(f"[EXTRACTOR] Failed for bill {bill_id}: {e}")
        # Convert the error to a string to match the AgentState type definition
        state["bill_extracts"] = str({"error": str(e)})
        logger.error(f"[EXTRACTOR] State update: bill_extracts -> error {e}")

    logger.info(f"[EXTRACTOR] Completed extraction for bill {bill_id}")
    return state


def build_extractor_subgraph() -> StateGraph:
    """
    Build the Extractor subgraph using LangGraph.

    Returns:
        StateGraph: A LangGraph subgraph for extraction.
    """
    graph = StateGraph(AgentState)
    graph.add_node("extract", extract_bill_text)
    graph.set_entry_point("extract")
    graph.add_edge("extract", END)
    return graph
