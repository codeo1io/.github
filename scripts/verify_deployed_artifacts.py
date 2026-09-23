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

Exit codes:
  0  verified — wrapper delegates to the pinned repo twin, all entries check
  1  drift (any of the above broken); every drift is printed
  2  deployed artifacts absent — not a deployed host (CI/dev checkout); skip

Env overrides (tests): VERIFY_WRAPPER, VERIFY_MANIFEST, VERIFY_REPO.
"""
from __future__ import annotations

import hashlib
import os
import re
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


def main() -> int:
    drifts: list[str] = []

    if not WRAPPER.exists() or not MANIFEST.exists():
        missing = [str(p) for p in (WRAPPER, MANIFEST) if not p.exists()]
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
