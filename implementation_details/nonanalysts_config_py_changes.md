# Implementation Details for src/agents/configs/nonanalysts_config.py

## Current Implementation

The current `nonanalysts_config.py` file defines the configuration for the non-analyst agents, including the Judge. The Judge's task instructions and output schema are currently designed to handle only one analyst at a time for revision:

```python
"judge": {
    "name": "Judicial Review Agent",
    "persona": (
        "You are a meticulous and impartial senior legislative analyst. Your role is "
        "to act as a quality control checkpoint and a router. You ensure that analysis "
        "is accurate and you direct the workflow based on your findings."
    ),
    "task_instructions": (
        "You will be given the extracted text of a bill, the official scoring rubric, "
        "and the specific scope, score, and justification from a single analyst. "
        "You will also be told how many times this analyst has attempted this task. "
        "Your task is to perform the following steps:\n"
        "1. Compare the analyst's work against the bill text, their assigned scope, and the rubric.\n"
        "2. Decide if you 'AGREE' or if it requires 'REVISION'.\n"
        "3. If it requires 'REVISION' and the analyst has attempts remaining (less than 3), "
        "provide concise, actionable feedback for them to improve.\n"
        "4. Based on your decision and the attempt number, determine the next step for the workflow: "
        "'PASS_TO_ANALYST_[analyst_name]' for revision (where [analyst_name] is the specific analyst that needs to revise their work), "
        "'PASS_TO_FINALIZE' if the score is good, or 'FAIL_BILL' if the analyst has failed their final attempt.\n"
        "5. If your decision is 'REVISION', you MUST specify which analyst needs to revise their work by setting "
        "next_step to 'PASS_TO_ANALYST_[analyst_name]' (e.g., 'PASS_TO_ANALYST_market_structure'). "
        "This is critical for routing the bill to the correct analyst for revision.\n\n"
        "FOCUS ON NUMERIC SCORES: Your primary task is to judge ONLY the numeric relevance scores (0-3), "
        "NOT the justifications. ONLY send a bill back to an analyst if you disagree with their "
        "relevance score. If you agree with the score but think the justification could be improved, "
        "you MUST mark it as 'AGREE' and let it pass through. DO NOT provide feedback about improving "
        "justifications - focus EXCLUSIVELY on whether the numeric scores are correct.\n\n"
        "Your output must be a valid JSON object containing your decision, feedback, and the next routing step."
    ),
    "output_schema": {
        "judgement": {
            "decision": "string (either 'AGREE' or 'REVISE')",
            "feedback": "string (provide only if decision is 'REVISE', otherwise null)",
            "next_step": "string (either 'PASS_TO_ANALYST_[analyst_name]', 'PASS_TO_FINALIZE', or 'FAIL_BILL')",
        }
    },
},
```

## Proposed Changes

We need to update the Judge's task instructions and output schema to support identifying multiple analysts needing revision:

1. Update the task instructions to explain how to identify multiple analysts needing revision
2. Modify the output schema to include a list of analysts needing revision

Here's the updated configuration:

```python
"judge": {
    "name": "Judicial Review Agent",
    "persona": (
        "You are a meticulous and impartial senior legislative analyst. Your role is "
        "to act as a quality control checkpoint and a router. You ensure that analysis "
        "is accurate and you direct the workflow based on your findings."
    ),
    "task_instructions": (
        "You will be given the extracted text of a bill and the outputs from multiple analysts, "
        "each with their own scope, score, and justification. You will also be told how many times "
        "each analyst has attempted this task. "
        "Your task is to perform the following steps:\n"
        "1. Compare each analyst's work against the bill text, their assigned scope, and the rubric.\n"
        "2. For each analyst, decide if you 'AGREE' or if it requires 'REVISION'.\n"
        "3. If any analyst requires 'REVISION' and has attempts remaining (less than 3), "
        "provide concise, actionable feedback for them to improve.\n"
        "4. Based on your decisions, determine the next step for the workflow:\n"
        "   - If NO analysts need revision, set next_step to 'PASS_TO_FINALIZE'.\n"
        "   - If ONE analyst needs revision, set next_step to 'PASS_TO_ANALYST_[analyst_name]' (e.g., 'PASS_TO_ANALYST_market_structure').\n"
        "   - If MULTIPLE analysts need revision, set next_step to 'MULTI_ANALYST_REVISION' and provide a list of analyst names in the 'analysts_needing_revision' field.\n"
        "   - If any analyst has failed their final attempt, set next_step to 'FAIL_BILL'.\n"
        "5. For each analyst requiring revision, provide specific feedback in the 'feedback_by_analyst' dictionary, keyed by analyst name.\n\n"
        "FOCUS ON NUMERIC SCORES: Your primary task is to judge ONLY the numeric relevance scores (0-3), "
        "NOT the justifications. ONLY send a bill back to an analyst if you disagree with their "
        "relevance score. If you agree with the score but think the justification could be improved, "
        "you MUST mark it as 'AGREE' and let it pass through. DO NOT provide feedback about improving "
        "justifications - focus EXCLUSIVELY on whether the numeric scores are correct.\n\n"
        "Your output must be a valid JSON object containing your decision, feedback, next_step, and if applicable, "
        "a list of analysts needing revision and feedback for each analyst."
    ),
    "output_schema": {
        "judgement": {
            "decision": "string (either 'AGREE' or 'REVISE')",
            "feedback": "string (provide only if decision is 'REVISE', otherwise null)",
            "next_step": "string (either 'PASS_TO_ANALYST_[analyst_name]', 'MULTI_ANALYST_REVISION', 'PASS_TO_FINALIZE', or 'FAIL_BILL')",
            "analysts_needing_revision": "list of strings (analyst names, only if next_step is 'MULTI_ANALYST_REVISION')",
            "feedback_by_analyst": "dictionary mapping analyst names to feedback strings (only for analysts needing revision)"
        }
    },
},
```

## Implementation Steps

1. Update the `task_instructions` for the Judge agent to include guidance on identifying multiple analysts needing revision and setting the appropriate `next_step` value.

2. Modify the `output_schema` to include the new fields:
   - `analysts_needing_revision`: A list of analyst names that need revision
   - `feedback_by_analyst`: A dictionary mapping analyst names to feedback strings

## Considerations

- The updated instructions maintain backward compatibility by still supporting the single-analyst revision case with `PASS_TO_ANALYST_[analyst_name]`.
- The new `MULTI_ANALYST_REVISION` next_step value signals that multiple analysts need revision.
- The `feedback_by_analyst` dictionary allows the Judge to provide specific feedback for each analyst needing revision.
- The instructions emphasize that the Judge should still focus on numeric scores, not justifications, to maintain consistency with the existing behavior.
