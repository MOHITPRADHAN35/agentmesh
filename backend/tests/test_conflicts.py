import pytest
from app.services.llm_provider import MockDeterministicProvider

def test_mock_contradiction_detection():
    provider = MockDeterministicProvider()
    
    existing = [
        {"id": "mem_1", "content": "We decided to use PostgreSQL for our database."},
        {"id": "mem_2", "content": "FastAPI runs on port 8000."}
    ]
    
    # Incompatible claim
    new_claim = "We switched to MongoDB for our database."
    conflict = provider.evaluate_contradiction(new_claim, existing)
    
    assert conflict is not None
    assert conflict["conflicting_memory_id"] == "mem_1"
    assert "conflict detected" in conflict["explanation"].lower()

def test_no_contradiction_for_complementary_facts():
    provider = MockDeterministicProvider()
    
    existing = [
        {"id": "mem_1", "content": "We decided to use PostgreSQL for our database."}
    ]
    
    new_claim = "Frontend will be styled with CSS."
    conflict = provider.evaluate_contradiction(new_claim, existing)
    
    assert conflict is None

def test_mock_task_planning():
    provider = MockDeterministicProvider()
    msg = "We need to build the Docker image and deploy to cloud."
    tasks = provider.plan_tasks(msg, [])
    assert len(tasks) == 1
    assert "Action:" in tasks[0]["title"]
