import pytest
from unittest.mock import patch
from src.state import AgentState
from src.agents.summarizer import summarize_bill_text


@pytest.fixture
def sample_state():
    return {
        "bill_id": "B010",
        "bill_text": "An Act to promote AI safety.\n\nSection 1: Oversight.\n\nSection 2: Enforcement.",
    }


def test_summarizer_success(sample_state):
    mock_output = {
        "summary": "This bill promotes AI safety through oversight and enforcement."
    }

    with patch("src.agents.summarizer.ChatOpenAI.invoke", return_value=mock_output):
        state = summarize_bill_text(sample_state)
        assert "summary" in state
        assert state["summary"] == mock_output["summary"]


def test_summarizer_no_text():
    state: AgentState = {"bill_id": "B011", "bill_text": ""}
    state = summarize_bill_text(state)
    assert "No bill text provided" in state["summary"] or "Error" in state["summary"]
