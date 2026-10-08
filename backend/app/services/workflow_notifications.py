"""Failure notifications for workflow replays.

Delivery payloads are intentionally sparse: workflow identity, run status,
failure step, and error code. Runtime inputs, selectors, target content, and
vault values are never included.
"""

from __future__ import annotations

from html import escape
from urllib.parse import urlsplit

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.services.vault import WorkflowVault, load_secrets

_SLACK_HOSTS = {"hooks.slack.com", "hooks.slack-gov.com"}


def validate_slack_webhook(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in _SLACK_HOSTS:
        raise ValueError("Slack webhook must use an official hooks.slack.com HTTPS URL")
    if not parsed.path.startswith("/services/"):
        raise ValueError("Slack webhook path is invalid")
    return value.strip()


def validate_alert_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 320 or email.count("@") != 1:
        raise ValueError("A valid alert email is required")
    local, domain = email.rsplit("@", 1)
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise ValueError("A valid alert email is required")
    return email


class WorkflowNotifier:
    def __init__(self, settings: Settings, factory: async_sessionmaker[AsyncSession]) -> None:
        self._settings = settings
        self._factory = factory

    async def notify_failure(
        self,
        *,
        workflow_id: str,
        organization_id: str,
        workflow_name: str,
        report_id: str,
        outcome: dict,
    ) -> list[dict[str, str]]:
        if outcome.get("status") not in {"failed", "blocked"}:
            return []
        try:
            vault = WorkflowVault(self._settings)
            async with self._factory() as session:
                secrets = await load_secrets(
                    session, vault, organization_id=organization_id, workflow_id=workflow_id
                )
        except Exception:
            return [{"channel": "vault", "status": "skipped", "error_code": "vault_unavailable"}]

        status = str(outcome.get("status") or "failed")
        failure_step = str(outcome.get("failure_step_id") or "not reported")
        error_code = str(outcome.get("error_code") or "workflow_failed")
        report_url = f"{self._settings.frontend_base_url.rstrip('/')}/report/{report_id}"
        text = (
            f"Orbit workflow alert: {workflow_name}\n"
            f"Status: {status}\nFailure step: {failure_step}\n"
            f"Error: {error_code}\nReport: {report_url}"
        )
        deliveries: list[dict[str, str]] = []
        timeout = httpx.Timeout(10, connect=5)
        async with httpx.AsyncClient(timeout=timeout) as client:
            slack_url = secrets.get("notification.slack_webhook")
            if slack_url:
                try:
                    validate_slack_webhook(slack_url)
                    response = await client.post(slack_url, json={"text": text})
                    response.raise_for_status()
                    deliveries.append({"channel": "slack", "status": "sent"})
                except Exception:
                    deliveries.append({
                        "channel": "slack", "status": "failed", "error_code": "delivery_failed"
                    })

            email = secrets.get("notification.email")
            if email:
                if not self._settings.resend_api_key or not self._settings.notification_from_email:
                    deliveries.append({
                        "channel": "email", "status": "skipped", "error_code": "provider_unavailable"
                    })
                else:
                    try:
                        response = await client.post(
                            "https://api.resend.com/emails",
                            headers={"Authorization": f"Bearer {self._settings.resend_api_key}"},
                            json={
                                "from": self._settings.notification_from_email,
                                "to": [validate_alert_email(email)],
                                "subject": f"Orbit alert: {workflow_name} {status}",
                                "html": (
                                    f"<h2>Workflow {escape(status)}</h2>"
                                    f"<p><strong>{escape(workflow_name)}</strong></p>"
                                    f"<p>Failure step: {escape(failure_step)}<br>"
                                    f"Error: {escape(error_code)}</p>"
                                    f'<p><a href="{escape(report_url)}">Open report</a></p>'
                                ),
                            },
                        )
                        response.raise_for_status()
                        deliveries.append({"channel": "email", "status": "sent"})
                    except Exception:
                        deliveries.append({
                            "channel": "email", "status": "failed", "error_code": "delivery_failed"
                        })
        return deliveries
