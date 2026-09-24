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
import json
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
    # cycle-6 rm-019: PRODUCTION-shaped cron inventory source. The fleet
    # host writes a top-level OBJECT {"jobs": [...], "updated_at": ...}
    # (57 jobs live); this fixture previously created NO jobs.json at all,
    # so the suite locked in the empty-mirror behavior the cycle-6 assess
    # proved live ({} mirrored since 9f94762). last_status exercises the
    # field projection (mirror keeps id/name/schedule/enabled only).
    (home / ".hermes" / "cron").mkdir(parents=True)
    (home / ".hermes" / "cron" / "jobs.json").write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "id": "cron-a",
                        "name": "repo settings sync",
                        "schedule": "40 8 * * *",
                        "enabled": True,
                        "last_status": "ok",
                    },
                    {
                        "id": "cron-b",
                        "name": "watchdog",
                        "schedule": "*/5 * * * *",
                        "enabled": False,
                    },
                ],
                "updated_at": FROZEN_TS,
            }
        )
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
    # cycle-6 rm-019: the production-shaped (dict) jobs.json source MUST
    # mirror a populated inventory — this is the assertion whose absence
    # let the {} regression pass the whole suite for a cycle
    inv_raw = _origin_show(origin, "data", "control-plane/cron-inventory.json")
    assert inv_raw.startswith(f"# generated {FROZEN_TS}\n"), inv_raw[:60]
    inventory = json.loads(
        "\n".join(
            line for line in inv_raw.splitlines() if not line.startswith("#")
        )
    )
    assert inventory == {
        "cron-a": {
            "name": "repo settings sync",
            "schedule": "40 8 * * *",
            "enabled": True,
        },
        "cron-b": {
            "name": "watchdog",
            "schedule": "*/5 * * * *",
            "enabled": False,
        },
    }, "dict-shaped jobs.json must mirror a populated, projected inventory"

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


# --------------------------------------------------------------------------
# Cycle-6 batch F additions (rm-019 shape tolerance + rm-044 self-check +
# rm-045 success-path restore / index hygiene / fetch visibility)
# --------------------------------------------------------------------------


def test_legacy_list_shaped_jobs_still_mirror(tmp_path: Path) -> None:
    """rm-019: the pre-E1 list-shaped sources keep mirroring (tolerance,
    not a flip) — both documented shapes populate the inventory."""
    origin = _make_origin(tmp_path)
    repo = _make_repo(origin, tmp_path)
    home = _fake_home(tmp_path)
    jobs_path = home / ".hermes" / "cron" / "jobs.json"
    jobs_path.write_text(
        json.dumps(
            [
                {"id": "cron-a", "name": "repo settings sync",
                 "schedule": "40 8 * * *", "enabled": True},
                {"id": "cron-b", "name": "watchdog",
                 "schedule": "*/5 * * * *", "enabled": False},
            ]
        )
    )
    frozen = _frozen_clock(tmp_path)

    r = _run(_env(repo, home, frozen), repo)
    assert r.returncode == 0, r.stderr
    inv = json.loads(
        "\n".join(
            line
            for line in _origin_show(
                origin, "data", "control-plane/cron-inventory.json"
            ).splitlines()
            if not line.startswith("#")
        )
    )
    assert set(inv) == {"cron-a", "cron-b"}, "list-shaped source emptied the mirror"


def test_shape_regression_fails_closed_instead_of_empty_mirror(tmp_path: Path) -> None:
    """rm-044 self-check: entries without ids = non-empty source, empty
    inventory — the run must FAIL loudly and restore the entry branch,
    never stage/push {}. This is the exact class that shipped the cycle-6
    {} regression invisibly."""
    origin = _make_origin(tmp_path)
    repo = _make_repo(origin, tmp_path)
    home = _fake_home(tmp_path)
    (home / ".hermes" / "cron" / "jobs.json").write_text(
        json.dumps({"jobs": [{"name": "idless-job", "schedule": "@daily"}]})
    )
    frozen = _frozen_clock(tmp_path)

    _git(repo, "checkout", "-q", "-b", "feature")
    r = _run(_env(repo, home, frozen), repo)
    assert r.returncode != 0, "empty-mirror outcome must fail, not succeed"
    assert "cron-inventory integrity" in r.stderr
    assert "FAILED" in r.stderr
    assert _branch(repo) == "feature", "fail-closed must restore the entry branch"
    # nothing was pushed: no data branch may exist on the remote
    assert (
        _git(origin, "rev-parse", "--verify", "data", check=False).returncode != 0
    ), "fail-closed run must not push any mirror state"


def test_corrupt_jobs_json_fails_closed(tmp_path: Path) -> None:
    """rm-044: a corrupt source must fail the run — the old warn-and-
    continue path OVERWROTE the last known mirror with {}."""
    origin = _make_origin(tmp_path)
    repo = _make_repo(origin, tmp_path)
    home = _fake_home(tmp_path)
    (home / ".hermes" / "cron" / "jobs.json").write_text("{not json at all")
    frozen = _frozen_clock(tmp_path)

    _git(repo, "checkout", "-q", "-b", "feature")
    r = _run(_env(repo, home, frozen), repo)
    assert r.returncode != 0
    assert "jobs.json unreadable" in r.stderr
    assert _branch(repo) == "feature"


def test_success_from_feature_branch_restores_feature(tmp_path: Path) -> None:
    """rm-045: BOTH success paths (push, then no-op) restore the ENTRY
    branch — a manual run from any branch finds its checkout where it
    left it, instead of being dumped on main."""
    origin = _make_origin(tmp_path)
    repo = _make_repo(origin, tmp_path)
    home = _fake_home(tmp_path)
    frozen = _frozen_clock(tmp_path)

    _git(repo, "checkout", "-q", "-b", "feature")
    r1 = _run(_env(repo, home, frozen), repo)
    assert r1.returncode == 0, r1.stderr
    assert "pushed control-plane mirror" in r1.stdout
    assert _branch(repo) == "feature", "push success must restore the entry branch"

    r2 = _run(_env(repo, home, frozen), repo)
    assert r2.returncode == 0, r2.stderr
    assert "no control-plane changes" in r2.stdout
    assert _branch(repo) == "feature", "no-op success must restore the entry branch"


def test_failed_commit_leaves_no_staged_residue(tmp_path: Path) -> None:
    """rm-045: a failure between `git add` and `git commit` must restore
    the entry branch WITH a clean index — the old branch-only restore left
    the half-staged mirror edits staged on the restored branch."""
    origin = _make_origin(tmp_path)
    repo = _make_repo(origin, tmp_path)
    home = _fake_home(tmp_path)
    frozen = _frozen_clock(tmp_path)

    _git(repo, "checkout", "-q", "-b", "feature")
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)

    r = _run(_env(repo, home, frozen), repo)
    assert r.returncode != 0, "rejected commit must fail the run"
    assert "FAILED" in r.stderr
    assert "restored checkout to feature" in r.stderr
    assert _branch(repo) == "feature"
    staged = _git(repo, "diff", "--cached", "--name-only").stdout
    assert staged == "", f"restore left staged residue: {staged!r}"
    dirty = _git(repo, "status", "--porcelain").stdout
    assert dirty == "", f"restore left working-tree residue: {dirty!r}"


def test_fetch_failure_is_visible_and_fails_loud(tmp_path: Path) -> None:
    """rm-045: fetch_ok used to be a dead variable — a failed fetch was
    silent. It must now WARN; the run then proceeds against the stale
    tracking ref and fails loudly at the push (broken remote)."""
    origin = _make_origin(tmp_path)
    repo = _make_repo(origin, tmp_path)
    home = _fake_home(tmp_path)
    frozen = _frozen_clock(tmp_path)

    _git(repo, "checkout", "-q", "-b", "feature")
    _git(
        repo, "remote", "set-url", "origin",
        str(tmp_path / "nonexistent-remote.git"),
    )
    r = _run(_env(repo, home, frozen), repo)
    assert r.returncode != 0, "push to a broken remote must fail the run"
    assert "WARNING: fetch origin/data failed" in r.stderr
    assert "FAILED" in r.stderr
    assert _branch(repo) == "feature"
