from app.services.workflow_compiler import available_workflows, compile_workflow


def _document() -> dict:
    return {
        "meta": {
            "product_name": "Acme", "host": "acme.test", "url": "https://acme.test/app",
        },
        "user_flows": {
            "reasoning": "Authentication and workspace surfaces were observed.",
            "flows": [{
                "name": "Primary activation flow",
                "steps": ["Land on site", "Sign up", "Create workspace", "Open dashboard"],
                "confidence": 76,
            }],
        },
        "api": {
            "endpoints": [
                {"method": "POST", "path": "/api/workspaces", "confidence": 91, "note": "Workspace creation request"},
                {"method": "GET", "path": "/api/issues", "confidence": 86, "note": "Issue list request"},
            ],
        },
        "architecture": {
            "request_flows": [{
                "name": "Activation request path", "confidence": 84, "classification": "observed",
                "evidence": ["POST /api/workspaces returned 201"],
            }],
            "unknowns": ["Worker scheduling is not directly observable."],
        },
    }


def test_lists_only_real_report_workflows() -> None:
    result = available_workflows(_document())
    assert result == [{
        "name": "Primary activation flow", "steps": 4, "confidence": 76,
        "classification": "inferred",
    }]
    assert available_workflows({"user_flows": {"flows": []}}) == []


def test_compiles_evidence_grounded_contract_and_playwright() -> None:
    result = compile_workflow(_document(), "Primary activation flow")
    contract = result["contract"]

    assert contract["version"] == "orbit.workflow.v1"
    assert contract["status"] == "review_required"
    assert [step["action"] for step in contract["steps"]] == [
        "Land on site", "Sign up", "Create workspace", "Open dashboard",
    ]
    assert contract["endpoints"][0]["path"] == "/api/workspaces"
    assert contract["evidence"]
    assert all(step["evidence_ids"] for step in contract["steps"])
    assert "page.goto('https://acme.test/app')" in result["playwright"]
    assert "waitForResponse" in result["playwright"]
    assert '"automation_readiness"' in result["contract_json"]


def test_unknown_workflow_is_rejected() -> None:
    try:
        compile_workflow(_document(), "Made up flow")
    except ValueError as error:
        assert "not available" in str(error)
    else:
        raise AssertionError("Expected unknown workflow to be rejected")


def test_recorder_backed_workflow_generates_selector_based_automation() -> None:
    document = _document()
    document["user_flows"] = {
        "reasoning": "Actions were observed in an authorized Recorder capture.",
        "flows": [{
            "name": "Create workspace",
            "steps": ["Open /app", "Click new workspace", "Fill workspace name (text value redacted)", "Press Enter"],
            "confidence": 96,
            "classification": "observed",
            "evidence": ["Authorized DevTools Recorder capture with 4 sanitized actions"],
            "capture_steps": [
                {"type": "navigate", "url": "https://acme.test/app"},
                {"type": "click", "selector": 'button[data-testid="new-workspace"]'},
                {"type": "change", "selector": 'input[name="workspace"]', "value_kind": "text"},
                {"type": "keyDown", "key": "Enter"},
            ],
        }],
    }

    result = compile_workflow(document, "Create workspace")
    contract = result["contract"]

    assert contract["status"] == "ready"
    assert contract["automation_readiness"] >= 80
    assert contract["steps"][1]["selector"] == 'button[data-testid="new-workspace"]'
    assert "page.locator('button[data-testid=\"new-workspace\"]')" in result["playwright"]
    assert "process.env.ORBIT_INPUT_TEXT" in result["playwright"]
    assert "page.keyboard.press('Enter')" in result["playwright"]
