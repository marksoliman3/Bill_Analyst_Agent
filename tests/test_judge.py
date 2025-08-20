import pytest
from unittest.mock import patch
from src.state import AgentState
from src.agents.judge import judge_analysis


@pytest.fixture
def sample_state():
    return {
        "bill_id": "B200",
        "bill_text": "An Act to regulate AI systems.",
        "market_structure_analysis": {"score": 2, "justification": "Mocked"},
    }


def test_judge_success(sample_state):
    mock_output = {
        "decision": "AGREE",
        "feedback": None,
        "next_step": "PASS_TO_FINALIZE",
    }

    with patch("src.agents.judge.ChatOpenAI.invoke", return_value=mock_output):
        state = judge_analysis(sample_state)
        assert "judgement" in state
        assert state["judgement"] == mock_output


def test_judge_no_analyst_outputs():
    state: AgentState = {"bill_id": "B201", "bill_text": "Some bill text"}
    state = judge_analysis(state)
    assert "judgement" in state
    assert state["judgement"]["next_step"] == "FAIL_BILL"


def test_judge_feedback_routing(sample_state):
    mock_output = {
        "decision": "DISAGREE",
        "feedback": "Needs more detail on market impact.",
        "next_step": "PASS_TO_ANALYST",
        "target_analyst": "market_structure",
    }

    with patch("src.agents.judge.ChatOpenAI.invoke", return_value=mock_output):
        state = judge_analysis(sample_state)
        assert "judgement" in state
        assert state["judgement"]["feedback"] == "Needs more detail on market impact."
        assert "feedback" in state
        assert (
            state["feedback"]["market_structure"]
            == "Needs more detail on market impact."
        )
