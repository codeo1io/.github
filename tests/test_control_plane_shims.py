"""Behavioral tests for scripts/control-plane-sync.sh (rm-024).

Cycle-2 validated the hardened script with an ad-hoc /tmp shim matrix; these
tests persist that matrix so the guarantees cannot silently regress:

  1. idempotent no-op    — no changes means exit 0, no commit, back on main
  2. untracked detection — a FRESH data branch (everything untracked) still
                           commits; `git diff --quiet` alone was blind to it
  3. bounded mirror      — the watchdog log is tailed to its env-configured cap
  4. push-failure safety — nonzero exit restores the ENTRY branch (trap)
  5. single-flight lock  — a concurrent holder makes the run exit 0 immediately

Every test builds a throwaway git repo + bare origin and points the script at
them via CONTROL_PLANE_REPO / CONTROL_PLANE_LOCK / CONTROL_PLANE_WATCHDOG_MAX_LINES
and a fixture $HOME — the real fleet checkout is never touched.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "control-plane-sync.sh"


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd, capture_output=True, text=True,
        check=True,
    )


def _fixture_home(tmp_path: Path, watchdog_lines: int = 10) -> Path:
    home = tmp_path / "home"
    (home / ".hermes").mkdir(parents=True)
    (home / ".hermes" / "conductor-tracks.tsv").write_text(
        "repo\tdb\ttoml\nalpha\ta.db\ta.toml\n"
    )
    (home / ".hermes" / "conductor-watchdog-alerts.log").write_text(
        "".join(f"line-{i}\n" for i in range(watchdog_lines))
    )
    return home


def _make_repo(tmp_path: Path, fresh_data: bool = False, reject_push: bool = False) -> tuple[Path, Path]:
    """(repo, origin) pair: repo on `main` with a `data` branch on origin.

    fresh_data=True -> origin's data branch has NO control-plane/ content yet
    (the untracked-files case). reject_push=True -> origin rejects pushes
    (hook installed after setup so only the script's push is rejected).
    """
    origin = tmp_path / "origin.git"
    origin.mkdir()
    _run_git(origin, "init", "-q", "-b", "main", "--bare")
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("fixture\n")
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-qm", "init")
    _run_git(repo, "remote", "add", "origin", str(origin))
    _run_git(repo, "push", "-q", "origin", "main")
    _run_git(repo, "branch", "data")
    if fresh_data:
        # data branch = just the initial commit; control-plane/ is untracked
        _run_git(repo, "push", "-q", "origin", "data")
    else:
        _run_git(repo, "checkout", "-q", "data")
        (repo / "control-plane").mkdir()
        (repo / "control-plane" / "conductor-tracks.tsv").write_text(
            "repo\tdb\ttoml\nold\told.db\told.toml\n"
        )
        _run_git(repo, "add", "-A")
        _run_git(repo, "commit", "-qm", "prior mirror")
        _run_git(repo, "push", "-q", "origin", "data")
        _run_git(repo, "checkout", "-q", "main")
    if reject_push:
        # installed AFTER setup so only the script's mirror push is rejected
        hook = origin / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
    return repo, origin


def _script_env(repo: Path, home: Path, tmp_path: Path, **extra: str) -> dict:
    env = dict(os.environ)
    # pin `date`: the script stamps "# generated $TS" into mirrored artifacts,
    # so two runs straddling a wall-clock second boundary would legitimately
    # differ — a time shim keeps idempotence assertions deterministic
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    if not (bin_dir / "date").exists():
        (bin_dir / "date").write_text('#!/bin/sh\necho "2026-09-21T00:00:00Z"\n')
        (bin_dir / "date").chmod(0o755)
    env.update({
        "HOME": str(home),
        "CONTROL_PLANE_REPO": str(repo),
        "CONTROL_PLANE_LOCK": str(tmp_path / "cp.lock"),
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "PATH": f"{bin_dir}:{env['PATH']}",
    })
    env.update(extra)
    return env


def _data_tree(origin: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(origin), "ls-tree", "-r", "--name-only", "data"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.splitlines()


def _data_show(origin: Path, path: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(origin), "show", f"data:{path}"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout


def test_idempotent_noop_commits_nothing(tmp_path):
    repo, origin = _make_repo(tmp_path)
    home = _fixture_home(tmp_path)
    # first run mirrors the fixtures; second run must be a no-op
    r1 = subprocess.run(["bash", str(SCRIPT)], env=_script_env(repo, home, tmp_path), capture_output=True, text=True)
    assert r1.returncode == 0, r1.stderr
    before = _data_tree(origin)
    r2 = subprocess.run(["bash", str(SCRIPT)], env=_script_env(repo, home, tmp_path), capture_output=True, text=True)
    assert r2.returncode == 0
    assert "no control-plane changes" in r2.stdout
    assert _data_tree(origin) == before
    out = subprocess.run(["git", "-C", str(repo), "branch", "--show-current"],
                         capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "main"


def test_fresh_data_branch_untracked_files_still_commit(tmp_path):
    # the cycle-2 B2 regression: `git diff --quiet` alone is blind to
    # UNTRACKED files, so a fresh data branch silently skipped the mirror
    repo, origin = _make_repo(tmp_path, fresh_data=True)
    home = _fixture_home(tmp_path)
    r = subprocess.run(["bash", str(SCRIPT)], env=_script_env(repo, home, tmp_path), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "pushed control-plane mirror" in r.stdout
    tree = _data_tree(origin)
    assert "control-plane/conductor-tracks.tsv" in tree


def test_watchdog_mirror_is_bounded(tmp_path):
    repo, origin = _make_repo(tmp_path)
    home = _fixture_home(tmp_path, watchdog_lines=10)
    r = subprocess.run(
        ["bash", str(SCRIPT)],
        env=_script_env(repo, home, tmp_path, CONTROL_PLANE_WATCHDOG_MAX_LINES="4"),
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    # the script checks out main at the end; read the mirror from the data branch
    mirrored = _data_show(origin, "control-plane/conductor-watchdog-alerts.log")
    assert mirrored == "line-6\nline-7\nline-8\nline-9\n"


def test_push_failure_restores_entry_branch(tmp_path):
    repo, origin = _make_repo(tmp_path, reject_push=True)
    home = _fixture_home(tmp_path)
    _run_git(repo, "checkout", "-q", "-b", "feature")
    before_tree, before_tip = _data_tree(origin), _run_git(origin, "rev-parse", "data").stdout
    r = subprocess.run(["bash", str(SCRIPT)], env=_script_env(repo, home, tmp_path), capture_output=True, text=True)
    assert r.returncode != 0
    assert "restored checkout to feature" in r.stderr
    branch = subprocess.run(["git", "-C", str(repo), "branch", "--show-current"],
                            capture_output=True, text=True, check=True)
    assert branch.stdout.strip() == "feature"
    # and the failed mirror never landed on origin (tree + tip unchanged)
    assert _data_tree(origin) == before_tree
    assert _run_git(origin, "rev-parse", "data").stdout == before_tip


def test_lock_contention_exits_clean_without_syncing(tmp_path):
    repo, origin = _make_repo(tmp_path)
    home = _fixture_home(tmp_path)
    env = _script_env(repo, home, tmp_path)
    before = _data_tree(origin)
    holder = subprocess.Popen(
        ["flock", env["CONTROL_PLANE_LOCK"], "-c", "sleep 10"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        import time
        time.sleep(0.5)  # let the holder acquire the lock
        r = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)
    finally:
        holder.terminate()
        holder.wait()
    assert r.returncode == 0
    assert "lock held by another run" in r.stderr
    assert _data_tree(origin) == before  # nothing synced behind the lock
