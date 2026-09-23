"""Hermetic behavioral tests for the PRODUCTION control-plane mirror twin.

Cycle-5 batch E1 (rm-017/rm-019): the deployed cron wrapper execs
``scripts/sync_data_branch.py`` from the canonical checkout, so this file
locks the cycle-2 B2 hardening properties onto THAT file (ported from the
retired, never-deployed ``scripts/control-plane-sync.sh``):

  * flock single-flight: a concurrent run exits 0 without touching the tree
  * entry-branch restore: a failure mid-run restores the entry branch (and
    screams if even the restore fails)
  * bounded watchdog mirror: only the tail of the alert log is mirrored;
    the source stays the record
  * copy-set parity: corrections.yaml (from the canonical main tree) AND
    both kanban OWNERS files are mirrored — closing the stale-corrections
    gap found on origin/data
  * stage-before-diff: untracked control-plane files count as changes, so a
    fresh data branch gets created instead of silently skipped
  * bounded subprocesses: git timeouts synthesize rc=124 and fail the run
    with branch restore instead of hanging the cron slot

The script runs as a subprocess against throwaway fixture repos (bare
origin + clone), exactly like production runs it. Wall-clock is frozen via
a ``sitecustomize.py`` injected through PYTHONPATH so the ts-stamped
generated files (runners.txt, cron-inventory.json) stay byte-stable across
runs — the idempotence test depends on that determinism. Freeze the
harness, never the script.
"""

from __future__ import annotations

import fcntl
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sync_data_branch.py"
FROZEN_TS = "2026-09-21T00:00:00Z"

KANBAN_OWNERS = ("t_acd6a2e8", "t_851e7951")
WATCHDOG_LINES = [f"wd line {i}" for i in range(10)]
CORRECTIONS_MAIN = (
    "# fixture corrections ledger\nversion: 1\nentries:\n"
    "  - id: fixture-amended\n"
    "    what: amended entry (canonical main-tree copy)\n"
)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], check=check, capture_output=True, text=True
    )


def _make_origin(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    origin.mkdir()
    _git(origin, "init", "-q", "--bare", "-b", "main")
    # initial main commit so clones have a HEAD
    seed = tmp_path / "seed"
    seed.mkdir()
    _git(seed, "init", "-q", "-b", "main")
    _git(seed, "config", "user.email", "fixture@example.invalid")
    _git(seed, "config", "user.name", "fixture")
    (seed / "README.md").write_text("# fixture fleet repo\n")
    (seed / "control-plane").mkdir()
    (seed / "control-plane" / "corrections.yaml").write_text(CORRECTIONS_MAIN)
    _git(seed, "add", "-A")
    _git(seed, "commit", "-qm", "seed")
    _git(seed, "push", "-q", str(origin), "main")
    subprocess.run(["rm", "-rf", str(seed)], check=True)
    return origin


def _make_repo(origin: Path, tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "clone", "-q", str(origin), str(repo)], check=True, capture_output=True
    )
    _git(repo, "config", "user.email", "fixture@example.invalid")
    _git(repo, "config", "user.name", "fixture")
    return repo


def _fake_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    (home / ".hermes" / "kanban" / "attachments").mkdir(parents=True)
    (home / ".hermes" / "conductor-tracks.tsv").write_text(
        "track_id\trepo\tintent\n42\tacme\tmaintain\n"
    )
    (home / ".hermes" / "conductor-watchdog-alerts.log").write_text(
        "\n".join(WATCHDOG_LINES) + "\n"
    )
    for tid in KANBAN_OWNERS:
        own = home / ".hermes" / "kanban" / "attachments" / tid / "OWNERS.md"
        own.parent.mkdir(parents=True, exist_ok=True)
        own.write_text(f"# {tid} owners\n@fixture-bot\n")
    return home


def _frozen_clock(tmp_path: Path) -> Path:
    """sitecustomize.py dir: freeze datetime.now for any python subprocess."""
    fixed = tmp_path / "frozen-clock"
    fixed.mkdir()
    (fixed / "sitecustomize.py").write_text(
        "import datetime as _dt\n"
        "class _Frozen(_dt.datetime):\n"
        "    @classmethod\n"
        "    def now(cls, tz=None):\n"
        "        return cls(2026, 9, 21, 0, 0, 0, tzinfo=tz or _dt.timezone.utc)\n"
        "_dt.datetime = _Frozen\n"
    )
    return fixed


def _env(repo: Path, home: Path, frozen: Path, **extra: str) -> dict:
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["PATH"] = "/usr/bin:/bin"
    env["PYTHONPATH"] = str(frozen)
    env["CONTROL_PLANE_REPO"] = str(repo)
    env["CONTROL_PLANE_LOCK"] = str(home / "sync.lock")
    env.update(extra)
    return env


def _run(env: dict, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        env=env,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=120,
    )


def _origin_show(origin: Path, ref: str, path: str) -> str:
    return subprocess.run(
        ["git", "-C", str(origin), "show", f"{ref}:{path}"],
        check=True, capture_output=True, text=True,
    ).stdout


def _branch(repo: Path) -> str:
    return _git(repo, "branch", "--show-current").stdout.strip()


# --------------------------------------------------------------------------
# Properties
# --------------------------------------------------------------------------


def test_mirror_pushes_full_copy_set_then_no_op(tmp_path: Path) -> None:
    origin = _make_origin(tmp_path)
    repo = _make_repo(origin, tmp_path)
    home = _fake_home(tmp_path)
    frozen = _frozen_clock(tmp_path)

    r1 = _run(_env(repo, home, frozen), repo)
    assert r1.returncode == 0, f"first run failed:\n{r1.stderr}"
    assert "pushed control-plane mirror" in r1.stdout
    assert _branch(repo) == "main", "entry branch must be restored on success"

    # copy-set parity: every mirrored file exists with source-faithful content
    assert _origin_show(origin, "data", "control-plane/conductor-tracks.tsv") == (
        home / ".hermes" / "conductor-tracks.tsv"
    ).read_text()
    for tid in KANBAN_OWNERS:
        assert _origin_show(
            origin, "data", f"control-plane/kanban-{tid}-OWNERS.md"
        ) == (home / ".hermes" / "kanban" / "attachments" / tid / "OWNERS.md").read_text()
    # corrections mirrored from the canonical MAIN tree, not stale data content
    assert _origin_show(origin, "data", "control-plane/corrections.yaml") == (
        CORRECTIONS_MAIN
    )
    watchdog = _origin_show(
        origin, "data", "control-plane/conductor-watchdog-alerts.log"
    ).splitlines()
    assert watchdog == WATCHDOG_LINES, "default bound (5000) mirrors all 10 lines"
    assert _origin_show(origin, "data", "control-plane/runners.txt") == (
        f"# generated {FROZEN_TS}\n"
    )

    # second run: byte-identical mirror (frozen clock) -> no-op
    r2 = _run(_env(repo, home, frozen), repo)
    assert r2.returncode == 0, f"idempotent run failed:\n{r2.stderr}"
    assert "no control-plane changes" in r2.stdout
    assert _branch(repo) == "main"


def test_watchdog_mirror_is_bounded_to_tail(tmp_path: Path) -> None:
    origin = _make_origin(tmp_path)
    repo = _make_repo(origin, tmp_path)
    home = _fake_home(tmp_path)
    frozen = _frozen_clock(tmp_path)

    r = _run(
        _env(repo, home, frozen, CONTROL_PLANE_WATCHDOG_MAX_LINES="4"), repo
    )
    assert r.returncode == 0, r.stderr
    mirrored = _origin_show(
        origin, "data", "control-plane/conductor-watchdog-alerts.log"
    ).splitlines()
    assert mirrored == WATCHDOG_LINES[-4:], "mirror must be the bounded tail"


def test_fresh_data_branch_is_created_not_skipped(tmp_path: Path) -> None:
    origin = _make_origin(tmp_path)
    repo = _make_repo(origin, tmp_path)
    # ensure NO local data branch exists: untracked-only staging must still
    # detect the change (stage-before-diff)
    r = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "data"],
        capture_output=True, text=True,
    )
    assert r.returncode != 0, "fixture unexpectedly already has a data branch"

    home = _fake_home(tmp_path)
    frozen = _frozen_clock(tmp_path)
    result = _run(_env(repo, home, frozen), repo)
    assert result.returncode == 0, result.stderr
    assert "pushed control-plane mirror" in result.stdout
    assert "control-plane/conductor-tracks.tsv" in _git(
        origin, "ls-tree", "-r", "--name-only", "data"
    ).stdout


def test_concurrent_run_is_single_flight(tmp_path: Path) -> None:
    origin = _make_origin(tmp_path)
    repo = _make_repo(origin, tmp_path)
    home = _fake_home(tmp_path)
    frozen = _frozen_clock(tmp_path)
    lock = home / "sync.lock"

    # hold the single-flight lock like a slow concurrent run
    held = os.open(str(lock), os.O_CREAT | os.O_WRONLY, 0o644)
    fcntl.flock(held, fcntl.LOCK_EX)

    before = _git(origin, "rev-parse", "data", check=False).stdout.strip() or "<absent>"
    r = _run(_env(repo, home, frozen), repo)
    fcntl.flock(held, fcntl.LOCK_UN)
    os.close(held)

    assert r.returncode == 0, "single-flight exit must be a clean 0"
    assert "lock held by another run" in r.stderr
    after = _git(origin, "rev-parse", "data", check=False).stdout.strip() or "<absent>"
    assert before == after, "locked-out run must not touch the mirror"
    assert _branch(repo) == "main"


def test_failed_push_restores_entry_branch(tmp_path: Path) -> None:
    origin = _make_origin(tmp_path)
    repo = _make_repo(origin, tmp_path)
    home = _fake_home(tmp_path)
    frozen = _frozen_clock(tmp_path)

    # entry branch is `feature`, not main — restore must target IT
    _git(repo, "checkout", "-q", "-b", "feature")

    # remote rejects every push: pre-receive hook exits 1
    hook = origin / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)

    r = _run(_env(repo, home, frozen), repo)
    assert r.returncode != 0, "rejected push must fail the run"
    assert "FAILED" in r.stderr
    assert "restored checkout to feature" in r.stderr
    assert _branch(repo) == "feature"


def test_git_timeout_fails_loudly_instead_of_hanging(tmp_path: Path) -> None:
    origin = _make_origin(tmp_path)
    repo = _make_repo(origin, tmp_path)
    home = _fake_home(tmp_path)
    frozen = _frozen_clock(tmp_path)

    _git(repo, "checkout", "-q", "-b", "feature")
    r = _run(
        _env(repo, home, frozen, CONTROL_PLANE_GIT_TIMEOUT="0"), repo
    )
    assert r.returncode != 0, "timeout synthesis must fail the run"
    assert "timed out after 0s" in r.stderr
    # even the restore attempt timed out — the run must say so, not hang
    assert "RESTORE FAILED" in r.stderr
