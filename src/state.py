from typing import TypedDict, List, Optional, Dict, Any
from typing_extensions import Annotated
from langgraph.graph import add_messages
from pydantic import BaseModel


class AgentState(TypedDict, total=False):
    # Static identifiers (read-only, not updated concurrently)
    bill_id: Annotated[
        str, "static"
    ]  # Use static to prevent concurrent updates
    bill_text: Annotated[str, "static"]

    # Extractor output (single value)
    bill_extracts: Optional[str]

    # Summarizer output (single value)
    summary: Optional[str]

    # Analysts outputs (multiple analysts may write concurrently)
    analyst_results: Dict[
        str, Any
    ]  # Removed add_messages annotation to prevent message conversion

    # Judge outputs
    judge_feedback: Optional[str]
    feedback: Optional[Dict[str, str]]  # keyed by analyst_id
    next_step: Optional[str]

    # Retry tracking
    retry_attempts: Dict[str, int]  # track retries per analyst

    # Final status
    status: str


class SummaryOutput(BaseModel):
    summary: str


class ExtractOutput(BaseModel):
    bill_extracts: str


class AnalystOutput(BaseModel):
    score: int
    justification: str
    attempts: int


class JudgeOutput(BaseModel):
    next_step: str
    feedback: Optional[str]
