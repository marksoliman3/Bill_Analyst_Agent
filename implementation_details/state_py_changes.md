# Implementation Details for src/state.py

## Current Implementation

The current `AgentState` TypedDict in `state.py` includes fields for tracking the bill information, agent outputs, and retry attempts, but it doesn't have a way to track multiple analysts needing revision simultaneously.

```python
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
    judgement: Optional[Dict[str, Any]]  # Contains decision, feedback, and next_step
    judge_feedback: Optional[str]  # For backward compatibility
    feedback: Optional[Dict[str, str]]  # keyed by analyst_id
    next_step: Optional[str]  # For backward compatibility

    # Retry tracking
    retry_attempts: Dict[str, int]  # track retries per analyst

    # Consolidator output
    consolidated_report: Optional[Dict[str, Any]]
    
    # Final status
    status: str
```

## Proposed Changes

We need to add two new fields to the `AgentState` TypedDict:

1. `analysts_needing_revision`: A list of analyst IDs that need revision
2. `current_revision_analyst`: The ID of the analyst currently being processed in a revision cycle

Here's the updated `AgentState` TypedDict:

```python
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
    judgement: Optional[Dict[str, Any]]  # Contains decision, feedback, and next_step
    judge_feedback: Optional[str]  # For backward compatibility
    feedback: Optional[Dict[str, str]]  # keyed by analyst_id
    next_step: Optional[str]  # For backward compatibility

    # Retry tracking
    retry_attempts: Dict[str, int]  # track retries per analyst

    # Multi-analyst revision tracking
    analysts_needing_revision: Optional[List[str]]  # List of analyst IDs that need revision
    current_revision_analyst: Optional[str]  # Current analyst being processed in a revision cycle

    # Consolidator output
    consolidated_report: Optional[Dict[str, Any]]
    
    # Final status
    status: str
```

## Implementation Steps

1. Add the necessary import for `List` if it's not already imported:
   ```python
   from typing import TypedDict, List, Optional, Dict, Any
   ```

2. Add the two new fields to the `AgentState` TypedDict as shown above.

3. No changes are needed to the Pydantic models (`SummaryOutput`, `ExtractOutput`, `AnalystOutput`, `JudgeOutput`) as they define the output structure of individual agents, not the overall state.

## Considerations

- The `analysts_needing_revision` field is a list because we need to maintain the order of analysts to be processed.
- The `current_revision_analyst` field helps track which analyst is currently being processed in a revision cycle, which is useful for logging and debugging.
- Both fields are optional (`Optional`) because they're only relevant during the revision process.
