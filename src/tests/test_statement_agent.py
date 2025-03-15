import pytest
from pathlib import Path
from src.agents.statement_ingestion_agent import StatementIngestionAgent
from src.schemas.statement_parser import StatementResponse

def test_agent_initialization():
    """Test that the agent can be initialized."""
    agent = StatementIngestionAgent()
    assert agent is not None
    assert agent.model is not None
    assert agent.fallback_model is not None
    assert agent.output_parser is not None

@pytest.mark.skip(reason="Requires actual PDF file")
def test_process_statement():
    """Test processing a single statement."""
    agent = StatementIngestionAgent()
    pdf_path = Path("tests/data/sample_statement.pdf")
    
    response = agent.process_statement(pdf_path)
    assert isinstance(response, StatementResponse)
    assert response.status == "success"
    assert response.data is not None
    assert response.error is None

@pytest.mark.skip(reason="Requires actual directory with PDFs")
def test_process_directory():
    """Test processing a directory of statements."""
    agent = StatementIngestionAgent()
    results = agent.process_directory(
        company="IT DevOps LLC",
        account_number="000000954291944",
        year="2023"
    )
    
    assert isinstance(results, list)
    assert len(results) > 0
    for result in results:
        assert "filename" in result
        assert "status" in result
        assert "message" in result 