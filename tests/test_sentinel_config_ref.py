"""Sentinel config-distribution trust chain (cycle-6 batch F4, rm-043).

The reusable workflow checks out the fleet gitleaks.toml at
``inputs.config-ref``. Callers without an explicit ref — magic-hermes and
hermes-agent, which pin the reusable workflow at mutable @main — inherit
this DEFAULT, so a stale default means the fleet scans with an old config
and nothing anywhere notices. That is exactly how the cycle-5 hardened
config (cf3a0fe) spent two cycles not reaching 2 of 3 callers while the
default still pointed at the cycle-4 d04d86d.

Locks three properties of the default:

  * it is a FULL 40-hex SHA (not @main, not a short SHA — auditability of
    what callers actually scanned with)
  * the commit exists in this repository's history
  * PARITY: gitleaks.toml at the default ref == gitleaks.toml at HEAD

The parity check is deliberately gate-forcing: whenever gitleaks.toml
changes, the default MUST be re-bumped to the landing commit in the same
batch (the promote rider, documented in the workflow header). Until that
rider executes, HEAD's config differs from the default's and this test
fails — that failure IS the enforcement. Cycle-6 implement-time tree is
green because HEAD (659c726) still equals the interim default; the moment
batch F lands, the rider must bump the default to the batch commit.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "private-leak-sentinel.yaml"
CONFIG = "gitleaks.toml"


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args], capture_output=True, text=True
    )


def _config_ref_default() -> str:
    workflow = yaml.safe_load(WORKFLOW.read_text())
    # YAML 1.1 parses a bare `on:` key as boolean True
    trigger = workflow.get("on", workflow.get(True))
    default = trigger["workflow_call"]["inputs"]["config-ref"]["default"]
    assert isinstance(default, str), f"config-ref default malformed: {default!r}"
    return default.strip()


def test_default_is_a_full_sha() -> None:
    default = _config_ref_default()
    assert re.fullmatch(r"[0-9a-f]{40}", default), (
        f"config-ref default {default!r} is not a full 40-hex SHA — callers "
        "scanning with a mutable/short ref cannot be audited"
    )


def test_default_commit_exists() -> None:
    default = _config_ref_default()
    res = _git("cat-file", "-e", f"{default}^{{commit}}")
    assert res.returncode == 0, (
        f"config-ref default {default} is not a commit in this repository — "
        "callers' scans would fail to resolve it"
    )


def test_default_ref_config_matches_head() -> None:
    default = _config_ref_default()
    at_default = _git("show", f"{default}:{CONFIG}")
    at_head = _git("show", f"HEAD:{CONFIG}")
    assert at_default.returncode == 0 and at_head.returncode == 0, (
        f"gitleaks.toml not resolvable at default ({default}) or HEAD"
    )
    assert at_default.stdout == at_head.stdout, (
        f"STALE config-ref default: gitleaks.toml at {default[:12]} differs "
        "from HEAD. The hardened working-tree config is NOT what @main "
        "callers scan with. Execute the promote rider: bump the default in "
        ".github/workflows/private-leak-sentinel.yaml to the commit that "
        "lands this batch (same batch, not later)."
    )
