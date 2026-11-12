"""Unit tests for scripts/sync_repo_settings.py (rm-004 / rm-006 / rm-011 / rm-001
/ rm-027 / rm-032).

Hermetic: pure helpers, the gh seam (timeout / pagination via monkeypatch), and
a fully stubbed main() run cover the code path; the live --dry-run gate stays
the manual verification step (see README).
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


# --- gh seam: timeout (rm-017 landed in cycle-2; locked here) -------------

def test_gh_timeout_synthesizes_rc124(monkeypatch):
    def expired(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd=["gh"], timeout=srs.GH_TIMEOUT)

    monkeypatch.setattr(srs.subprocess, "run", expired)
    r = srs.gh("api", "user")
    assert r.returncode == 124  # uniform with gh failures -> FATAL/allow_fail paths
    assert "timed out" in r.stderr


# --- gh seam: transient-egress retry (rm-034 class, 2026-11-12) ------------
# Observed live: "dial tcp ...: no route to host" flaps killed 4 of 15 daily
# syncs (2026-10-30, 11-07, 11-11, 11-12). gh() must retry ONLY transient
# network shapes; auth verdicts and timeouts stay single-shot.


def test_is_transient_gh_failure_classifies():
    flap = (
        'gh: Put "https://api.github.com/repos/codeo1io/x/branches/main/protection": '
        "dial tcp 172.182.252.137:443: connect: no route to host"
    )
    assert srs._is_transient_gh_failure(flap) is True
    assert srs._is_transient_gh_failure("gh: EOF") is True
    assert srs._is_transient_gh_failure("gh: server returned 503 Service Unavailable") is True
    # Non-transient: retry cannot fix these
    assert srs._is_transient_gh_failure("gh: Bad credentials (HTTP 401)") is False
    assert srs._is_transient_gh_failure("gh: Not Found (HTTP 404)") is False
    assert srs._is_transient_gh_failure("") is False
    assert srs._is_transient_gh_failure("gh: Resource not accessible (HTTP 403)") is False


def _cp(rc, stderr=""):
    return subprocess.CompletedProcess(["gh"], rc, stdout="", stderr=stderr)


def test_gh_retries_transient_flap_then_succeeds(monkeypatch):
    # The live 2026-11-12 shape: one flap call, then the route returns.
    monkeypatch.setattr(srs.time, "sleep", lambda _s: None)
    calls = {"n": 0}

    def flaky(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            return _cp(1, "dial tcp 172.182.252.137:443: connect: no route to host")
        return _cp(0, "")

    monkeypatch.setattr(srs.subprocess, "run", flaky)
    r = srs.gh("api", "user")
    assert r.returncode == 0
    assert calls["n"] == 2  # retried exactly once, then succeeded


def test_gh_persistent_flap_exhausts_retries(monkeypatch):
    monkeypatch.setattr(srs.time, "sleep", lambda _s: None)
    calls = {"n": 0}

    def always_flap(*_a, **_k):
        calls["n"] += 1
        return _cp(1, "dial tcp 172.182.252.137:443: connect: no route to host")

    monkeypatch.setattr(srs.subprocess, "run", always_flap)
    r = srs.gh("api", "user")
    assert r.returncode == 1
    assert calls["n"] == srs.GH_TRANSIENT_RETRIES + 1  # bounded, not infinite


def test_gh_does_not_retry_auth_failure(monkeypatch):
    monkeypatch.setattr(srs.time, "sleep", lambda _s: None)
    calls = {"n": 0}

    def denied(*_a, **_k):
        calls["n"] += 1
        return _cp(1, "gh: Bad credentials (HTTP 401)")

    monkeypatch.setattr(srs.subprocess, "run", denied)
    r = srs.gh("api", "user")
    assert r.returncode == 1
    assert calls["n"] == 1  # single-shot: a retry cannot fix auth


def test_gh_does_not_retry_timeout(monkeypatch):
    monkeypatch.setattr(srs.time, "sleep", lambda _s: None)
    calls = {"n": 0}

    def expired(*_a, **_k):
        calls["n"] += 1
        raise subprocess.TimeoutExpired(cmd=["gh"], timeout=srs.GH_TIMEOUT)

    monkeypatch.setattr(srs.subprocess, "run", expired)
    r = srs.gh("api", "user")
    assert r.returncode == 124
    assert calls["n"] == 1  # timeout is a hang, not a flap: no retry


def test_gh_json_flap_does_not_raise_when_retry_recovers(monkeypatch):
    # End-to-end seam check: a flap under gh_json must not surface as a
    # RuntimeError (which at list_repos is a whole-pass FATAL).
    monkeypatch.setattr(srs.time, "sleep", lambda _s: None)
    calls = {"n": 0}

    def flaky(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            return _cp(1, "gh: Put https://api.github.com: dial tcp: no route to host")
        import json as _json
        ok = subprocess.CompletedProcess(
            ["gh"], 0, stdout=_json.dumps({"data": {}}), stderr=""
        )
        return ok

    monkeypatch.setattr(srs.subprocess, "run", flaky)
    out = srs.gh_json("api", "graphql", "-f", "query=q")
    assert out == {"data": {}}


def test_gh_retry_backoff_is_linear_not_zero(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(srs.time, "sleep", sleeps.append)
    calls = {"n": 0}

    def always_flap(*_a, **_k):
        calls["n"] += 1
        return _cp(1, "dial tcp: connection refused")

    monkeypatch.setattr(srs.subprocess, "run", always_flap)
    srs.gh("api", "user")
    assert sleeps == [5.0, 10.0, 15.0]  # linear backoff across 3 retries


def test_gh_json_timeout_raises_with_rc124(monkeypatch):
    monkeypatch.setattr(srs, "gh", lambda *a, **k: subprocess.CompletedProcess(
        ["gh"], returncode=124, stdout="", stderr="timed out"))
    try:
        srs.gh_json("api", "user")
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "rc=124" in str(exc)


# --- list_repos pagination (rm-032) ---------------------------------------

def _gql_page(names, has_next, cursor=None):
    return {"data": {"repositoryOwner": {"repositories": {
        "nodes": [{"name": n, "isPrivate": False, "isArchived": False,
                   "isFork": False, "defaultBranchRef": {"name": "main"}} for n in names],
        "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
    }}}}


def test_list_repos_paginates_past_300(monkeypatch):
    # 4 pages (100+100+100+24=324) — past the old `--limit 300` cap — prove
    # the single-call truncation is gone and cursors thread between pages
    # (rm-032 acceptance: unit test with >300 fake repos).
    pages = [
        _gql_page([f"r{i:03d}" for i in range(100)], True, "c1"),
        _gql_page([f"r{i:03d}" for i in range(100, 200)], True, "c2"),
        _gql_page([f"r{i:03d}" for i in range(200, 300)], True, "c3"),
        _gql_page([f"r{i:03d}" for i in range(300, 324)], False),
    ]
    seen_queries: list[str] = []

    def fake_gh_json(*args, **_k):
        assert args[:2] == ("api", "graphql")
        seen_queries.append(args[3])  # (api, graphql, -f, query=...)
        return pages[len(seen_queries) - 1]

    monkeypatch.setattr(srs, "gh_json", fake_gh_json)
    repos = srs.list_repos("codeo1io")
    assert len(repos) == 324
    assert len(seen_queries) == 4
    assert "after" not in seen_queries[0]           # first page: no cursor
    assert '"c1"' in seen_queries[1]                # cursor threaded
    assert '"c2"' in seen_queries[2]
    assert '"c3"' in seen_queries[3]


def test_list_repos_unknown_owner_returns_empty(monkeypatch):
    monkeypatch.setattr(srs, "gh_json", lambda *a, **k: {"data": {"repositoryOwner": None}})
    assert srs.list_repos("no-such-owner") == []


# --- security_and_analysis drift (rm-027, report-only) --------------------

def _sa(status):
    return {k: {"status": status} for k, _ in srs.SECURITY_FEATURES}


def test_security_drift_public_all_disabled_reports_three_rows():
    full = {"private": False, "security_and_analysis": _sa("disabled")}
    rows = srs.security_and_analysis_drift(full)
    assert len(rows) == 3
    assert any("secret scanning=disabled want enabled" in r for r in rows)


def test_security_drift_public_enabled_reports_nothing():
    assert srs.security_and_analysis_drift({"private": False, "security_and_analysis": _sa("enabled")}) == []


def test_security_drift_private_repo_out_of_scope():
    # private repos are plan-gated; no rows, no noise
    assert srs.security_and_analysis_drift({"private": True, "security_and_analysis": _sa("disabled")}) == []


def test_security_drift_missing_field_reports_unavailable():
    rows = srs.security_and_analysis_drift({"private": False})
    assert len(rows) == 3 and all("unavailable" in r for r in rows)


_MIN_CFG = """\
merge:
  allow_squash_merge: true
  allow_merge_commit: false
  allow_rebase_merge: false
  delete_branch_on_merge: true
branch_protection:
  enforce_admins: false
  required_status_checks:
    strict: false
    contexts: []
  required_pull_request_reviews: null
  restrictions: null
  allow_force_pushes: false
  allow_deletions: false
visibility:
  expect_private: true
  expect_public_forks: true
"""


def test_main_apply_reports_security_drift_and_never_mutates_it(tmp_path, monkeypatch, capsys):
    # End-to-end seam test of the rm-027 property: even in --apply mode the
    # security rows are REPORT-ONLY — zero mutating gh calls are issued for
    # them (and with matched merge settings, zero mutations at all).
    monkeypatch.setattr(srs, "ROOT", tmp_path)
    (tmp_path / "common-settings.yaml").write_text(_MIN_CFG)
    (tmp_path / "expect-public.txt").write_text("pubrepo\n")
    (tmp_path / "protection-opt-in.txt").write_text("")
    (tmp_path / "exclude-repos.txt").write_text("")
    monkeypatch.setattr(srs, "list_repos", lambda owner: [
        {"name": "privrepo", "isPrivate": True, "isArchived": False,
         "isFork": False, "defaultBranchRef": {"name": "main"}},
        {"name": "pubrepo", "isPrivate": False, "isArchived": False,
         "isFork": False, "defaultBranchRef": {"name": "main"}},
    ])
    calls: list[tuple] = []

    def fake_gh_json(*args, **kwargs):
        calls.append(args)
        if args[:2] == ("api", "repos/codeo1io/pubrepo"):
            return {"private": False, "isFork": False,
                    "allow_squash_merge": True, "allow_merge_commit": False,
                    "allow_rebase_merge": False, "delete_branch_on_merge": True,
                    "security_and_analysis": _sa("disabled")}
        if args[:2] == ("api", "repos/codeo1io/privrepo"):
            return {"private": True, "isFork": False,
                    "allow_squash_merge": True, "allow_merge_commit": False,
                    "allow_rebase_merge": False, "delete_branch_on_merge": True,
                    "security_and_analysis": _sa("disabled")}
        raise AssertionError(f"unexpected gh_json call: {args}")

    monkeypatch.setattr(srs, "gh_json", fake_gh_json)
    monkeypatch.setattr(sys, "argv", ["sync_repo_settings.py", "--apply"])
    rc = srs.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "security_report_only=1" in out
    assert "pubrepo: DRIFT security (report-only)" in out
    assert "secret scanning=disabled want enabled" in out
    # private repo is out of scope: no report line for it at all
    assert not [ln for ln in out.splitlines() if ln.lstrip().startswith("privrepo")]
    # the report-only guarantee: no PATCH/PUT anywhere in this run
    assert not any("--method" in " ".join(a) for a in calls), calls


def test_drift_found_counts_unique_repos(tmp_path, monkeypatch, capsys):
    # Cycle-7 F1e: one repo drifting BOTH merge settings and branch
    # protection used to be counted twice (drift_found=2) — drift_found
    # must be the number of drifted REPOS.
    monkeypatch.setattr(srs, "ROOT", tmp_path)
    (tmp_path / "common-settings.yaml").write_text(_MIN_CFG)
    (tmp_path / "expect-public.txt").write_text("pubrepo\n")
    (tmp_path / "protection-opt-in.txt").write_text("pubrepo\n")
    (tmp_path / "exclude-repos.txt").write_text("")
    monkeypatch.setattr(srs, "list_repos", lambda owner: [
        {"name": "pubrepo", "isPrivate": False, "isArchived": False,
         "isFork": False, "defaultBranchRef": {"name": "main"}},
    ])

    def fake_gh_json(*args, **kwargs):
        if args[:2] == ("api", "repos/codeo1io/pubrepo"):
            # merge drift: squash off (want on)
            return {"private": False, "isFork": False,
                    "allow_squash_merge": False, "allow_merge_commit": False,
                    "allow_rebase_merge": False, "delete_branch_on_merge": True}
        if args[:2] == ("api", "repos/codeo1io/pubrepo/branches/main/protection"):
            # protection drift: strict=True (want False)
            return {"enforce_admins": {"enabled": False},
                    "required_status_checks": {"strict": True, "contexts": []},
                    "required_pull_request_reviews": None,
                    "restrictions": None,
                    "allow_force_pushes": False, "allow_deletions": False}
        raise AssertionError(f"unexpected gh_json call: {args}")

    monkeypatch.setattr(srs, "gh_json", fake_gh_json)
    monkeypatch.setattr(sys, "argv", ["sync_repo_settings.py", "--dry-run"])
    rc = srs.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "DRIFT merge settings" in out and "DRIFT branch protection" in out
    assert "drift_found=1" in out, "one drifted repo must count once, not twice"
