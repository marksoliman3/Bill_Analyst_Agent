import pytest
from unittest.mock import patch
from src.state import AgentState
from src.agents.analysts import make_analyst_node
from src.agents.configs.analysts_config import ANALYST_DEFINITIONS


@pytest.mark.parametrize("analyst_key", list(ANALYST_DEFINITIONS.keys()))
def test_analyst_success(analyst_key):
    state: AgentState = {
        "bill_id": "B100",
        "bill_text": "An Act to regulate AI systems with safety, competition, and property rights provisions.",
    }

    mock_output = {
        "score": 2,
        "justification": f"Mocked justification for {analyst_key}",
    }

    with patch("src.agents.analysts.ChatOpenAI.invoke", return_value=mock_output):
        analyst_fn = make_analyst_node(analyst_key)
        state = analyst_fn(state)
        assert f"{analyst_key}_analysis" in state
        assert state[f"{analyst_key}_analysis"] == mock_output


@pytest.mark.parametrize("analyst_key", list(ANALYST_DEFINITIONS.keys()))
def test_analyst_no_text(analyst_key):
    state: AgentState = {"bill_id": "B101", "bill_text": ""}
    analyst_fn = make_analyst_node(analyst_key)
    state = analyst_fn(state)
    assert "error" in state[f"{analyst_key}_analysis"]


@pytest.mark.parametrize("analyst_key", list(ANALYST_DEFINITIONS.keys()))
def test_analyst_with_feedback(analyst_key):
    state: AgentState = {
        "bill_id": "B102",
        "bill_extracts": "Extracted spans about AI safety and competition.",
        "feedback": {analyst_key: "Revise your justification with more detail."},
    }

    mock_output = {
        "score": 1,
        "justification": f"Revised justification for {analyst_key}",
    }

    with patch("src.agents.analysts.ChatOpenAI.invoke", return_value=mock_output):
        analyst_fn = make_analyst_node(analyst_key)
        state = analyst_fn(state)
        assert f"{analyst_key}_analysis" in state
        assert state[f"{analyst_key}_analysis"] == mock_output
