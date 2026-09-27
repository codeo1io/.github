#!/usr/bin/env python3
"""Sync fleet control-plane state to the codeo1io/.github `data` branch.

This is the SINGLE executed implementation of the control-plane mirror
(cycle-5 batch E1, rm-017/rm-019): the daily 08:40 cron job runs the
deployed wrapper (HOME/.hermes/scripts/control-plane-sync.sh), which execs
THIS file from the canonical checkout — so every hardening property must
live here. The cycle-2 B2 hardened twin (scripts/control-plane-sync.sh) was
never deployed and is retired by the same batch; its properties were ported:

  * flock single-flight  — a concurrent run exits 0 immediately
  * entry-branch restore — any failure restores the branch we started on
  * bounded watchdog     — the mirrored alert log is tailed to
                           CONTROL_PLANE_WATCHDOG_MAX_LINES (default 5000);
                           the source log stays the record
  * stage-before-diff    — untracked files count as changes (a bare
                           `git diff --quiet` was blind to a fresh data
                           branch)
  * bounded subprocesses — every git call gets a timeout; expiry
                           synthesizes rc=124 and fails the run loudly
                           instead of hanging the cron slot

Copy-set (parity with the retired twin + cycle-5 closure): conductor-tracks,
watchdog alerts (bounded), kanban OWNERS for t_acd6a2e8 AND t_851e7951,
generated cron/runners inventories, and control-plane/corrections.yaml
mirrored from the canonical main-tree copy (origin/main) so the data branch
can never carry a stale corrections claim again.

Env overrides (used by tests/test_control_plane_shims.py):
CONTROL_PLANE_REPO, CONTROL_PLANE_LOCK, CONTROL_PLANE_WATCHDOG_MAX_LINES,
CONTROL_PLANE_GIT_TIMEOUT, CONTROL_PLANE_CANONICAL_REF.
"""
from __future__ import annotations

import fcntl
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = os.environ.get("CONTROL_PLANE_REPO", "/work/projects/.github")
DATA_BRANCH = "data"
MAIN_BRANCH = "main"
CANONICAL_REF = os.environ.get("CONTROL_PLANE_CANONICAL_REF", "origin/main")
LOCK_FILE = os.environ.get("CONTROL_PLANE_LOCK", "/tmp/control-plane-sync.lock")
WATCHDOG_MAX_LINES = int(os.environ.get("CONTROL_PLANE_WATCHDOG_MAX_LINES", "5000"))
GIT_TIMEOUT = int(os.environ.get("CONTROL_PLANE_GIT_TIMEOUT", "60"))
KANBAN_OWNERS = ("t_acd6a2e8", "t_851e7951")


class SyncError(Exception):
    """A git step failed (nonzero rc, or rc=124 synthesized on timeout)."""


def git(*args: str) -> subprocess.CompletedProcess:
    """Run `git -C REPO` with a hard timeout; rc=124 on expiry, never raises."""
    try:
        return subprocess.run(
            ["git", "-C", REPO, *args],
            capture_output=True, text=True, timeout=GIT_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        print(
            f"control-plane-sync: git {args[0]} timed out after {GIT_TIMEOUT}s",
            file=sys.stderr,
        )
        return subprocess.CompletedProcess(["git", *args], 124, "", str(exc))


def must(res: subprocess.CompletedProcess, label: str) -> str:
    if res.returncode != 0:
        raise SyncError(f"{label} rc={res.returncode}: {res.stderr.strip()}")
    return res.stdout


def mirror_bounded(src: Path, dst: Path) -> None:
    """Copy the last WATCHDOG_MAX_LINES lines of src to dst; source is the record."""
    with open(src, "r", errors="replace") as fh:
        lines = fh.readlines()
    dst.write_text("".join(lines[-WATCHDOG_MAX_LINES:]))


def _restore(restore_branch: str) -> None:
    # cycle-6 rm-045: the failed attempt may have left control-plane files
    # staged (failure between `git add` and `git commit`); a branch-only
    # restore kept that residue staged ON the restored branch — and staged
    # edits could even block the switch itself. Clear index+tree first
    # (best effort, current branch), switch, then reset again so the
    # restored branch is exactly as found. Runs start from a clean canonical
    # checkout (AGENTS hardening contract), so this only ever discards the
    # mirror's own half-written state.
    git("reset", "--hard", "HEAD")  # best effort: clear staged mirror edits
    res = git("checkout", restore_branch)
    if res.returncode == 0:
        print(f"restored checkout to {restore_branch}", file=sys.stderr)
        if git("reset", "--hard", "HEAD").returncode != 0:
            print("RESTORE WARNING: index reset failed on restored branch", file=sys.stderr)
    else:
        current = git("branch", "--show-current").stdout.strip() or "detached HEAD"
        print(f"RESTORE FAILED, still on {current}", file=sys.stderr)


def main() -> int:
    lock_fd = os.open(LOCK_FILE, os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("control-plane-sync: lock held by another run; exiting", file=sys.stderr)
        return 0

    os.chdir(REPO)
    restore = MAIN_BRANCH  # until the entry branch is known
    try:
        entry = must(git("branch", "--show-current"), "branch --show-current").strip()
        restore = entry if entry and entry != DATA_BRANCH else MAIN_BRANCH
        # fetch failure tolerated (first boot: no remote data ref yet)
        fetch_ok = git("fetch", "origin", DATA_BRANCH).returncode == 0
        has_remote = (
            git("show-ref", "--verify", "--quiet", f"refs/remotes/origin/{DATA_BRANCH}").returncode == 0
        )
        if not fetch_ok:
            # cycle-6 rm-045: fetch_ok was assigned and never used — a failed
            # fetch proceeded silently against the stale remote-tracking ref.
            # The push still fails loudly on a diverged remote (non-FF), but
            # the operator now SEES why the run worked from stale state.
            print(
                "control-plane-sync: WARNING: fetch origin/data failed — "
                "proceeding against the last known remote-tracking ref; a "
                "diverged remote will reject the push and restore the entry branch",
                file=sys.stderr,
            )
        if git("checkout", DATA_BRANCH).returncode != 0:
            if has_remote:
                must(
                    git("checkout", "-b", DATA_BRANCH, f"origin/{DATA_BRANCH}"),
                    f"checkout -b {DATA_BRANCH}",
                )
            else:
                # first boot: seed the data branch from the current checkout
                must(git("checkout", "-b", DATA_BRANCH), f"checkout -b {DATA_BRANCH}")
        elif has_remote:
            must(git("reset", "--hard", f"origin/{DATA_BRANCH}"), "reset --hard")

        os.makedirs("control-plane", exist_ok=True)
        home = Path.home()
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        shutil.copyfile(
            home / ".hermes" / "conductor-tracks.tsv",
            "control-plane/conductor-tracks.tsv",
        )
        mirror_bounded(
            home / ".hermes" / "conductor-watchdog-alerts.log",
            Path("control-plane") / "conductor-watchdog-alerts.log",
        )

        for tid in KANBAN_OWNERS:
            src = home / ".hermes" / "kanban" / "attachments" / tid / "OWNERS.md"
            if src.exists():
                shutil.copyfile(
                    src, f"control-plane/kanban-{tid}-OWNERS.md"
                )
            else:
                # optional today, parity copy: warn, never wedge the mirror
                print(
                    f"control-plane-sync: kanban {tid} OWNERS.md absent; skipping",
                    file=sys.stderr,
                )

        # corrections.yaml: canonical copy is tracked on main; mirror it onto
        # data so the branch can never retain a stale corrections claim
        # (the cycle-5 assess found the data copy predating the B3/D4
        # amendments — no previous sync path copied it).
        corr = git("show", f"{CANONICAL_REF}:control-plane/corrections.yaml")
        if corr.returncode == 0:
            corr_dest = Path("control-plane").joinpath("corrections.yaml")
            corr_dest.write_text(corr.stdout)
            # rm-044 write-fidelity self-check: the mirrored copy must be
            # exactly the canonical bytes — the data branch must never
            # carry a stale or truncated corrections claim.
            if corr_dest.read_text() != corr.stdout:
                raise SyncError(
                    "corrections parity: mirrored copy differs from the "
                    f"canonical {CANONICAL_REF} copy"
                )
        else:
            print(
                f"control-plane-sync: no corrections.yaml on {CANONICAL_REF}; skipping",
                file=sys.stderr,
            )

        # cron inventory (regenerated each run, ts-stamped)
        # cycle-6 rm-019: production jobs.json is a top-level OBJECT
        # {"jobs": [...], "updated_at": ...} (57 jobs live on the fleet
        # host). The list-only comprehension below iterated that dict as a
        # list, silently dropped every job, and mirrored {} for a day
        # (since 9f94762, proven by the cycle-6 assess). Accept the object
        # shape first, keep list tolerance for legacy sources, and fail
        # CLOSED when a non-empty source yields an empty inventory.
        raw_jobs: list = []
        jobs: dict = {}
        jobs_path = home / ".hermes" / "cron" / "jobs.json"
        if jobs_path.exists():
            try:
                raw = json.loads(jobs_path.read_text())
            except (json.JSONDecodeError, OSError) as exc:
                # a corrupt/unreadable source must fail the run — the old
                # warn-and-continue path OVERWROTE the last known mirror
                # with {}, the exact silent-loss class rm-044 guards
                raise SyncError(f"cron jobs.json unreadable: {exc}") from exc
            if isinstance(raw, dict):
                candidate = raw.get("jobs", [])
                raw_jobs = candidate if isinstance(candidate, list) else []
            elif isinstance(raw, list):
                raw_jobs = raw
            jobs = {
                job["id"]: {
                    "name": job.get("name", job["id"]),
                    "schedule": job.get("schedule", ""),
                    "enabled": job.get("enabled", True),
                }
                for job in raw_jobs
                if isinstance(job, dict) and "id" in job
            }
            # rm-044 content self-check: a non-empty source MUST yield a
            # non-empty inventory. Its absence is what let the regression
            # ship {} invisibly; any future shape/parsing bug now fails the
            # run loudly (entry branch restored) instead.
            if raw_jobs and not jobs:
                raise SyncError(
                    "cron-inventory integrity: non-empty jobs.json produced "
                    "an empty inventory (shape/parsing regression) — refusing "
                    "to mirror {}"
                )
        Path("control-plane").joinpath("cron-inventory.json").write_text(
            f"# generated {ts}\n" + json.dumps(jobs, indent=2, sort_keys=True) + "\n"
        )

        # runners inventory (regenerated each run, ts-stamped)
        runners_root = home / "runners"
        runner_names = (
            sorted(p.parent.name for p in runners_root.glob("*/.runner"))
            if runners_root.exists()
            else []
        )
        Path("control-plane").joinpath("runners.txt").write_text(
            f"# generated {ts}\n" + ("\n".join(runner_names) + "\n" if runner_names else "")
        )

        # stage FIRST, then test the STAGED diff: untracked files count
        # (`git diff --quiet` alone was blind to a fresh data branch)
        must(git("add", "control-plane"), "add control-plane")
        if git("diff", "--staged", "--quiet").returncode == 0:
            print("no control-plane changes")
            # cycle-6 rm-045: success restores the ENTRY branch, not
            # unconditionally main — a manual run from any branch must
            # find its checkout where it left it
            must(git("checkout", restore), f"checkout {restore}")
            return 0

        names = must(
            git("diff", "--staged", "--name-only"), "diff --staged --name-only"
        ).splitlines()
        must(
            git(
                "-c", "user.name=fleet-bot",
                "-c", "user.email=fleet-bot@users.noreply.github.com",
                "commit", "-m", f"chore(control-plane): mirror fleet state {ts}",
            ),
            "commit",
        )
        must(git("push", "origin", DATA_BRANCH), f"push origin {DATA_BRANCH}")
        print(f"pushed control-plane mirror {ts} ({len(names)} files)")
        # cycle-6 rm-045: entry branch, not unconditionally main (see above)
        must(git("checkout", restore), f"checkout {restore}")
        return 0
    except (SyncError, OSError) as exc:
        print(f"control-plane-sync: FAILED: {exc}", file=sys.stderr)
        _restore(restore)
        return 1


if __name__ == "__main__":
    sys.exit(main())
