#!/usr/bin/env python3
"""Verify pinned SSH host keys in ~/.ssh/known_hosts against GitHub's published
fingerprints (https://api.github.com/meta). Exit 1 on missing/mismatched keys.

Catches silent host-key rotation drift and MITM. Run daily (wired into the
repo-settings-sync cron) and manually after any connectivity incident.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import urllib.request

KNOWN_HOSTS = "/home/agent/.ssh/known_hosts"
HOSTS = ["github.com"]
ALGO = {"ED25519": "SHA256_ED25519", "RSA": "SHA256_RSA", "ECDSA": "SHA256_ECDSA"}


def meta_fingerprints() -> dict:
    with urllib.request.urlopen("https://api.github.com/meta", timeout=10) as r:
        return json.load(r)["ssh_key_fingerprints"]


def known_fingerprints(host: str) -> dict:
    r = subprocess.run(
        ["ssh-keygen", "-F", host, "-f", KNOWN_HOSTS], capture_output=True, text=True
    )
    lines = [l for l in r.stdout.splitlines() if l and not l.startswith("#")]
    if not lines:
        return {}
    with tempfile.NamedTemporaryFile("w", suffix=".kh", delete=False) as t:
        t.write("\n".join(lines) + "\n")
        path = t.name
    lf = subprocess.run(["ssh-keygen", "-lf", path], capture_output=True, text=True).stdout
    out: dict[str, str] = {}
    for line in lf.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[1].startswith("SHA256:"):
            out[parts[-1].strip("()")] = parts[1]
    return out


def main() -> int:
    fail = False
    try:
        meta = meta_fingerprints()
    except Exception as exc:  # noqa: BLE001
        print(f"FATAL: cannot fetch api.github.com/meta: {exc}")
        return 1
    for host in HOSTS:
        have = known_fingerprints(host)
        if not have:
            print(f"{host}: FAIL no pinned keys in {KNOWN_HOSTS}")
            fail = True
            continue
        for typ, meta_key in ALGO.items():
            want = meta.get(meta_key)
            if want is not None and not want.startswith("SHA256:"):
                want = "SHA256:" + want  # api.github.com/meta omits the prefix
            got = have.get(typ)
            if want is None:
                continue
            if got is None:
                print(f"{host}: FAIL MISSING {typ} key (expected {want})")
                fail = True
            elif got != want:
                print(f"{host}: FAIL {typ} MISMATCH have={got} want={want} — treat as possible MITM, do NOT ssh")
                fail = True
            else:
                print(f"{host}: OK {typ} {got}")
    print("RESULT: " + ("FAIL" if fail else "OK"))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
