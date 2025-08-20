import pytest
from unittest.mock import patch
from src.state import AgentState
from src.graph import build_full_graph


@pytest.fixture
def sample_state():
    return {
        "bill_id": "B300",
        "bill_text": "An Act to regulate AI systems with multiple provisions.",
    }


def test_full_graph_execution(sample_state):
    # Mock all LLM calls to return predictable outputs
    with patch(
        "src.agents.extractor.ChatOpenAI.invoke",
        return_value={"extracted_text": "Mocked extract"},
    ), patch(
        "src.agents.summarizer.ChatOpenAI.invoke",
        return_value={"summary": "Mocked summary"},
    ), patch(
        "src.agents.analysts.ChatOpenAI.invoke",
        return_value={"score": 2, "justification": "Mocked justification"},
    ), patch(
        "src.agents.judge.ChatOpenAI.invoke",
        return_value={
            "decision": "AGREE",
            "feedback": None,
            "next_step": "PASS_TO_FINALIZE",
        },
    ):

        graph = build_full_graph().compile()
        final_state = graph.invoke(sample_state)

        assert "consolidated_report" in final_state
        assert "summary" in final_state
        assert "extracted" in final_state or "extracted_text" in final_state.get(
            "consolidated_report", {}
        )
        assert "judgement" in final_state
