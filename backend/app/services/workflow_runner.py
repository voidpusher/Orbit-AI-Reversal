"""Controlled browser replay for saved Orbit workflow contracts.

Sensitive inputs are accepted only for the lifetime of one call and are never
included in the returned result. The runner records redacted step outcomes and
proposes selector repairs, but it never mutates the saved contract automatically.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Mapping
from urllib.parse import urljoin, urlsplit

import httpx
from fastapi import HTTPException

from app.core.config import Settings
from app.services.url_policy import assert_public_resolution, normalize_public_url


def validate_workflow_contract(contract: Mapping) -> None:
    if contract.get("version") != "orbit.workflow.v1":
        raise ValueError("Unsupported workflow contract version")
    if not str(contract.get("id") or "").strip() or not str(contract.get("name") or "").strip():
        raise ValueError("Workflow contract identity is required")
    if not isinstance(contract.get("steps"), list) or not contract["steps"]:
        raise ValueError("Workflow contract must contain at least one step")
    if len(contract["steps"]) > 100:
        raise ValueError("Workflow contract exceeds the 100-step execution limit")


def required_inputs(contract: Mapping) -> list[str]:
    return sorted({
        str(step.get("input_kind") or "text")
        for step in contract.get("steps") or []
        if step.get("kind") == "input"
    })


def _safe_inputs(contract: Mapping, inputs: Mapping[str, str]) -> dict[str, str]:
    required = required_inputs(contract)
    missing = [key for key in required if not inputs.get(key)]
    if missing:
        raise ValueError(f"Runtime input required: {', '.join(missing)}")
    return {key: str(inputs[key])[:2000] for key in required}


def _same_origin_url(target_url: str, candidate: str) -> str:
    target = urlsplit(target_url)
    resolved = urljoin(target_url, candidate)
    parsed = urlsplit(resolved)
    if (parsed.scheme, parsed.hostname, parsed.port) != (target.scheme, target.hostname, target.port):
        raise ValueError("Workflow navigation cannot leave the captured target origin")
    return normalize_public_url(resolved)


def _quote_attribute(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


class WorkflowRunner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def run(self, contract: dict, inputs: Mapping[str, str]) -> dict:
        validate_workflow_contract(contract)
        try:
            safe_inputs = _safe_inputs(contract, inputs)
        except ValueError as error:
            return {
                "status": "blocked", "error_code": "runtime_input_required",
                "failure_step_id": None, "steps": [], "repair_proposal": None,
                "message": str(error),
            }

        target_url = normalize_public_url(str(contract.get("target_url") or ""), self._settings.allowed_analysis_hosts)
        await assert_public_resolution(target_url)

        if self._settings.browser_exploration:
            return await self._run_local(contract, target_url, safe_inputs)

        remote_url = self._remote_url()
        if remote_url and self._settings.capture_secret:
            return await self._run_remote(remote_url, contract, safe_inputs)
        return {
            "status": "blocked", "error_code": "replay_runtime_unavailable",
            "failure_step_id": None, "steps": [], "repair_proposal": None,
            "message": "A browser replay runtime is not configured for this deployment.",
        }

    def _remote_url(self) -> str | None:
        configured = getattr(self._settings, "workflow_replay_url", None)
        if configured:
            return configured
        if self._settings.browser_capture_url:
            return self._settings.browser_capture_url.replace("/browser-capture", "/workflow-replay")
        if os.getenv("VERCEL"):
            return f"{self._settings.public_base_url.rstrip('/')}/api/workflow-replay"
        return None

    async def _run_remote(self, url: str, contract: dict, inputs: dict[str, str]) -> dict:
        timeout = httpx.Timeout(100, connect=20)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                url,
                headers={"x-orbit-capture-secret": self._settings.capture_secret or ""},
                json={"contract": contract, "inputs": inputs},
            )
            response.raise_for_status()
            return dict(response.json())

    async def _run_local(self, contract: dict, target_url: str, inputs: dict[str, str]) -> dict:
        from playwright.async_api import async_playwright

        started = time.perf_counter()
        step_results: list[dict] = []
        failure_step_id: str | None = None
        error_code: str | None = None
        repair: dict | None = None
        checked_hosts: set[str] = set()

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(viewport={"width": 1440, "height": 900})

            async def guard(route) -> None:
                try:
                    request_url = normalize_public_url(route.request.url)
                    host = urlsplit(request_url).hostname or ""
                    if host not in checked_hosts:
                        await assert_public_resolution(request_url)
                        checked_hosts.add(host)
                    await route.continue_()
                except Exception:
                    await route.abort("blockedbyclient")

            await context.route("**/*", guard)
            page = await context.new_page()
            try:
                for step in contract.get("steps") or []:
                    step_started = time.perf_counter()
                    step_id = str(step.get("id") or f"step-{len(step_results) + 1}")
                    try:
                        await self._execute_step(page, target_url, step, inputs)
                        step_results.append({
                            "step_id": step_id, "action": str(step.get("action") or "Action"),
                            "status": "passed", "duration_ms": round((time.perf_counter() - step_started) * 1000),
                        })
                    except Exception as error:
                        failure_step_id = step_id
                        error_code = "selector_not_found" if step.get("selector") else "step_failed"
                        if step.get("selector"):
                            repair = await self._repair_proposal(page, step)
                        step_results.append({
                            "step_id": step_id, "action": str(step.get("action") or "Action"),
                            "status": "failed", "duration_ms": round((time.perf_counter() - step_started) * 1000),
                            "error_code": error_code, "message": type(error).__name__,
                        })
                        break
            finally:
                await context.close()
                await browser.close()

        return {
            "status": "failed" if failure_step_id else "passed",
            "error_code": error_code,
            "failure_step_id": failure_step_id,
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "steps": step_results,
            "repair_proposal": repair,
            "message": "Replay completed" if not failure_step_id else "Replay stopped at the first failed step",
        }

    async def _execute_step(self, page, target_url: str, step: Mapping, inputs: Mapping[str, str]) -> None:
        kind = str(step.get("kind") or "interaction")
        selector = str(step.get("selector") or "").strip()
        action = str(step.get("action") or "Action")
        if kind == "navigate":
            url = _same_origin_url(target_url, str(step.get("url") or target_url))
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        elif kind == "input":
            await page.locator(selector).first.fill(inputs[str(step.get("input_kind") or "text")], timeout=10_000)
        elif kind == "keyboard":
            await page.keyboard.press(str(step.get("key") or "Enter"))
        elif kind == "scroll":
            await page.mouse.wheel(0, 600)
        elif kind == "assertion":
            locator = page.locator(selector).first if selector else page.get_by_text(action, exact=False).first
            await locator.wait_for(state="visible", timeout=10_000)
        else:
            if selector:
                await page.locator(selector).first.click(timeout=10_000)
            else:
                await page.get_by_role("button", name=action, exact=False).or_(
                    page.get_by_role("link", name=action, exact=False)
                ).first.click(timeout=10_000)

    async def _repair_proposal(self, page, step: Mapping) -> dict | None:
        action_terms = [term.lower() for term in str(step.get("action") or "").split() if len(term) > 2]
        candidates = await page.locator("button, a, input, [role='button']").evaluate_all(
            """elements => elements.slice(0, 250).map(el => ({
              testid: el.getAttribute('data-testid'), id: el.id || null,
              name: el.getAttribute('name'), aria: el.getAttribute('aria-label'),
              text: (el.textContent || '').trim().slice(0, 120)
            }))"""
        )
        for candidate in candidates:
            haystack = " ".join(str(candidate.get(key) or "") for key in ("testid", "id", "name", "aria", "text")).lower()
            if action_terms and not any(term in haystack for term in action_terms):
                continue
            selector = None
            reason = None
            if candidate.get("testid"):
                selector, reason = f'[data-testid="{_quote_attribute(candidate["testid"])}"]', "unique data-testid matched the action"
            elif candidate.get("id") and re.fullmatch(r"[A-Za-z][\w-]*", str(candidate["id"])):
                selector, reason = f'#{candidate["id"]}', "element id matched the action"
            elif candidate.get("name"):
                selector, reason = f'[name="{_quote_attribute(candidate["name"])}"]', "element name matched the action"
            elif candidate.get("aria"):
                selector, reason = f'[aria-label="{_quote_attribute(candidate["aria"])}"]', "accessible label matched the action"
            if selector and await page.locator(selector).count() == 1:
                return {
                    "step_id": str(step.get("id") or ""), "old_selector": str(step.get("selector") or ""),
                    "proposed_selector": selector, "confidence": 82, "reason": reason,
                    "requires_approval": True,
                }
        return None


def blocked_result_from_exception(error: Exception) -> dict:
    if isinstance(error, (ValueError, HTTPException)):
        message = str(getattr(error, "detail", error))
        code = "contract_invalid"
    else:
        message = "The replay runtime failed before the workflow completed."
        code = "replay_runtime_failed"
    return {
        "status": "blocked", "error_code": code, "failure_step_id": None,
        "steps": [], "repair_proposal": None, "message": message,
    }
