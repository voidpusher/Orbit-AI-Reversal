from app.schemas import WorkflowStepRequest
from app.services.analyzer import AnalysisInputs, infer_user_flows
from app.services.workflow_import import build_workflow_evidence


def test_workflow_evidence_preserves_actions_without_values_or_query_strings() -> None:
    evidence = build_workflow_evidence(
        "analysis-1",
        "https://app.example.com/workspace",
        "Create project",
        [
            WorkflowStepRequest(type="navigate", url="https://app.example.com/workspaces/123456?token=secret"),
            WorkflowStepRequest(type="click", selector='button[data-testid="new-project"]'),
            WorkflowStepRequest(type="change", selector='input[name="title"]', value_kind="text", value_length=24),
            WorkflowStepRequest(type="keyDown", key="Enter"),
        ],
    )

    assert evidence.kind == "workflow_capture"
    assert evidence.redaction_version == "workflow-v1"
    assert evidence.metadata_json["step_count"] == 4
    assert evidence.metadata_json["steps"][0]["url"] == "https://app.example.com/workspaces/:id"
    assert "secret" not in str(evidence.metadata_json)
    assert evidence.metadata_json["steps"][2]["value_kind"] == "text"
    assert "value" not in evidence.metadata_json["steps"][2]


def test_recorded_workflow_becomes_observed_report_journey() -> None:
    inputs = AnalysisInputs(
        product_name="Example",
        host="app.example.com",
        url="https://app.example.com/workspace",
        workflow_captures=[{
            "title": "Create project",
            "steps": [
                {"id": "capture-1", "type": "navigate", "url": "https://app.example.com/workspace"},
                {"id": "capture-2", "type": "click", "selector": 'button[data-testid="new-project"]'},
                {"id": "capture-3", "type": "change", "selector": 'input[name="title"]', "value_kind": "text"},
            ],
        }],
    )

    result = infer_user_flows(inputs, [])
    flow = result["flows"][0]
    assert flow["name"] == "Create project"
    assert flow["classification"] == "observed"
    assert flow["capture_steps"][1]["selector"] == 'button[data-testid="new-project"]'
    assert "value redacted" in flow["steps"][2]
