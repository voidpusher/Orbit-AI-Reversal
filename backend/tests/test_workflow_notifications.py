import pytest

from app.services.workflow_notifications import validate_alert_email, validate_slack_webhook


@pytest.mark.parametrize(
    "url",
    [
        "https://hooks.slack.com/services/T000/B000/token",
        "https://hooks.slack-gov.com/services/T000/B000/token",
    ],
)
def test_slack_webhook_allows_only_official_hosts(url: str) -> None:
    assert validate_slack_webhook(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "http://hooks.slack.com/services/T000/B000/token",
        "https://hooks.slack.com.attacker.example/services/token",
        "https://hooks.slack.com/not-services/token",
        "https://127.0.0.1/services/token",
    ],
)
def test_slack_webhook_rejects_spoofed_or_internal_destinations(url: str) -> None:
    with pytest.raises(ValueError):
        validate_slack_webhook(url)


def test_alert_email_is_normalized_without_exposing_other_values() -> None:
    assert validate_alert_email(" Alerts@Example.com ") == "alerts@example.com"
    with pytest.raises(ValueError):
        validate_alert_email("not-an-email")
