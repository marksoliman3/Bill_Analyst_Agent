# Implementation Details for src/agents/configs/analysts_config.py

## Current Implementation

The current `analysts_config.py` file defines the configuration for the analyst agents, including their personas, scopes, task instructions, revision instructions, and output schemas. The key components are:

1. The `SCORING_RUBRIC` shared by all analysts
2. The `OUTPUT_SCHEMA` defining the expected output format
3. The `ANALYST_DEFINITIONS` dictionary containing the configuration for each analyst

Currently, the revision instructions are designed for a single revision:

```python
"revision_instructions": (
    "Your previous analysis was reviewed and requires revision. "
    "**Carefully consider the following feedback from the judge: '{feedback}'.** "
    "Re-evaluate the bill extracts in light of this feedback and provide an updated response. "
    "Your new response must still follow all original instructions: "
    "First, reason through how the text relates to your specific scope. "
    "Then, using the provided scoring rubric, assign an updated score. "
    "Finally, provide a brief but clear justification for your new score, citing specific elements from the text. "
    "Your output must be a valid JSON object."
),
```

## Proposed Changes

After careful consideration and based on user feedback, **no changes are needed to the `analysts_config.py` file** for the multi-analyst revision process. The current revision instructions are already designed to handle feedback from the judge, and they don't need to be aware of whether they're part of a single-analyst or multi-analyst revision.

The existing revision instructions are sufficient:

```python
"revision_instructions": (
    "Your previous analysis was reviewed and requires revision. "
    "**Carefully consider the following feedback from the judge: '{feedback}'.** "
    "Re-evaluate the bill extracts in light of this feedback and provide an updated response. "
    "Your new response must still follow all original instructions: "
    "First, reason through how the text relates to your specific scope. "
    "Then, using the provided scoring rubric, assign an updated score. "
    "Finally, provide a brief but clear justification for your new score, citing specific elements from the text. "
    "Your output must be a valid JSON object."
),
```

## Implementation Steps

**No implementation steps are needed for `analysts_config.py`.**

The existing configuration is sufficient for the multi-analyst revision process:

1. No changes are needed to the `revision_instructions` for any analyst in the `ANALYST_DEFINITIONS` dictionary.
2. No changes are needed to the `SCORING_RUBRIC` or `OUTPUT_SCHEMA`.

## Considerations

- The current instructions already work for both single-analyst and multi-analyst revision without any changes.
- The analysts don't need to be aware of the other analysts being revised, as each analyst is still responsible for their own scope and score.
- The multi-analyst revision process is handled by the judge, revision router, and graph, not by the analysts themselves.
- Keeping the analyst configuration unchanged maintains simplicity and reduces the risk of introducing bugs.
