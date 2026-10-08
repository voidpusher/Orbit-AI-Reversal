"""Tenant-scoped encryption helpers for workflow runtime secrets.

Vault values are encrypted with AES-256-GCM. The organization, workflow, entry
name, and key version are authenticated as AAD so ciphertext cannot be copied
between tenants or records without decryption failing.
"""

from __future__ import annotations

import base64
import os
from datetime import datetime, timezone

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import WorkflowSecret


class VaultUnavailableError(RuntimeError):
    pass


class VaultIntegrityError(RuntimeError):
    pass


class WorkflowVault:
    key_version = "v1"

    def __init__(self, settings: Settings) -> None:
        encoded = (settings.vault_key or "").strip()
        if not encoded:
            raise VaultUnavailableError("The workflow credential vault is not configured")
        try:
            padded = encoded + "=" * (-len(encoded) % 4)
            key = base64.urlsafe_b64decode(padded.encode())
        except Exception as error:
            raise VaultUnavailableError("The workflow vault key is malformed") from error
        if len(key) != 32:
            raise VaultUnavailableError("The workflow vault key must decode to exactly 32 bytes")
        self._cipher = AESGCM(key)

    @staticmethod
    def available(settings: Settings) -> bool:
        try:
            WorkflowVault(settings)
            return True
        except VaultUnavailableError:
            return False

    def _aad(self, organization_id: str, workflow_id: str, name: str) -> bytes:
        return f"orbit:{self.key_version}:{organization_id}:{workflow_id}:{name}".encode()

    def encrypt(self, organization_id: str, workflow_id: str, name: str, value: str) -> tuple[str, str]:
        nonce = os.urandom(12)
        ciphertext = self._cipher.encrypt(
            nonce, value.encode(), self._aad(organization_id, workflow_id, name)
        )
        return (
            base64.urlsafe_b64encode(ciphertext).decode(),
            base64.urlsafe_b64encode(nonce).decode(),
        )

    def decrypt(self, entry: WorkflowSecret) -> str:
        try:
            ciphertext = base64.urlsafe_b64decode(entry.ciphertext.encode())
            nonce = base64.urlsafe_b64decode(entry.nonce.encode())
            plaintext = self._cipher.decrypt(
                nonce,
                ciphertext,
                self._aad(entry.organization_id, entry.workflow_id, entry.name),
            )
            return plaintext.decode()
        except (InvalidTag, ValueError, UnicodeDecodeError) as error:
            raise VaultIntegrityError("A workflow vault entry failed integrity verification") from error


async def upsert_secret(
    session: AsyncSession,
    vault: WorkflowVault,
    *,
    organization_id: str,
    workflow_id: str,
    name: str,
    value: str,
) -> WorkflowSecret:
    ciphertext, nonce = vault.encrypt(organization_id, workflow_id, name, value)
    entry = await session.scalar(select(WorkflowSecret).where(
        WorkflowSecret.organization_id == organization_id,
        WorkflowSecret.workflow_id == workflow_id,
        WorkflowSecret.name == name,
    ))
    if entry is None:
        entry = WorkflowSecret(
            organization_id=organization_id,
            workflow_id=workflow_id,
            name=name,
            ciphertext=ciphertext,
            nonce=nonce,
            key_version=vault.key_version,
        )
        session.add(entry)
    else:
        entry.ciphertext = ciphertext
        entry.nonce = nonce
        entry.key_version = vault.key_version
        entry.updated_at = datetime.now(timezone.utc)
    return entry


async def load_secrets(
    session: AsyncSession,
    vault: WorkflowVault,
    *,
    organization_id: str,
    workflow_id: str,
) -> dict[str, str]:
    entries = list((await session.scalars(select(WorkflowSecret).where(
        WorkflowSecret.organization_id == organization_id,
        WorkflowSecret.workflow_id == workflow_id,
    ))).all())
    return {entry.name: vault.decrypt(entry) for entry in entries}


async def list_secret_entries(
    session: AsyncSession, *, organization_id: str, workflow_id: str
) -> list[WorkflowSecret]:
    return list((await session.scalars(select(WorkflowSecret).where(
        WorkflowSecret.organization_id == organization_id,
        WorkflowSecret.workflow_id == workflow_id,
    ).order_by(WorkflowSecret.name))).all())
