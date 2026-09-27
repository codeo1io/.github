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

Cycle-6 batch F3 (rm-044): the rc-2 skip tests and the clean-chain test
run against a tmp fixture repo whose origin/data branch carries a HEALTHY
control-plane mirror (populated inventory, bounded watchdog, canonical
corrections) — the content checks run for real against that fixture, and
planted-violation tests prove each check fires (including from a NON-host
checkout, where content drift outranks the rc=2 skip).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_deployed_artifacts.py"
REAL_DELEGATE = ROOT / "scripts" / "sync_data_branch.py"


def _g(cwd: Path | None, *args: str) -> None:
    argv = ["git"] + ((["-C", str(cwd)] if cwd else [])) + list(args)
    subprocess.run(argv, check=True, capture_output=True, text=True)

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


def _run(wrapper: Path, manifest: Path, repo: Path = ROOT, home: Path | None = None,
         **env_extra: str) -> subprocess.CompletedProcess:
    env = dict(
        os.environ,
        VERIFY_WRAPPER=str(wrapper),
        VERIFY_MANIFEST=str(manifest),
        VERIFY_REPO=str(repo),
    )
    if home is not None:
        env["HOME"] = str(home)
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60
    )


def test_clean_chain_verifies(tmp_path: Path) -> None:
    wrapper, manifest = _make_deployed(tmp_path)
    repo, _origin = _make_content_repo(tmp_path)
    home = _content_home(tmp_path)
    res = _run(wrapper, manifest, repo=repo, home=home)
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
    repo, _origin = _make_content_repo(tmp_path)
    res = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env=dict(
            os.environ,
            VERIFY_WRAPPER=str(tmp_path / "nope" / "control-plane-sync.sh"),
            VERIFY_MANIFEST=str(tmp_path / "nope" / "MANIFEST.sha256"),
            VERIFY_REPO=str(repo),
        ),
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 2, "absent deployed artifacts must skip (rc 2)"
    assert "absent" in res.stdout


# --------------------------------------------------------------------------
# Cycle-6 batch F3 (rm-044): data-branch CONTENT checks
# --------------------------------------------------------------------------

CONTENT_JOBS = [
    {"id": "cron-a", "name": "repo settings sync", "schedule": "40 8 * * *", "enabled": True},
    {"id": "cron-b", "name": "watchdog", "schedule": "*/5 * * * *", "enabled": False},
]
CORRECTIONS_FIXTURE = "# fixture canonical corrections\nversion: 1\n"
WATCHDOG_FIXTURE = [f"wd {i}" for i in range(3)]


def _healthy_inventory() -> str:
    projected = {
        job["id"]: {
            "name": job["name"],
            "schedule": job["schedule"],
            "enabled": job["enabled"],
        }
        for job in CONTENT_JOBS
    }
    return "# generated 2026-09-21T00:00:00Z\n" + json.dumps(projected, indent=2, sort_keys=True) + "\n"


def _make_content_repo(
    tmp_path: Path,
    *,
    inventory: str | None = None,
    watchdog_lines: int = 3,
    corrections_data: str | None = None,
) -> tuple[Path, Path]:
    """Fixture repo whose origin/data branch carries a (default-healthy)
    control-plane mirror; the real delegate script rides along so the
    wrapper trust-chain checks keep working against it."""
    origin = tmp_path / "content-origin.git"
    origin.mkdir()
    _g(origin, "init", "-q", "--bare", "-b", "main")

    repo = tmp_path / "content-repo"
    _g(None, "clone", "-q", str(origin), str(repo))
    _g(repo, "config", "user.email", "fixture@example.invalid")
    _g(repo, "config", "user.name", "fixture")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "sync_data_branch.py").write_text(REAL_DELEGATE.read_text())
    (repo / "control-plane").mkdir()
    (repo / "control-plane" / "corrections.yaml").write_text(CORRECTIONS_FIXTURE)
    _g(repo, "add", "-A")
    _g(repo, "commit", "-qm", "seed main")
    _g(repo, "push", "-q", "origin", "main")

    _g(repo, "checkout", "-q", "-b", "data")
    (repo / "control-plane" / "cron-inventory.json").write_text(
        _healthy_inventory() if inventory is None else inventory
    )
    (repo / "control-plane" / "conductor-watchdog-alerts.log").write_text(
        "\n".join(f"wd {i}" for i in range(watchdog_lines)) + "\n"
    )
    (repo / "control-plane" / "corrections.yaml").write_text(
        CORRECTIONS_FIXTURE if corrections_data is None else corrections_data
    )
    _g(repo, "add", "-A")
    _g(repo, "commit", "-qm", "seed data")
    _g(repo, "push", "-q", "origin", "data")
    _g(repo, "checkout", "-q", "main")
    return repo, origin


def _content_home(tmp_path: Path, *, jobs: object = None) -> Path:
    home = tmp_path / "vhome"
    (home / ".hermes" / "cron").mkdir(parents=True)
    payload = CONTENT_JOBS if jobs is None else jobs
    (home / ".hermes" / "cron" / "jobs.json").write_text(
        payload if isinstance(payload, str) else json.dumps(payload)
    )
    return home


def test_empty_inventory_with_live_jobs_is_drift(tmp_path: Path) -> None:
    """The exact cycle-6 production bug, planted: {} mirror while the host
    source holds jobs — must be rc 1 with the violation named."""
    wrapper, manifest = _make_deployed(tmp_path)
    repo, _origin = _make_content_repo(
        tmp_path, inventory="# generated 2026-09-21T00:00:00Z\n{}\n"
    )
    home = _content_home(tmp_path)
    res = _run(wrapper, manifest, repo=repo, home=home)
    assert res.returncode == 1, "silent empty mirror must be drift"
    assert "EMPTY while jobs.json holds 2 jobs" in res.stderr


def test_stale_inventory_with_empty_host_jobs_is_drift(tmp_path: Path) -> None:
    wrapper, manifest = _make_deployed(tmp_path)
    repo, _origin = _make_content_repo(tmp_path)  # populated mirror
    home = _content_home(tmp_path, jobs={"jobs": [], "updated_at": "x"})
    res = _run(wrapper, manifest, repo=repo, home=home)
    assert res.returncode == 1
    assert "stale jobs" in res.stderr


def test_oversized_watchdog_mirror_is_drift(tmp_path: Path) -> None:
    wrapper, manifest = _make_deployed(tmp_path)
    repo, _origin = _make_content_repo(tmp_path, watchdog_lines=7)
    home = _content_home(tmp_path)
    res = _run(
        wrapper, manifest, repo=repo, home=home,
        CONTROL_PLANE_WATCHDOG_MAX_LINES="5",
    )
    assert res.returncode == 1, "mirror above the cap must be drift"
    assert "exceeds cap 5" in res.stderr


def test_corrections_divergence_is_drift(tmp_path: Path) -> None:
    wrapper, manifest = _make_deployed(tmp_path)
    repo, _origin = _make_content_repo(
        tmp_path, corrections_data="# stale claim from an old run\n"
    )
    home = _content_home(tmp_path)
    res = _run(wrapper, manifest, repo=repo, home=home)
    assert res.returncode == 1, "data-branch corrections must match canonical main"
    assert "diverges from canonical" in res.stderr


def test_nonhost_checkout_reports_content_drift_not_rc2(tmp_path: Path) -> None:
    """Content drift outranks the not-a-deployed-host skip: a CI/dev
    checkout with a broken mirror must FAIL, not silently skip."""
    repo, _origin = _make_content_repo(
        tmp_path, inventory="# generated 2026-09-21T00:00:00Z\n{}\n"
    )
    home = _content_home(tmp_path)
    res = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env=dict(
            os.environ,
            VERIFY_WRAPPER=str(tmp_path / "nope" / "control-plane-sync.sh"),
            VERIFY_MANIFEST=str(tmp_path / "nope" / "MANIFEST.sha256"),
            VERIFY_REPO=str(repo),
            HOME=str(home),
        ),
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 1, "content drift must not hide behind rc=2"
    assert "silent mirror regression" in res.stderr
