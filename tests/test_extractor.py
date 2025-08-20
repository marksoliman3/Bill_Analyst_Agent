import pytest
from unittest.mock import patch
from src.state import AgentState
from src.agents.extractor import extract_bill_text


@pytest.fixture
def sample_state():
    return {
        "bill_id": "B001",
        "bill_text": "An Act to regulate AI systems.\n\nSection 1: Definitions.\n\nSection 2: Enforcement.",
    }


def test_extractor_success(sample_state):
    mock_output = {"extracted_text": "Relevant sections here."}

    with patch("src.agents.extractor.ChatOpenAI.invoke", return_value=mock_output):
        state = extract_bill_text(sample_state)
        assert "extracted" in state
        assert state["extracted"] == mock_output


def test_extractor_no_text():
    state: AgentState = {"bill_id": "B002", "bill_text": ""}
    state = extract_bill_text(state)
    assert "error" in state["extracted"]
