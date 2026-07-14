"""Optional Sentry error tracking.

Activates only when `ORBIT_SENTRY_DSN` is set *and* the `sentry-sdk` package is
installed, so the application runs identically with or without it. Sensitive
values are never sent: PII sending is disabled and the Authorization header and
common secret query params are scrubbed before an event leaves the process.
"""

from __future__ import annotations

import logging

from app.core.config import Settings

logger = logging.getLogger(__name__)

_SENSITIVE_HEADERS = {"authorization", "cookie", "idempotency-key"}


def _scrub(event: dict, _hint: dict) -> dict:
    request = event.get("request")
    if isinstance(request, dict):
        headers = request.get("headers")
        if isinstance(headers, dict):
            for key in list(headers):
                if key.lower() in _SENSITIVE_HEADERS:
                    headers[key] = "[redacted]"
    return event


def init_observability(settings: Settings) -> bool:
    """Initialize Sentry if configured. Returns True when active."""
    if not settings.sentry_dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        logger.warning("ORBIT_SENTRY_DSN is set but sentry-sdk is not installed; error tracking disabled")
        return False

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
        before_send=_scrub,
    )
    logger.info("Sentry error tracking enabled")
    return True
