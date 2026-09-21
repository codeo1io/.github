#!/usr/bin/env python3
"""Verify pinned SSH host keys in ~/.ssh/known_hosts against GitHub's published
fingerprints (https://api.github.com/meta). Exit 1 on missing/mismatched keys.

The pinned set per algorithm must EXACTLY match GitHub's published keys: ssh
accepts ANY pinned key for a host, so a stale or extra same-algorithm entry is
as dangerous as a wrong one (silent MITM window) and must FAIL, not pass.

Checks github.com AND the ssh.github.com:443 fallback (blocked-port escape
hatch) — an unpinned fallback host would silently bypass this check.

Catches silent host-key rotation drift and MITM. Run daily (wired into the
repo-settings-sync cron) and manually after any connectivity incident.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.request

KNOWN_HOSTS = "/home/agent/.ssh/known_hosts"
# Non-default ports are written/matched in known_hosts as "[host]:port".
HOSTS = ["github.com", "[ssh.github.com]:443"]


def meta_fingerprints() -> dict:
    with urllib.request.urlopen("https://api.github.com/meta", timeout=10) as r:
        return json.load(r)["ssh_key_fingerprints"]


def _ssh_keygen(*args: str) -> subprocess.CompletedProcess:
    """Bounded ssh-keygen (fleet rule: every subprocess call gets a timeout).
    On timeout, synthesize rc=124 with empty stdout so callers grade it through
    their existing missing/empty paths (checker fails safe: treated as no pins).
    """
    try:
        return subprocess.run(
            ["ssh-keygen", *args], capture_output=True, text=True, timeout=10
        )
    except subprocess.TimeoutExpired:
        print(f"warn: ssh-keygen {' '.join(args)} timed out", file=sys.stderr)
        return subprocess.CompletedProcess(["ssh-keygen", *args], 124, "", "timed out")


def known_fingerprints(host: str) -> dict[str, set[str]]:
    """Every pinned fingerprint per algorithm for host — ALL same-type keys.

    ssh-keygen -F prints one line per pinned key; keeping only one per
    algorithm (the old last-key-wins dict) hid stale duplicates from the
    comparison below. ssh-keygen -lf needs a file, so matches go through a
    temp file that is ALWAYS unlinked (the old delete=False leaked one
    /tmp/*.kh per run).
    """
    r = _ssh_keygen("-F", host, "-f", KNOWN_HOSTS)
    lines = [l for l in r.stdout.splitlines() if l and not l.startswith("#")]
    if not lines:
        return {}
    fd, path = tempfile.mkstemp(suffix=".kh")
    try:
        with os.fdopen(fd, "w") as t:
            t.write("\n".join(lines) + "\n")
        lf = _ssh_keygen("-lf", path).stdout
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
    out: dict[str, set[str]] = {}
    for line in lf.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[1].startswith("SHA256:"):
            out.setdefault(parts[-1].strip("()"), set()).add(parts[1])
    return out


def main() -> int:
    fail = False
    try:
        meta_raw = meta_fingerprints()
    except Exception as exc:  # noqa: BLE001
        print(f"FATAL: cannot fetch api.github.com/meta: {exc}")
        return 1
    # meta keys look like "SHA256_ED25519" -> {"ED25519": "SHA256:..."}.
    # Derived dynamically so a new GitHub algorithm is checked the day meta
    # publishes it, and a dropped one fails stale pins instead of skipping.
    want: dict[str, str] = {}
    for k, v in meta_raw.items():
        if not k.startswith("SHA256_"):
            continue
        want[k[len("SHA256_"):]] = v if v.startswith("SHA256:") else "SHA256:" + v

    for host in HOSTS:
        have = known_fingerprints(host)
        if not have:
            print(f"{host}: FAIL no pinned keys in {KNOWN_HOSTS}")
            fail = True
            continue
        # Pinned algorithms GitHub no longer publishes: stale keys ssh still
        # accepts — fail them rather than silently trusting.
        for algo in sorted(set(have) - set(want)):
            print(f"{host}: FAIL {algo} STALE ALGORITHM pinned {sorted(have[algo])} — "
                  f"not in api.github.com/meta ({sorted(want)}); do NOT ssh")
            fail = True
        for algo, meta_fp in sorted(want.items()):
            got = have.get(algo, set())
            if not got:
                print(f"{host}: FAIL MISSING {algo} key (expected {meta_fp})")
                fail = True
            elif meta_fp not in got:
                print(f"{host}: FAIL {algo} MISMATCH have={sorted(got)} want={meta_fp} — treat as possible MITM, do NOT ssh")
                fail = True
            elif got != {meta_fp}:
                print(f"{host}: FAIL {algo} STALE/EXTRA pinned {sorted(got - {meta_fp})} alongside {meta_fp} — "
                      f"ssh accepts ANY pinned key; treat as possible MITM, do NOT ssh")
                fail = True
            else:
                print(f"{host}: OK {algo} {meta_fp}")
    print("RESULT: " + ("FAIL" if fail else "OK"))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
