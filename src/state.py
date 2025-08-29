from typing import TypedDict, List, Optional, Dict, Any, Literal
from typing_extensions import Annotated
from langgraph.graph import add_messages
from pydantic import BaseModel, Field


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
    judgement: Optional[Dict[str, Any]]  # Contains decision, next_step, analysts_needing_revision, and feedback_by_analyst
    feedback: Optional[Dict[str, str]]  # keyed by analyst_id

    # Retry tracking
    retry_attempts: Dict[str, int]  # track retries per analyst

    # Multi-analyst revision tracking
    analysts_needing_revision: Optional[List[str]]  # List of analyst IDs that need revision
    processed_analysts: Optional[List[str]]  # List of analyst IDs that have been processed in the current revision cycle

    # Consolidator output
    consolidated_report: Optional[Dict[str, Any]]
    
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


# Add a nested model for the judgement content
class JudgementContent(BaseModel):
    decision: Literal["AGREE", "REVISE"] = Field(
        description="The overall decision, either 'AGREE' or 'REVISE'"
    )
    next_step: Literal["MULTI_ANALYST_REVISION", "PASS_TO_FINALIZE", "FAIL_BILL"] = Field(
        description="The next step in the workflow"
    )
    analysts_needing_revision: List[str] = Field(
        default=[],
        description="List of analyst names that need revision (only if next_step is 'MULTI_ANALYST_REVISION')"
    )
    feedback_by_analyst: Dict[str, str] = Field(
        default={},
        description="Dictionary mapping analyst names to feedback strings (only for analysts needing revision)"
    )

class JudgeOutput(BaseModel):
    judgement: JudgementContent = Field(
        description="The judge's decision, including overall decision, next step, and feedback"
    )
