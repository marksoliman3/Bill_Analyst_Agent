# Implementation Details for src/agents/judge.py

## Current Implementation

The current `judge.py` file defines the Judge agent subgraph, which reviews analyst outputs and produces a judgement. The key function is `judge_analysis`, which processes the state and updates it with the judge's decision. Currently, it only supports routing to a single analyst for revision:

```python
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
```

## Proposed Changes

We need to update the `judge_analysis` function to handle the new multi-analyst revision case:

1. Check if the next_step is "MULTI_ANALYST_REVISION"
2. Extract the list of analysts needing revision from the judgement
3. Store feedback for each analyst in the feedback dictionary
4. Update retry attempts for each analyst
5. Check if any analyst has reached the maximum number of retry attempts
6. Update the state with the list of analysts needing revision

Here's the updated code section:

```python
# Check if this is a multi-analyst revision case
if next_step == "MULTI_ANALYST_REVISION":
    # Extract the list of analysts needing revision
    analysts_needing_revision = judgement.get("analysts_needing_revision", [])
    logger.info(f"Multiple analysts need revision: {analysts_needing_revision}")
    
    # Store the list in state
    state["analysts_needing_revision"] = analysts_needing_revision
    
    # Get feedback for each analyst
    feedback_by_analyst = judgement.get("feedback_by_analyst", {})
    
    # Initialize feedback dictionary if it doesn't exist
    if "feedback" not in state or state["feedback"] is None:
        state["feedback"] = {}
    
    # Initialize retry_attempts dictionary if it doesn't exist
    if "retry_attempts" not in state or state["retry_attempts"] is None:
        state["retry_attempts"] = {}
    
    # Store feedback and update retry attempts for each analyst
    for analyst in analysts_needing_revision:
        # Store feedback
        if analyst in feedback_by_analyst:
            state["feedback"][analyst] = feedback_by_analyst[analyst]
            logger.info(f"Feedback for {analyst}: {feedback_by_analyst[analyst]}")
        
        # Update retry attempts
        current_attempts = state["retry_attempts"].get(analyst, 0) + 1
        state["retry_attempts"][analyst] = current_attempts
        logger.info(f"Retry attempts for {analyst}: {current_attempts}")
        
        # Check if this analyst has reached the maximum number of retry attempts
        from src.config import MAX_RETRY_ATTEMPTS
        if current_attempts >= MAX_RETRY_ATTEMPTS:
            logger.info(f"Max retries reached for {analyst}. Removing from revision list.")
            # Remove this analyst from the list
            analysts_needing_revision.remove(analyst)
    
    # If all analysts have reached max retries, pass to finalize
    if not analysts_needing_revision:
        logger.info("All analysts have reached max retries. Passing to finalize.")
        judgement["next_step"] = "PASS_TO_FINALIZE"
        state["judgement"] = judgement
        
        # Also update individual fields for backward compatibility
        state["next_step"] = judgement["next_step"]
        
        # Clear the analysts_needing_revision list
        state["analysts_needing_revision"] = []
    
    # Set the current_revision_analyst to None (will be set by revision_router)
    state["current_revision_analyst"] = None

# Handle the single-analyst case (for backward compatibility)
elif next_step.startswith("PASS_TO_ANALYST_"):
    target_analyst = next_step.replace("PASS_TO_ANALYST_", "")
    logger.info(f"Extracted target analyst from next_step: {target_analyst}")
    
    # Store feedback in state for targeted analyst if available
    if target_analyst and feedback:
        if "feedback" not in state or state["feedback"] is None:
            state["feedback"] = {}
        state["feedback"][target_analyst] = feedback
        logger.info(f"Feedback for {target_analyst}: {feedback}")

        # Track retry attempts per analyst
        if "retry_attempts" not in state or state["retry_attempts"] is None:
            state["retry_attempts"] = {}
        current_attempts = state["retry_attempts"].get(target_analyst, 0) + 1
        state["retry_attempts"][target_analyst] = current_attempts
        logger.info(f"Retry attempts for {target_analyst}: {current_attempts}")

        # Check against max retries
        from src.config import MAX_RETRY_ATTEMPTS
        if current_attempts >= MAX_RETRY_ATTEMPTS:
            # Stop looping, accept last analyst score
            judgement["next_step"] = "PASS_TO_FINALIZE"
            state["judgement"] = judgement
            
            # Also update individual fields for backward compatibility
            state["judge_feedback"] = judgement["feedback"]
            state["next_step"] = judgement["next_step"]
            
            logger.info(f"Max retries reached for {target_analyst}. Accepting last score.")
```

## Implementation Steps

1. Update the `judge_analysis` function to handle the new multi-analyst revision case as shown above.

2. Modify the parser to handle the updated output schema:
   ```python
   # Define parser using Pydantic model for structured output
   parser = PydanticOutputParser(pydantic_object=JudgeOutput)
   ```

3. Update the JudgeOutput Pydantic model in state.py to match the new output schema:
   ```python
   class JudgeOutput(BaseModel):
       judgement: Dict[str, Any]  # Contains decision, feedback, next_step, and possibly analysts_needing_revision and feedback_by_analyst
   ```

## Considerations

- The updated code maintains backward compatibility by still supporting the single-analyst revision case.
- The multi-analyst revision case is handled by checking if the next_step is "MULTI_ANALYST_REVISION".
- We check if any analyst has reached the maximum number of retry attempts and remove them from the list.
- If all analysts have reached max retries, we pass to finalize.
- We set the current_revision_analyst to None, as it will be set by the revision_router.
- We need to ensure that the JudgeOutput Pydantic model in state.py is updated to match the new output schema.
