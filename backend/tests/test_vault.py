import base64

import pytest

from app.core.config import Settings
from app.models import WorkflowSecret
from app.services.vault import VaultIntegrityError, VaultUnavailableError, WorkflowVault


def _settings(key: bytes = b"k" * 32) -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        vault_key=base64.urlsafe_b64encode(key).decode(),
    )


def _entry(*, ciphertext: str, nonce: str, organization_id: str = "org-a") -> WorkflowSecret:
    return WorkflowSecret(
        organization_id=organization_id,
        workflow_id="workflow-a",
        name="input.email",
        ciphertext=ciphertext,
        nonce=nonce,
        key_version="v1",
    )


def test_vault_encrypts_and_authenticates_record_scope() -> None:
    vault = WorkflowVault(_settings())
    plaintext = "private-user@example.com"
    ciphertext, nonce = vault.encrypt("org-a", "workflow-a", "input.email", plaintext)

    assert plaintext not in ciphertext
    assert vault.decrypt(_entry(ciphertext=ciphertext, nonce=nonce)) == plaintext

    copied_to_another_tenant = _entry(
        ciphertext=ciphertext,
        nonce=nonce,
        organization_id="org-b",
    )
    with pytest.raises(VaultIntegrityError):
        vault.decrypt(copied_to_another_tenant)


@pytest.mark.parametrize("key", [None, "not-base64", base64.urlsafe_b64encode(b"short").decode()])
def test_vault_rejects_missing_or_malformed_keys(key: str | None) -> None:
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:", vault_key=key)
    with pytest.raises(VaultUnavailableError):
        WorkflowVault(settings)
