"""Unit tests for scripts/sync_repo_settings.py (rm-004 / rm-006 / rm-011 / rm-001).

Hermetic: only pure helpers and argparse behavior are exercised here; the gh
API path is covered by the manual --dry-run verification gate (see README).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import sync_repo_settings as srs  # noqa: E402

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "sync_repo_settings.py"


def test_read_list_strips_inline_comments(tmp_path):
    f = tmp_path / "list.txt"
    f.write_text(
        "# header comment\n"
        "stonks\n"
        "\n"
        "ChadGPT   # canonical casing\n"
        "   spaced   \n"
        "#trailing comment\n"
    )
    assert srs.read_list(f) == {"stonks", "ChadGPT", "spaced"}


def test_read_list_missing_file_is_empty(tmp_path):
    assert srs.read_list(tmp_path / "nope.txt") == set()


def test_casefold_set(tmp_path):
    assert srs.casefold_set({"ChadGPT", "STONKS", "fleet-status"}) == {
        "chadgpt", "stonks", "fleet-status"
    }


def test_unmatched_entries_catches_rename_and_typo():
    fleet = {"ChadGPT", "stonks", "dashboard"}
    entries = {"chadgpt", "stonkss", "dashboard"}  # rename-tolerant, typo caught
    assert srs.unmatched_entries(entries, fleet) == ["stonkss"]


def test_dry_run_and_apply_are_mutually_exclusive():
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run", "--apply"],
        capture_output=True, text=True,
    )
    assert r.returncode == 2  # argparse usage error
    assert "not allowed with argument" in r.stderr


def test_merge_keys_excludes_never_enforced_auto_merge():
    # rm-011 guard: allow_auto_merge is plan-gated and must stay out of the
    # enforced invariant set (removed from common-settings.yaml 2026-09-21).
    assert "allow_auto_merge" not in srs.MERGE_KEYS
    assert srs.MERGE_KEYS == (
        "allow_squash_merge",
        "allow_merge_commit",
        "allow_rebase_merge",
        "delete_branch_on_merge",
    )
