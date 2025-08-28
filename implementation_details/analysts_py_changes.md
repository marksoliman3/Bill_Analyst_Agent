# Implementation Details for src/agents/analysts.py

## Current Implementation

The current `analysts.py` file defines the analyst subgraphs, which take the extracted bill text as input and produce a JSON-like analysis output (score + justification). The key function is `make_analyst_node`, which creates an analyst node function based on its configuration. Currently, it handles feedback for a single analyst:

```python
# Choose instructions: revision or task
if state.get("feedback") and analyst_key in state["feedback"]:
    instructions = (
        config["revision_instructions"].format(
            feedback=state["feedback"][analyst_key]
        )
        + "\n"
        + config["scoring_rubric"]
    )
else:
    instructions = config["task_instructions"] + "\n" + config["scoring_rubric"]
```

## Proposed Changes

We need to update the `make_analyst_node` function to be aware of the multi-analyst revision process:

1. Check if the analyst is the current revision analyst
2. If so, use the revision instructions with the feedback for this analyst
3. Ensure the analyst updates its results in a way that preserves other analysts' work

Here's the updated code:

```python
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
        if state.get("analysts_needing_revision") and state.get("current_revision_analyst") == analyst_key:
            logger.info(f"[ANALYST:{analyst_key}] This is part of a multi-analyst revision")
            is_revision = True

        bill_extracts = state.get("bill_extracts", "")
        if not bill_extracts:
            logger.warning(
                f"[ANALYST:{analyst_key}] No bill_extracts found in state for bill {bill_id}"
            )
            state[f"{analyst_key}_analysis"] = {"error": "No bill extracts provided"}
            return state

        logger.info(
            f"[ANALYST:{analyst_key}] Processing bill {bill_id} with {len(bill_extracts)} characters"
        )

        # Choose instructions: revision or task
        if state.get("feedback") and analyst_key in state["feedback"]:
            instructions = (
                config["revision_instructions"].format(
                    feedback=state["feedback"][analyst_key]
                )
                + "\n"
                + config["scoring_rubric"]
            )
            logger.info(f"[ANALYST:{analyst_key}] Using revision instructions with feedback")
        else:
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

        # Define parser
        parser = JsonOutputParser()

        # Build chain
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        chain = prompt | llm | parser

        try:
            logger.info(f"[ANALYST:{analyst_key}] Calling LLM for bill {bill_id}")
            result = chain.invoke({"bill_extracts": bill_extracts})
            logger.info(
                f"[ANALYST:{analyst_key}] LLM call completed for bill {bill_id}"
            )

            # Initialize analyst_results if it doesn't exist
            if "analyst_results" not in state:
                state["analyst_results"] = {}
            # Add this analyst's result to the analyst_results dictionary
            state["analyst_results"][analyst_key] = result
            # Keep the old field for backward compatibility
            state[f"{analyst_key}_analysis"] = result

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
            state["analyst_results"][analyst_key] = {"error": str(e)}
            state[f"{analyst_key}_analysis"] = {"error": str(e)}
            logger.error(
                f"[ANALYST:{analyst_key}] State update: {analyst_key}_analysis -> error {e}"
            )

        logger.info(f"[ANALYST:{analyst_key}] Completed analysis for bill {bill_id}")
        return state

    return analyst_fn
```

## Implementation Steps

1. Update the `make_analyst_node` function to check if the analyst is part of a multi-analyst revision:
   ```python
   # Check if this is part of a multi-analyst revision
   is_revision = False
   if state.get("analysts_needing_revision") and state.get("current_revision_analyst") == analyst_key:
       logger.info(f"[ANALYST:{analyst_key}] This is part of a multi-analyst revision")
       is_revision = True
   ```

2. Add logging to indicate when an analyst is part of a multi-analyst revision:
   ```python
   # If this is part of a multi-analyst revision, log that the revision is complete
   if is_revision:
       logger.info(f"[ANALYST:{analyst_key}] Completed revision as part of multi-analyst revision")
   ```

3. No changes are needed to the `build_analyst_subgraph` function or the `ANALYST_SUBGRAPHS` dictionary.

## Considerations

- The updated code maintains backward compatibility by still supporting the single-analyst revision case.
- The multi-analyst revision case is handled by checking if the analyst is the current revision analyst.
- We add logging to indicate when an analyst is part of a multi-analyst revision, which will be helpful for debugging.
- No changes are needed to the way analysts update their results, as they already update only their own entry in the analyst_results dictionary.
