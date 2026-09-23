"""Tests for scripts/verify_deployed_artifacts.py (cycle-5 batch E2, rm-042).

The cycle-5 assess proved the gap this tool closes: the deployed cron
wrapper delegated to scripts/sync_data_branch.py while the hardened twin
never ran, and the deployed MANIFEST.sha256 pinned neither cron-wired
entrypoint — nothing could have detected the divergence.

Locks the contract:

  * rc 0  — wrapper + delegate pinned, every entry verifies
  * rc 1  — planted digest divergence, unpinned entrypoint, dangling
            delegation, pinned-but-missing artifact (each reported)
  * rc 2  — deployed artifacts absent (CI/dev checkout: skip, not fail)

Hermetic: wrapper/manifest/repo all point at tmp fixtures via
VERIFY_WRAPPER / VERIFY_MANIFEST / VERIFY_REPO; the delegate pin is checked
against the REAL repository copy of scripts/sync_data_branch.py so the
planted-diff test exercises the exact production trust chain.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_deployed_artifacts.py"
REAL_DELEGATE = ROOT / "scripts" / "sync_data_branch.py"

WRAPPER_BODY = (
    "#!/bin/sh\n"
    "# deployed cron wrapper (fixture)\n"
    "cd /work/projects/.github\n"
    "exec python3 scripts/sync_data_branch.py\n"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_deployed(tmp_path: Path, *, delegate_digest: str | None = None,
                   wrapper_digest: str | None = None,
                   extra_entries: dict[str, str] | None = None,
                   omit_delegate: bool = False) -> tuple[Path, Path]:
    """Fixture: deployed wrapper + manifest next to it."""
    deployed = tmp_path / "deployed"
    deployed.mkdir()
    wrapper = deployed / "control-plane-sync.sh"
    wrapper.write_text(WRAPPER_BODY)
    manifest = deployed / "MANIFEST.sha256"
    lines = []
    if wrapper_digest is not None:
        lines.append(f"{wrapper_digest}  control-plane-sync.sh")
    else:
        lines.append(f"{_sha(wrapper)}  control-plane-sync.sh")
    if not omit_delegate:
        lines.append(
            f"{delegate_digest if delegate_digest is not None else _sha(REAL_DELEGATE)}"
            "  sync_data_branch.py"
        )
    for name, digest in (extra_entries or {}).items():
        lines.append(f"{digest}  {name}")
    manifest.write_text("\n".join(lines) + "\n")
    return wrapper, manifest


def _run(wrapper: Path, manifest: Path) -> subprocess.CompletedProcess:
    env = dict(
        __import__("os").environ,
        VERIFY_WRAPPER=str(wrapper),
        VERIFY_MANIFEST=str(manifest),
        VERIFY_REPO=str(ROOT),
    )
    return subprocess.run(
        [sys.executable, str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60
    )


def test_clean_chain_verifies(tmp_path: Path) -> None:
    wrapper, manifest = _make_deployed(tmp_path)
    res = _run(wrapper, manifest)
    assert res.returncode == 0, res.stderr
    assert "deployed artifacts verified" in res.stdout
    assert "sync_data_branch.py" in res.stdout


def test_planted_digest_divergence_fails(tmp_path: Path) -> None:
    planted = "0" * 64  # plausible digest, wrong content
    wrapper, manifest = _make_deployed(tmp_path, delegate_digest=planted)
    res = _run(wrapper, manifest)
    assert res.returncode == 1, "planted divergence must fail"
    assert "sync_data_branch.py: digest mismatch" in res.stderr


def test_unpinned_entrypoint_fails(tmp_path: Path) -> None:
    # wrapper pinned (correctly) but the delegate entry omitted entirely
    wrapper, manifest = _make_deployed(tmp_path, omit_delegate=True)
    manifest.write_text(f"{_sha(wrapper)}  control-plane-sync.sh\n")
    res = _run(wrapper, manifest)
    assert res.returncode == 1, "unpinned delegate must fail"
    assert "sync_data_branch.py: not pinned" in res.stderr


def test_wrapper_digest_divergence_fails(tmp_path: Path) -> None:
    wrapper, manifest = _make_deployed(tmp_path, wrapper_digest="f" * 64)
    res = _run(wrapper, manifest)
    assert res.returncode == 1, "wrapper digest divergence must fail"
    assert "control-plane-sync.sh: digest mismatch" in res.stderr


def test_dangling_delegation_fails(tmp_path: Path) -> None:
    wrapper, manifest = _make_deployed(tmp_path)
    wrapper.write_text("#!/bin/sh\nexec python3 scripts/does_not_exist.py\n")
    res = _run(wrapper, manifest)
    assert res.returncode == 1, "dangling delegation must fail"
    assert "does not exist" in res.stderr


def test_pinned_but_missing_artifact_fails(tmp_path: Path) -> None:
    wrapper, manifest = _make_deployed(
        tmp_path, extra_entries={"absent-fleet-script.sh": "a" * 64}
    )
    res = _run(wrapper, manifest)
    assert res.returncode == 1, "pinned-but-missing artifact must fail"
    assert "absent-fleet-script.sh: pinned but missing" in res.stderr


def test_absent_deployed_artifacts_skip_with_rc2(tmp_path: Path) -> None:
    res = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env=dict(
            __import__("os").environ,
            VERIFY_WRAPPER=str(tmp_path / "nope" / "control-plane-sync.sh"),
            VERIFY_MANIFEST=str(tmp_path / "nope" / "MANIFEST.sha256"),
            VERIFY_REPO=str(ROOT),
        ),
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 2, "absent deployed artifacts must skip (rc 2)"
    assert "absent" in res.stdout
