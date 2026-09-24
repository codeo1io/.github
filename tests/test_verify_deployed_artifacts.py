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
REAL_AUX_DELEGATE = ROOT / "scripts" / "sync_repo_settings.py"
REAL_AUX_DELEGATE_2 = ROOT / "scripts" / "check_known_hosts.py"

WRAPPER_BODY = (
    "#!/bin/sh\n"
    "# deployed cron wrapper (fixture)\n"
    "cd /work/projects/.github\n"
    "exec python3 scripts/sync_data_branch.py\n"
)

# real shape: the deployed repo-settings wrapper names TWO of our scripts
AUX_WRAPPER_BODY = (
    "#!/bin/sh\n"
    "# deployed repo-settings wrapper (fixture)\n"
    'REPO="/work/projects/.github"\n'
    '  if ! python3 "$REPO/scripts/check_known_hosts.py"; then echo drift; fi\n'
    '  python3 "$REPO/scripts/sync_repo_settings.py" --apply\n'
)

# fleet noise: references OTHER repos' scripts/ trees — must be ignored
FOREIGN_WRAPPER_BODY = (
    "#!/bin/sh\n"
    "cd /work/projects/somewhere-else\n"
    "exec bash scripts/check.sh\n"
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


# --- cycle-7 F1a: half-deployed pair is drift, never a silent skip ----------


def test_wrapper_present_manifest_missing_is_drift(tmp_path: Path) -> None:
    # THE cycle-7 P2: a deployed wrapper whose manifest vanished graded rc 2
    # ("not a deployed host") and silently disabled verification.
    wrapper, manifest = _make_deployed(tmp_path)
    manifest.unlink()
    res = _run(wrapper, manifest)
    assert res.returncode == 1, "wrapper-without-manifest must be DRIFT (rc 1), not skip"
    assert "MANIFEST.sha256" in res.stderr and "missing" in res.stderr
    assert "unverifiable" in res.stderr


def test_manifest_present_wrapper_missing_is_drift(tmp_path: Path) -> None:
    wrapper, manifest = _make_deployed(tmp_path)
    wrapper.unlink()
    res = _run(wrapper, manifest)
    assert res.returncode == 1, "manifest-without-wrapper must be DRIFT (rc 1), not skip"
    assert "configured wrapper missing" in res.stderr


# --- cycle-7 F1a: auxiliary delegating wrappers (repo-settings chain) -------


def test_auxiliary_wrapper_chain_verifies(tmp_path: Path) -> None:
    wrapper, manifest = _make_deployed(tmp_path)
    aux = wrapper.parent / "repo-settings-sync.sh"
    aux.write_text(AUX_WRAPPER_BODY)
    manifest.write_text(
        manifest.read_text()
        + f"{_sha(aux)}  repo-settings-sync.sh\n"
        + f"{_sha(REAL_AUX_DELEGATE_2)}  check_known_hosts.py\n"
        + f"{_sha(REAL_AUX_DELEGATE)}  sync_repo_settings.py\n"
    )
    res = _run(wrapper, manifest)
    assert res.returncode == 0, res.stderr


def test_auxiliary_wrapper_unpinned_is_drift(tmp_path: Path) -> None:
    wrapper, manifest = _make_deployed(tmp_path)
    aux = wrapper.parent / "repo-settings-sync.sh"
    aux.write_text(AUX_WRAPPER_BODY)  # delegating wrapper present, NOT pinned
    res = _run(wrapper, manifest)
    assert res.returncode == 1, "an unpinned delegating wrapper must be drift"
    assert "repo-settings-sync.sh: not pinned" in res.stderr
    assert "sync_repo_settings.py: not pinned" in res.stderr
    assert "check_known_hosts.py: not pinned" in res.stderr


def test_auxiliary_delegate_digest_checked_against_repo_copy(tmp_path: Path) -> None:
    wrapper, manifest = _make_deployed(tmp_path)
    aux = wrapper.parent / "repo-settings-sync.sh"
    aux.write_text(AUX_WRAPPER_BODY)
    manifest.write_text(
        manifest.read_text()
        + f"{_sha(aux)}  repo-settings-sync.sh\n"
        + f"{_sha(REAL_AUX_DELEGATE_2)}  check_known_hosts.py\n"
        + f"{'0' * 64}  sync_repo_settings.py\n"  # plausible digest, wrong
    )
    res = _run(wrapper, manifest)
    assert res.returncode == 1, "auxiliary delegate digest must be checked"
    assert "sync_repo_settings.py: digest mismatch" in res.stderr


def test_foreign_repo_delegations_are_out_of_scope(tmp_path: Path) -> None:
    """The deployed dir hosts dozens of fleet scripts referencing OTHER
    repos' scripts/ trees — discovery must resolve delegations into THIS
    repo only, or the live host run drowns in spurious drift (caught while
    pinning the real manifest, cycle-7 F2)."""
    wrapper, manifest = _make_deployed(tmp_path)
    # pure-foreign wrapper: entirely ignored, pinned or not
    foreign = wrapper.parent / "fleet-noise.sh"
    foreign.write_text(FOREIGN_WRAPPER_BODY)
    res = _run(wrapper, manifest)
    assert res.returncode == 0, res.stderr
    assert "fleet-noise.sh" not in res.stderr
    assert "check.sh" not in res.stderr

    # mixed wrapper: only OUR delegate joins the contract
    mixed = wrapper.parent / "mixed-wrapper.sh"
    mixed.write_text(
        "#!/bin/sh\n"
        "cd /somewhere\n"
        "bash scripts/other_repo_helper.sh\n"
        "exec python3 scripts/sync_repo_settings.py --apply\n"
    )
    manifest.write_text(
        manifest.read_text()
        + f"{_sha(mixed)}  mixed-wrapper.sh\n"
        + f"{_sha(REAL_AUX_DELEGATE)}  sync_repo_settings.py\n"
    )
    res = _run(wrapper, manifest)
    assert res.returncode == 0, res.stderr
    assert "other_repo_helper.sh" not in res.stderr


def test_non_delegating_script_is_not_required_to_be_pinned(tmp_path: Path) -> None:
    wrapper, manifest = _make_deployed(tmp_path)
    (wrapper.parent / "plain-fleet-script.sh").write_text("#!/bin/sh\necho fleet\n")
    res = _run(wrapper, manifest)
    assert res.returncode == 0, res.stderr
