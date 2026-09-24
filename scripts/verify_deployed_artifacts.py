#!/usr/bin/env python3
"""Verify deployed fleet artifacts against their pinned digests (rm-042).

The cycle-5 assess proved the failure class this closes: the deployed 08:40
cron wrapper delegated to scripts/sync_data_branch.py while the hardened
scripts/control-plane-sync.sh never ran anywhere — and nothing on the host
could have noticed, because the deployed MANIFEST.sha256 pins 14 fleet
scripts but NEITHER cron-wired sync entrypoint. Repo-side half of the fix:

  1. WRAPPER: the deployed cron wrapper must exist and delegate to a script
     that EXISTS in this repository (a dangling delegation is drift).
  1b. AUXILIARY WRAPPERS: every *.sh in the manifest directory whose
     delegation RESOLVES INTO THIS REPO (e.g. the repo-settings wrapper,
     which execs both check_known_hosts.py and sync_repo_settings.py) gets
     the same treatment — pinned, and each of our delegates it names pinned
     against the repo copy. Wrappers referencing other repos' scripts/
     (the fleet dir hosts dozens) are out of scope by construction.
  2. DELEGATE PIN: the manifest must pin the delegate's basename, and the
     pinned digest must equal the repository copy's digest — the cron
     executes the repo file, so the manifest is the trust chain for what
     production actually runs.
  3. MANIFEST INTEGRITY: every manifest entry whose file exists must verify
     (sha256), the wrapper itself must be pinned, and pinned-but-missing
     files are drift.

Exit codes:
  0  verified — wrapper delegates to the pinned repo twin, all entries check
  1  drift (any of the above broken); every drift is printed. A HALF-
      DEPLOYED PAIR IS DRIFT, NOT A SKIP: a present wrapper with a missing
      manifest (or vice versa) silently disables the trust chain exactly
      where it matters (cycle-7 assess P2) — only BOTH absent is a skip.
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


def discover_delegating_wrappers(scripts_dir: Path, repo: Path) -> list[tuple[Path, list[str]]]:
    """Deployed *.sh wrappers in scripts_dir delegating into THIS repo.

    The control-plane wrapper is not the only cron-wired entrypoint: the
    repo-settings wrapper execs repo scripts the same way. The deployed
    directory also hosts dozens of fleet scripts that reference OTHER
    repos' scripts/ trees — those are out of scope, so a delegation only
    counts when the named script exists under repo/scripts/ (each wrapper
    may name several; all of ours get the pin + digest contract).
    """
    found: list[tuple[Path, list[str]]] = []
    for path in sorted(scripts_dir.glob("*.sh")):
        try:
            text = path.read_text()
        except OSError:
            continue
        ours = sorted(
            {
                match.group("delegate")
                for match in DELEGATE_RE.finditer(text)
                if (repo / "scripts" / match.group("delegate")).exists()
            }
        )
        if ours:
            found.append((path, ours))
    return found


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

    # rc 2 ("not a deployed host") is ONLY true when BOTH halves of the
    # deployed pair are absent. A present wrapper with a missing manifest
    # (or the converse) is a half-deployed host whose trust chain cannot be
    # verified — grading that a skip would silently disable verification
    # exactly on the host where it matters (cycle-7 assess P2).
    if not WRAPPER.exists() and not MANIFEST.exists():
        print(f"deployed artifacts absent ({WRAPPER}, {MANIFEST}); skipping")
        return 2
    if not WRAPPER.exists():
        print(
            f"DRIFT: manifest present but configured wrapper missing: {WRAPPER}",
            file=sys.stderr,
        )
        return 1
    if not MANIFEST.exists():
        print(
            f"DRIFT: deployed wrapper present but {MANIFEST} missing — "
            "the deployed trust chain is unverifiable",
            file=sys.stderr,
        )
        return 1

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

    # auxiliary wrappers whose delegation resolves INTO this repo get the
    # primary's contract: pinned, and each of our delegates named in them
    # pinned against the REPO copy (the cron executes the repo file, not a
    # deployed twin). Wrappers naming only other repos' scripts are ignored.
    delegates: dict[str, Path] = {delegate_name: delegate_repo_path}
    aux_wrappers: list[tuple[Path, list[str]]] = []
    for aux_path, aux_ours in discover_delegating_wrappers(manifest_dir, REPO):
        if aux_path.resolve() == WRAPPER.resolve():
            continue  # primary, handled above
        aux_wrappers.append((aux_path, aux_ours))
        for aux_delegate in aux_ours:
            delegates.setdefault(
                aux_delegate, REPO / "scripts" / aux_delegate
            )

    for name, pinned in sorted(entries.items()):
        if name in delegates:
            target = delegates[name]  # the cron executes the repo copy
        else:
            target = manifest_dir / name
        if not target.exists():
            drifts.append(f"{name}: pinned but missing ({target})")
            continue
        actual = sha256_of(target)
        if actual != pinned:
            drifts.append(f"{name}: digest mismatch (pinned {pinned[:12]}…, actual {actual[:12]}…)")

    for required in (WRAPPER.name, delegate_name):
        if required not in entries:
            drifts.append(f"{required}: not pinned in manifest (cron-wired entrypoint unpinned)")
    for aux_path, aux_ours in aux_wrappers:
        if aux_path.name not in entries:
            drifts.append(f"{aux_path.name}: not pinned in manifest (delegating wrapper unpinned)")
        for aux_delegate in aux_ours:
            if aux_delegate not in entries:
                drifts.append(f"{aux_delegate}: not pinned in manifest (cron-wired entrypoint unpinned)")

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
