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
import hashlib
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
CLAIMS_MAIN = (
    "# fixture claims ledger\nversion: 1\nclaims:\n"
    "  - id: fixture-claim\n"
    "    what: canonical main-tree claims copy (cycle-7 F1h parity)\n"
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
    (seed / "control-plane" / "claims.yaml").write_text(CLAIMS_MAIN)
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
    # realistic cron jobs.json (cycle-8 rm-046): the host file is a top-level
    # dict {"jobs": [...]} with 57 entries — the fixture must exercise the
    # REAL shape or the suite certifies whatever an empty mirror produces
    # (the exact gap that let the cycle-6/8 silent-empty regression pass)
    (home / ".hermes" / "cron").mkdir(parents=True)
    (home / ".hermes" / "cron" / "jobs.json").write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "id": "control-plane-sync",
                        "name": "mirror fleet state",
                        "schedule": {"expr": "40 8 * * *"},
                        "enabled": True,
                        "script": "~/.hermes/scripts/control-plane-sync.sh",
                    },
                    {
                        "id": "repo-settings-sync",
                        "name": "sync repo settings",
                        "schedule": {"expr": "30 8 * * *"},
                        "enabled": True,
                        "script": "~/.hermes/scripts/repo-settings-sync.sh",
                    },
                ],
                "updated_at": "2026-09-21T00:00:00Z",
            }
        )
    )
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
    # claims.yaml: same parity class (cycle-7 F1h) — mirrored from main
    assert _origin_show(origin, "data", "control-plane/claims.yaml") == (
        CLAIMS_MAIN
    )
    watchdog = _origin_show(
        origin, "data", "control-plane/conductor-watchdog-alerts.log"
    ).splitlines()
    assert watchdog == WATCHDOG_LINES, "default bound (5000) mirrors all 10 lines"
    assert _origin_show(origin, "data", "control-plane/runners.txt") == (
        f"# generated {FROZEN_TS}\n"
    )
    # cron inventory mirrors the FULL fixture job set, count header included
    # (cycle-8 rm-046: an empty inventory can never pass this assertion again)
    cron = _origin_show(origin, "data", "control-plane/cron-inventory.json")
    assert f"# generated {FROZEN_TS}\n# 2 jobs\n" in cron
    assert "control-plane-sync" in cron and "repo-settings-sync" in cron
    # manifest-verify journal (cycle-8 rm-048): hermetic HOME has no deployed
    # pair -> rc=2 journaled exactly once; the state dedupe is what keeps the
    # second run below a true no-op
    verify_lines = _origin_show(
        origin, "data", "control-plane/manifest-verify.log"
    ).splitlines()
    assert len(verify_lines) == 1
    assert "rc=2 not-a-deployed-host" in verify_lines[0]

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


def test_success_restores_entry_branch(tmp_path: Path) -> None:
    """Cycle-7 F1c: the SUCCESS path used to hard-checkout main, stranding a
    run entered from a feature branch there (only the failure trap restored)."""
    origin = _make_origin(tmp_path)
    repo = _make_repo(origin, tmp_path)
    home = _fake_home(tmp_path)
    frozen = _frozen_clock(tmp_path)

    _git(repo, "checkout", "-q", "-b", "feature")
    r = _run(_env(repo, home, frozen), repo)
    assert r.returncode == 0, r.stderr
    assert "pushed control-plane mirror" in r.stdout
    assert _branch(repo) == "feature", "success must restore the ENTRY branch"

    # and the no-op path restores it too
    r2 = _run(_env(repo, home, frozen), repo)
    assert r2.returncode == 0, r2.stderr
    assert "no control-plane changes" in r2.stdout
    assert _branch(repo) == "feature"


def test_untracked_operator_file_is_never_staged(tmp_path: Path) -> None:
    """Cycle-7 F1b: staging is allowlisted — `git add control-plane` used to
    sweep ANY untracked operator file onto the PUBLIC data branch."""
    origin = _make_origin(tmp_path)
    repo = _make_repo(origin, tmp_path)
    home = _fake_home(tmp_path)
    frozen = _frozen_clock(tmp_path)

    # an operator leaves a scratch file inside the mirrored directory
    scratch = repo / "control-plane" / "operator-note.txt"
    scratch.write_text("operator scratch — must never reach the data branch\n")

    r = _run(_env(repo, home, frozen), repo)
    assert r.returncode == 0, r.stderr
    assert "pushed control-plane mirror" in r.stdout

    data_tree = _git(origin, "ls-tree", "-r", "--name-only", "data").stdout
    assert "control-plane/conductor-tracks.tsv" in data_tree, "copy-set must land"
    assert "operator-note.txt" not in data_tree, "scratch must NOT be committed"
    # the file survives untracked in the working tree, never swept away
    assert scratch.exists()
    tracked = _git(repo, "ls-files", "--", "control-plane").stdout
    assert "control-plane/operator-note.txt" not in tracked


def test_cron_inventory_accepts_legacy_list_shape(tmp_path: Path) -> None:
    """cycle-8 rm-046: a bare-list jobs.json (legacy / hand-edited shape)
    still mirrors its full job set — the parse must tolerate BOTH shapes."""
    origin = _make_origin(tmp_path)
    repo = _make_repo(origin, tmp_path)
    home = _fake_home(tmp_path)
    frozen = _frozen_clock(tmp_path)
    (home / ".hermes" / "cron" / "jobs.json").write_text(
        '[{"id": "legacy-job", "name": "legacy", "schedule": "0 4 * * *",'
        ' "enabled": false, "script": "~/.hermes/scripts/legacy.sh"}]'
    )

    r = _run(_env(repo, home, frozen), repo)
    assert r.returncode == 0, f"first run failed:\n{r.stderr}"

    cron = _origin_show(origin, "data", "control-plane/cron-inventory.json")
    assert "# 1 jobs" in cron and "legacy-job" in cron


def test_shapeless_jobs_json_fails_loudly_not_published(tmp_path: Path) -> None:
    """cycle-8 rm-046 canary: a shapeless/empty jobs source aborts the run
    loudly and publishes NOTHING — the silent-empty public mirror ({} daily
    on origin/data since 9f94762) is now structurally impossible."""
    origin = _make_origin(tmp_path)
    repo = _make_repo(origin, tmp_path)
    home = _fake_home(tmp_path)
    frozen = _frozen_clock(tmp_path)
    (home / ".hermes" / "cron" / "jobs.json").write_text('{"updated_at": "x"}')

    _git(repo, "checkout", "-q", "-b", "feature")
    r = _run(_env(repo, home, frozen), repo)
    assert r.returncode == 1
    assert "cron-inventory canary" in r.stderr
    assert _branch(repo) == "feature", "canary failure must restore entry branch"
    refs = _git(origin, "show-ref").stdout
    assert "refs/heads/data" not in refs, "canary failure must not publish"


def test_missing_jobs_json_fails_loudly(tmp_path: Path) -> None:
    """cycle-8 rm-046 canary: a MISSING jobs.json aborts loudly — the old
    code published an empty {} inventory to the public branch instead."""
    origin = _make_origin(tmp_path)
    repo = _make_repo(origin, tmp_path)
    home = _fake_home(tmp_path)
    frozen = _frozen_clock(tmp_path)
    (home / ".hermes" / "cron" / "jobs.json").unlink()

    r = _run(_env(repo, home, frozen), repo)
    assert r.returncode == 1
    assert "cron-inventory canary" in r.stderr
    assert "jobs.json is missing" in r.stderr
    assert _branch(repo) == "main"


def test_deployed_verify_drift_journaled_report_only(tmp_path: Path) -> None:
    """cycle-8 rm-048: the daily run verifies the deployed manifest against
    the entry-branch (canonical) scripts and journals drift names onto the
    public data branch — report-only (a red trust chain is VISIBLE, the
    mirror never wedges) and state-deduped (steady drift = no noise commit)."""
    origin = _make_origin(tmp_path)
    repo = _make_repo(origin, tmp_path)
    home = _fake_home(tmp_path)
    frozen = _frozen_clock(tmp_path)

    scripts = home / ".hermes" / "scripts"
    scripts.mkdir(parents=True)
    wrapper = scripts / "control-plane-sync.sh"
    wrapper.write_text("#!/bin/sh\nexec python3 scripts/sync_data_branch.py\n")
    # manifest pins digests that can never match the real (entry-branch)
    # scripts — deterministic two-name drift
    manifest = scripts / "MANIFEST.sha256"
    manifest.write_text(
        f"{'0' * 64}  control-plane-sync.sh\n"
        f"{'0' * 64}  sync_data_branch.py\n"
    )

    env = _env(
        repo, home, frozen,
        VERIFY_WRAPPER=str(wrapper),
        VERIFY_MANIFEST=str(manifest),
    )
    r1 = _run(env, repo)
    assert r1.returncode == 0, f"drift must not wedge the mirror:\n{r1.stderr}"
    assert "manifest-verify 1 drift=" in r1.stdout

    journal = _origin_show(
        origin, "data", "control-plane/manifest-verify.log"
    ).splitlines()
    assert len(journal) == 1
    assert "rc=1 drift=control-plane-sync.sh,sync_data_branch.py" in journal[0]

    # a steady drift state is deduped: the second identical run is a no-op
    r2 = _run(env, repo)
    assert r2.returncode == 0, r2.stderr
    assert "no control-plane changes" in r2.stdout


def test_deployed_verify_clean_state_journaled(tmp_path: Path) -> None:
    """cycle-8 rm-048: a GREEN contract (manifest pinning the TRUE digests)
    journals rc=0 clean — the daily visible proof the trust chain holds."""
    origin = _make_origin(tmp_path)
    repo = _make_repo(origin, tmp_path)
    home = _fake_home(tmp_path)
    frozen = _frozen_clock(tmp_path)

    scripts = home / ".hermes" / "scripts"
    scripts.mkdir(parents=True)
    wrapper = scripts / "control-plane-sync.sh"
    wrapper.write_text("#!/bin/sh\nexec python3 scripts/sync_data_branch.py\n")

    def sha(path: Path) -> str:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    manifest = scripts / "MANIFEST.sha256"
    manifest.write_text(
        f"{sha(wrapper)}  control-plane-sync.sh\n"
        f"{sha(ROOT / 'scripts' / 'sync_data_branch.py')}  sync_data_branch.py\n"
    )

    r = _run(
        _env(
            repo, home, frozen,
            VERIFY_WRAPPER=str(wrapper),
            VERIFY_MANIFEST=str(manifest),
        ),
        repo,
    )
    assert r.returncode == 0, f"run failed:\n{r.stderr}"
    assert "manifest-verify 0 clean" in r.stdout

    journal = _origin_show(
        origin, "data", "control-plane/manifest-verify.log"
    ).splitlines()
    assert len(journal) == 1 and "rc=0 clean" in journal[0]
