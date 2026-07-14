"""Artifacts (screenshots) are optional. A read-only filesystem — the normal case on
serverless hosts, where everything outside /tmp is unwritable — must never fail an
analysis. Regression: the artifact mkdir used to run *outside* the browser-fallback
try block, so an OSError there killed the run before the HTTP explorer could take over.
"""

from pathlib import Path

from app.core.config import Settings
from app.services.explorer import AnalysisExplorer


def _explorer(artifact_root: Path) -> AnalysisExplorer:
    return AnalysisExplorer(
        Settings(),
        session_factory=None,  # type: ignore[arg-type]  # unused by _ensure_artifact_root
        events=None,  # type: ignore[arg-type]
        artifact_root=artifact_root,
    )


def test_artifact_root_is_created_when_writable(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    explorer = _explorer(root)
    assert explorer._ensure_artifact_root() is True
    assert root.is_dir()


def test_unwritable_artifact_root_disables_screenshots_instead_of_raising(tmp_path: Path) -> None:
    # Nesting a directory under a regular file is unwritable on every platform,
    # which is how we stand in for a read-only serverless filesystem.
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("")

    explorer = _explorer(blocker / "artifacts")

    assert explorer._ensure_artifact_root() is False  # no exception escapes
    assert explorer._artifacts_disabled is True
    assert explorer._ensure_artifact_root() is False  # stays disabled, no repeated syscalls


def test_artifact_root_defaults_to_settings() -> None:
    explorer = AnalysisExplorer(Settings(), session_factory=None, events=None)  # type: ignore[arg-type]
    assert explorer._artifact_root == Path(Settings().artifact_root)
