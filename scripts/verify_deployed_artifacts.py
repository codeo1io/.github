#!/usr/bin/env python3
"""Verify deployed fleet artifacts against their pinned digests (rm-042).

The cycle-5 assess proved the failure class this closes: the deployed 08:40
cron wrapper delegated to scripts/sync_data_branch.py while the hardened
scripts/control-plane-sync.sh never ran anywhere — and nothing on the host
could have noticed, because the deployed MANIFEST.sha256 pins 14 fleet
scripts but NEITHER cron-wired sync entrypoint. Repo-side half of the fix:

  1. WRAPPER: the deployed cron wrapper must exist and delegate to a script
     that EXISTS in this repository (a dangling delegation is drift).
  2. DELEGATE PIN: the manifest must pin the delegate's basename, and the
     pinned digest must equal the repository copy's digest — the cron
     executes the repo file, so the manifest is the trust chain for what
     production actually runs.
  3. MANIFEST INTEGRITY: every manifest entry whose file exists must verify
     (sha256), the wrapper itself must be pinned, and pinned-but-missing
     files are drift.

Cycle-6 batch F3 (rm-044) extends the perimeter to the data branch's
CONTENT — the assess proved cron-inventory.json mirrored {} for a day
while the source held 57 jobs, invisible to every existing check:

  4. CONTENT: cron-inventory populated exactly when the host source is,
     watchdog mirror within CONTROL_PLANE_WATCHDOG_MAX_LINES, corrections
     parity against canonical origin/main. Read-only, from any checkout
     with origin fetched (content drift reports rc 1 even on non-hosts).

Exit codes:
  0  verified — wrapper delegates to the pinned repo twin, all entries check
  1  drift (any of the above broken, incl. content violations); every drift
     is printed
  2  deployed artifacts absent AND content clean — not a deployed host
     (CI/dev checkout); skip

Env overrides (tests): VERIFY_WRAPPER, VERIFY_MANIFEST, VERIFY_REPO.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("VERIFY_REPO", Path(__file__).resolve().parents[1]))
WRAPPER = Path(
    os.environ.get(
        "VERIFY_WRAPPER",
        os.path.join(os.path.expanduser("~"), ".hermes", "scripts", "control-plane-sync.sh"),
    )
)
MANIFEST = Path(
    os.environ.get(
        "VERIFY_MANIFEST",
        os.path.join(os.path.expanduser("~"), ".hermes", "scripts", "MANIFEST.sha256"),
    )
)

# sha256sum-style line: <64 hex>  [*]path  (paths may be bare basenames)
ENTRY_RE = re.compile(r"^(?P<digest>[0-9a-f]{64})[ \t]+\*?(?P<name>\S+)$")
# a wrapper delegation into the repo tree, e.g. `python3 scripts/sync_data_branch.py`
DELEGATE_RE = re.compile(r"scripts/(?P<delegate>[A-Za-z0-9_.\-/]+\.(?:py|sh))")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_manifest(text: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = ENTRY_RE.match(line)
        if match is None:
            raise ValueError(f"unparseable manifest line: {line!r}")
        entries[Path(match.group("name")).name] = match.group("digest")
    return entries


def _git_show(ref_path: str) -> "str | None":
    proc = subprocess.run(
        ["git", "-C", str(REPO), "show", ref_path],
        capture_output=True,
        text=True,
    )
    return proc.stdout if proc.returncode == 0 else None


def check_data_branch_content() -> "list[str]":
    """rm-044 (cycle-6 batch F3): the data branch's CONTENT, not just the
    deployed host artifacts, is part of the trust chain. The cycle-6 assess
    proved the silent-empty-mirror class: cron-inventory.json carried {}
    for a day (57 jobs in the source, dict-vs-list parsing bug) and nothing
    anywhere could see it. Read-only; needs the origin remote-tracking refs
    (any fetched checkout, host or not)."""
    violations: list[str] = []

    inventory: "dict | None" = None
    inv_raw = _git_show("origin/data:control-plane/cron-inventory.json")
    if inv_raw is None:
        violations.append(
            "data-branch: control-plane/cron-inventory.json not reachable (fetch origin?)"
        )
    else:
        body = "\n".join(
            line for line in inv_raw.splitlines() if not line.lstrip().startswith("#")
        )
        try:
            inventory = json.loads(body) if body.strip() else {}
        except json.JSONDecodeError:
            violations.append("data-branch: cron-inventory.json is not valid JSON")

    if inventory is not None:
        # iff-check is host-side only: without a local jobs.json there is no
        # source of truth to compare against
        jobs_path = Path.home() / ".hermes" / "cron" / "jobs.json"
        if jobs_path.exists():
            try:
                raw = json.loads(jobs_path.read_text())
            except (json.JSONDecodeError, OSError):
                raw = None
                violations.append(
                    "host: cron jobs.json unreadable — inventory iff-check skipped"
                )
            if raw is not None:
                candidate = (
                    raw.get("jobs", [])
                    if isinstance(raw, dict)
                    else (raw if isinstance(raw, list) else [])
                )
                src_jobs = [
                    j for j in candidate if isinstance(j, dict) and "id" in j
                ]
                if src_jobs and not inventory:
                    violations.append(
                        f"data-branch: cron-inventory.json is EMPTY while jobs.json "
                        f"holds {len(src_jobs)} jobs (silent mirror regression)"
                    )
                if not src_jobs and inventory:
                    violations.append(
                        "data-branch: cron-inventory.json holds stale jobs while "
                        "jobs.json is empty"
                    )

    wd_raw = _git_show("origin/data:control-plane/conductor-watchdog-alerts.log")
    if wd_raw is not None:
        cap = int(os.environ.get("CONTROL_PLANE_WATCHDOG_MAX_LINES", "5000"))
        n_lines = len(wd_raw.splitlines())
        if n_lines > cap:
            violations.append(
                f"data-branch: watchdog mirror is {n_lines} lines, exceeds cap {cap}"
            )

    corr_data = _git_show("origin/data:control-plane/corrections.yaml")
    corr_main = _git_show("origin/main:control-plane/corrections.yaml")
    if corr_data is None:
        violations.append("data-branch: corrections.yaml not reachable")
    elif corr_main is not None and corr_data != corr_main:
        violations.append(
            "data-branch: corrections.yaml diverges from canonical origin/main"
        )

    return violations


def main() -> int:
    drifts: list[str] = []
    violations = check_data_branch_content()

    if not WRAPPER.exists() or not MANIFEST.exists():
        missing = [str(p) for p in (WRAPPER, MANIFEST) if not p.exists()]
        # content drift outranks "not a deployed host": it is visible from
        # ANY fetched checkout and must never hide behind the rc=2 skip
        if violations:
            for violation in violations:
                print(f"DRIFT: {violation}", file=sys.stderr)
            print(
                f"data-branch content verification FAILED "
                f"({len(violations)} violation/s)",
                file=sys.stderr,
            )
            return 1
        print(f"deployed artifacts absent ({', '.join(missing)}); skipping")
        return 2

    wrapper_text = WRAPPER.read_text()
    delegate_match = DELEGATE_RE.search(wrapper_text)
    if delegate_match is None:
        print(
            f"DRIFT: wrapper {WRAPPER} does not delegate to a scripts/ entrypoint",
            file=sys.stderr,
        )
        return 1
    delegate_name = delegate_match.group("delegate")
    delegate_repo_path = REPO / "scripts" / delegate_name
    if not delegate_repo_path.exists():
        print(
            f"DRIFT: wrapper delegates to scripts/{delegate_name} but that file "
            f"does not exist in {REPO}",
            file=sys.stderr,
        )
        return 1

    try:
        entries = parse_manifest(MANIFEST.read_text())
    except (OSError, ValueError) as exc:
        print(f"DRIFT: manifest unreadable: {exc}", file=sys.stderr)
        return 1

    manifest_dir = MANIFEST.parent
    for name, pinned in sorted(entries.items()):
        if name == delegate_name:
            target = delegate_repo_path  # the cron executes the repo copy
        else:
            target = manifest_dir / name
        if not target.exists():
            drifts.append(f"{name}: pinned but missing ({target})")
            continue
        actual = sha256_of(target)
        if actual != pinned:
            drifts.append(f"{name}: digest mismatch (pinned {pinned[:12]}…, actual {actual[:12]}…)")

    wrapper_entry = WRAPPER.name
    for required in (wrapper_entry, delegate_name):
        if required not in entries:
            drifts.append(f"{required}: not pinned in manifest (cron-wired entrypoint unpinned)")

    drifts.extend(violations)

    if drifts:
        for drift in drifts:
            print(f"DRIFT: {drift}", file=sys.stderr)
        print(
            f"deployed-artifact verification FAILED ({len(drifts)} drift/s); "
            f"wrapper={WRAPPER.name} -> scripts/{delegate_name}",
            file=sys.stderr,
        )
        return 1

    print(
        f"deployed artifacts verified ({len(entries)} pinned; "
        f"wrapper={WRAPPER.name} -> scripts/{delegate_name})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
