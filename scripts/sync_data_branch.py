#!/usr/bin/env python3
"""Sync fleet control-plane state to the codeo1io/.github `data` branch.

This is the SINGLE executed implementation of the control-plane mirror
(cycle-5 batch E1, rm-017/rm-019): the daily 08:40 cron job runs the
deployed wrapper (HOME/.hermes/scripts/control-plane-sync.sh), which execs
THIS file from the canonical checkout — so every hardening property must
live here. The cycle-2 B2 hardened twin (scripts/control-plane-sync.sh) was
never deployed and is retired by the same batch; its properties were ported:

  * flock single-flight  — a concurrent run exits 0 immediately
  * entry-branch restore — any exit (success or failure) restores the
                           branch we started on; only a restore failure
                           is louder than the run itself
  * bounded watchdog     — the mirrored alert log is tailed to
                           CONTROL_PLANE_WATCHDOG_MAX_LINES (default 5000);
                           the source log stays the record, and the tail is
                           streamed through a bounded deque (never fully
                           materialized)
  * stage-before-diff    — untracked files count as changes (a bare
                           `git diff --quiet` was blind to a fresh data
                           branch), but staging is ALLOWLISTED to the exact
                           copy-set written this run — `git add control-plane`
                           would sweep any untracked operator file onto the
                           PUBLIC data branch (cycle-7 assess)
  * bounded subprocesses — every git call gets a timeout; expiry
                           synthesizes rc=124 and fails the run loudly
                           instead of hanging the cron slot

Copy-set (parity with the retired twin + cycle-5/7 closure): conductor-tracks,
watchdog alerts (bounded), kanban OWNERS for t_acd6a2e8 AND t_851e7951,
generated cron/runners inventories, and control-plane/corrections.yaml AND
control-plane/claims.yaml mirrored from the canonical main-tree copy
(origin/main) so the data branch can never carry a stale correction or
claim again (cycle-7 F1h: claims.yaml is the same class as corrections).

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
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

REPO = os.environ.get("CONTROL_PLANE_REPO", "/work/projects/.github")
DATA_BRANCH = "data"
MAIN_BRANCH = "main"
CANONICAL_REF = os.environ.get("CONTROL_PLANE_CANONICAL_REF", "origin/main")
LOCK_FILE = os.environ.get("CONTROL_PLANE_LOCK", "/tmp/control-plane-sync.lock")
WATCHDOG_MAX_LINES = int(os.environ.get("CONTROL_PLANE_WATCHDOG_MAX_LINES", "5000"))
GIT_TIMEOUT = int(os.environ.get("CONTROL_PLANE_GIT_TIMEOUT", "60"))
VERIFY_MAX_LINES = int(os.environ.get("CONTROL_PLANE_VERIFY_MAX_LINES", "200"))
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
    """Copy the last WATCHDOG_MAX_LINES lines of src to dst; source is the record.

    Streams through a bounded deque — the source alert log grows without
    bound on the ops host and must never be fully materialized in memory
    just to keep a tail (cycle-7 assess: readlines() loaded the whole log).
    """
    with open(src, "r", errors="replace") as fh:
        tail = deque(fh, maxlen=WATCHDOG_MAX_LINES)
    dst.write_text("".join(tail))


def run_deployed_verify() -> tuple[int, str]:
    """Report-only deployed-artifact check (cycle-8 rm-048).

    Runs BEFORE the data branch is checked out so the digest comparison
    sees the ENTRY-branch (canonical) copies of the scripts the crons exec
    — comparing after the switch would grade the data-branch seed. Any
    outcome is journaled, never a wedged mirror.
    """
    script = Path(__file__).resolve().parent / "verify_deployed_artifacts.py"
    try:
        res = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, f"verify-unavailable({exc})"
    drift_names = sorted(
        {
            line.split("DRIFT:", 1)[1].split(":", 1)[0].strip()
            for line in (res.stdout + res.stderr).splitlines()
            if line.startswith("DRIFT:")
        }
    )
    if drift_names:
        return res.returncode, "drift=" + ",".join(drift_names)
    if res.returncode == 0:
        return 0, "clean"
    if res.returncode == 2:
        return 2, "not-a-deployed-host"
    return res.returncode, "unrecognized"


def _restore(restore_branch: str) -> None:
    res = git("checkout", restore_branch)
    if res.returncode == 0:
        print(f"restored checkout to {restore_branch}", file=sys.stderr)
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
        # deployed-artifact trust check (cycle-8 rm-048): run while the
        # worktree still holds the entry (canonical) branch — see
        # run_deployed_verify for why the pre-checkout timing matters
        verify_rc, verify_note = run_deployed_verify()
        # fetch failure tolerated (first boot: no remote data ref yet)
        git("fetch", "origin", DATA_BRANCH)
        has_remote = (
            git("show-ref", "--verify", "--quiet", f"refs/remotes/origin/{DATA_BRANCH}").returncode == 0
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
        # allowlist: EXACTLY the files written this run get staged (cycle-7
        # F1b) — anything else found under control-plane/ stays untracked
        mirrored: list[str] = [
            "control-plane/conductor-tracks.tsv",
            "control-plane/conductor-watchdog-alerts.log",
        ]

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
                mirrored.append(f"control-plane/kanban-{tid}-OWNERS.md")
            else:
                # optional today, parity copy: warn, never wedge the mirror
                print(
                    f"control-plane-sync: kanban {tid} OWNERS.md absent; skipping",
                    file=sys.stderr,
                )

        # corrections.yaml + claims.yaml: canonical copies are tracked on
        # main; mirror them onto data so the branch can never retain a stale
        # correction/claim (the cycle-5 assess found the data corrections
        # copy predating the B3/D4 amendments — no previous sync path copied
        # it; cycle-7 F1h closes the identical claims.yaml gap).
        for ledger in ("corrections.yaml", "claims.yaml"):
            res = git("show", f"{CANONICAL_REF}:control-plane/{ledger}")
            if res.returncode == 0:
                Path("control-plane").joinpath(ledger).write_text(res.stdout)
                mirrored.append(f"control-plane/{ledger}")
            else:
                print(
                    f"control-plane-sync: no {ledger} on {CANONICAL_REF}; skipping",
                    file=sys.stderr,
                )

        # cron inventory (regenerated each run, ts-stamped). The host's
        # ~/.hermes/cron/jobs.json is a top-level dict {"jobs": [...]} — a
        # legacy host (or hand-edited file) may carry the bare list shape;
        # accept BOTH. The canary makes the cycle-6/8 silent-empty mirror
        # impossible: a missing/unreadable/shapeless/empty jobs source
        # aborts the run LOUDLY instead of publishing an empty public
        # inventory (rm-046; the parse bug iterated the dict's string keys
        # and produced {} daily from 9f94762 onward).
        jobs_path = home / ".hermes" / "cron" / "jobs.json"
        if not jobs_path.exists():
            raise SyncError(
                "cron-inventory canary: ~/.hermes/cron/jobs.json is missing "
                "— refusing to publish an empty cron-inventory.json "
                "(cycle-8 rm-046)"
            )
        try:
            payload = json.loads(jobs_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            raise SyncError(f"cron-inventory canary: jobs.json unreadable: {exc}")
        job_list = payload.get("jobs") if isinstance(payload, dict) else payload
        if not isinstance(job_list, list):
            raise SyncError(
                'cron-inventory canary: jobs.json is neither {"jobs": [...]} '
                "nor a bare list — refusing to publish an empty "
                "cron-inventory.json"
            )
        jobs = {
            job["id"]: {
                "name": job.get("name", job["id"]),
                "schedule": job.get("schedule", ""),
                "enabled": job.get("enabled", True),
            }
            for job in job_list
            if isinstance(job, dict) and "id" in job
        }
        if not jobs:
            raise SyncError(
                "cron-inventory canary: parsed 0 jobs from jobs.json — "
                "refusing to publish an empty cron-inventory.json (the "
                "silent-empty regression class of cycle-6/8)"
            )
        Path("control-plane").joinpath("cron-inventory.json").write_text(
            f"# generated {ts}\n# {len(jobs)} jobs\n"
            + json.dumps(jobs, indent=2, sort_keys=True)
            + "\n"
        )
        mirrored.append("control-plane/cron-inventory.json")

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
        mirrored.append("control-plane/runners.txt")

        # manifest-verify journal (cycle-8 rm-048): the daily run proves the
        # deployed-artifact contract and records every STATE CHANGE (clean
        # -> drift -> clean) on the public data branch, so a red trust chain
        # is visible to anyone reading origin/data. Deduped on (rc, note) —
        # an unchanged state must not create a diff or the no-op fast path
        # dies and every run commits noise. Report-only by design.
        journal = Path("control-plane") / "manifest-verify.log"
        journal_lines = journal.read_text().splitlines() if journal.exists() else []
        if not journal_lines or not journal_lines[-1].endswith(
            f"rc={verify_rc} {verify_note}"
        ):
            journal_lines.append(f"{ts} rc={verify_rc} {verify_note}")
            print(f"control-plane-sync: manifest-verify {verify_rc} {verify_note}")
        journal.write_text("\n".join(journal_lines[-VERIFY_MAX_LINES:]) + "\n")
        mirrored.append("control-plane/manifest-verify.log")

        # stage FIRST (allowlisted to the copy-set), then test the STAGED
        # diff: untracked files count as changes — but ONLY the ones we
        # wrote. A blanket `git add control-plane` would commit any
        # untracked operator file onto the PUBLIC data branch.
        must(git("add", "--", *mirrored), "add control-plane copy-set")
        if git("diff", "--staged", "--quiet").returncode == 0:
            print("no control-plane changes")
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
        must(git("checkout", restore), f"checkout {restore}")
        return 0
    except (SyncError, OSError) as exc:
        print(f"control-plane-sync: FAILED: {exc}", file=sys.stderr)
        _restore(restore)
        return 1


if __name__ == "__main__":
    sys.exit(main())
