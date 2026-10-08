import pytest

from app.core.config import Settings
from app.services.workflow_runner import WorkflowRunner, _same_origin_url, required_inputs, validate_workflow_contract


def _contract() -> dict:
    return {
        "version": "orbit.workflow.v1",
        "id": "acme.login",
        "name": "Login",
        "target_url": "https://acme.example/login",
        "steps": [
            {"id": "step-1", "kind": "navigate", "action": "Open login"},
            {"id": "step-2", "kind": "input", "action": "Enter email", "selector": "#email", "input_kind": "email"},
        ],
    }


def test_contract_validation_and_required_inputs() -> None:
    validate_workflow_contract(_contract())
    assert required_inputs(_contract()) == ["email"]
    with pytest.raises(ValueError, match="version"):
        validate_workflow_contract({**_contract(), "version": "unknown"})


def test_navigation_is_confined_to_captured_origin() -> None:
    assert _same_origin_url("https://acme.example/app", "/settings") == "https://acme.example/settings"
    with pytest.raises(ValueError, match="cannot leave"):
        _same_origin_url("https://acme.example/app", "https://attacker.example/")


def test_missing_runtime_input_blocks_before_browser_or_network() -> None:
    runner = WorkflowRunner(Settings(browser_exploration=False, database_url="sqlite+aiosqlite:///:memory:"))
    # The missing-input branch completes before the coroutine performs any I/O.
    with pytest.raises(StopIteration) as completed:
        runner.run(_contract(), {}).send(None)
    outcome = completed.value.value
    assert outcome["status"] == "blocked"
    assert outcome["error_code"] == "runtime_input_required"
    assert "email" in outcome["message"]
    assert "inputs" not in outcome
