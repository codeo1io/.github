#!/usr/bin/env python3
"""Sync codeo1io fleet repo settings from common-settings.yaml (settings-as-code).

Fleet-wide: merge settings (squash-only, delete-branch-on-merge).
Opt-in (protection-opt-in.txt): branch protection — no force pushes, up-to-date
branches required before merge, admins NOT enforced so solo ff-push promote
flows (conductor release-promote) keep working.
Visibility (expect_private) is REPORT-ONLY: never auto-flipped.

Usage:
  sync_repo_settings.py [--dry-run | --apply] [--owner codeo1io]

Exit 0 on success (including fixed drift), 1 on hard API errors.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# A stuck gh/network call must never hang the 08:30 cron (rm-017).
GH_TIMEOUT = 60.0

MERGE_KEYS = (
    "allow_squash_merge",
    "allow_merge_commit",
    "allow_rebase_merge",
    "delete_branch_on_merge",
)
# allow_auto_merge is deliberately NOT drift-checked: on the free plan GitHub
# accepts the PATCH but silently keeps it false wherever branch protection
# cannot exist (private repos). Squash/delete/rebase flags are the durable
# invariants; auto-merge is a plan-gated convenience, not a fleet rule.


def gh(*args: str, input: str | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["gh", *args], capture_output=True, text=True, input=input,
            timeout=GH_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        # Uniform with gh failures: rc != 0 flows through the existing
        # allow_fail / FATAL paths instead of hanging the daily cron.
        return subprocess.CompletedProcess(
            ["gh", *args], returncode=124, stdout="",
            stderr=f"gh {' '.join(args)} timed out after {GH_TIMEOUT:.0f}s",
        )


def gh_json(*args: str, input: str | None = None, allow_fail: bool = False):
    r = gh(*args, input=input)
    if r.returncode != 0:
        if allow_fail:
            return None
        raise RuntimeError(f"gh {' '.join(args)} rc={r.returncode}: {r.stderr.strip()[:400]}")
    return json.loads(r.stdout) if r.stdout.strip() else None


def list_repos(owner: str) -> list[dict]:
    return gh_json(
        "repo", "list", owner, "--limit", "300",
        "--json", "name,isPrivate,isArchived,isFork,defaultBranchRef",
    ) or []


def read_list(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out: set[str] = set()
    for line in path.read_text().splitlines():
        # repo names cannot contain '#': anything after one is a comment
        entry = line.split("#", 1)[0].strip()
        if entry:
            out.add(entry)
    return out


def casefold_set(entries: set[str]) -> set[str]:
    """Casefolded view for membership tests: GitHub repo names are
    case-insensitive and the canonical casing can change on rename
    (e.g. chadgpt -> ChadGPT); a case-sensitive `in` silently dropped
    renamed repos from protection handling."""
    return {e.casefold() for e in entries}


def unmatched_entries(entries: set[str], fleet: set[str]) -> list[str]:
    """List entries matching no fleet repo (case-insensitive), sorted —
    catches renames, deletions, and typos in the opt-in/exclude/ack lists."""
    fleet_cf = casefold_set(fleet)
    return sorted(e for e in entries if e.casefold() not in fleet_cf)


def protection_body(cfg: dict) -> dict:
    p = cfg["branch_protection"]
    rsc = p["required_status_checks"]
    return {
        "required_status_checks": {"strict": rsc["strict"], "contexts": list(rsc["contexts"])},
        "enforce_admins": p["enforce_admins"],
        "required_pull_request_reviews": p["required_pull_request_reviews"],
        "restrictions": p["restrictions"],
        "allow_force_pushes": p["allow_force_pushes"],
        "allow_deletions": p["allow_deletions"],
    }


def protection_drift(current: dict | None, desired: dict) -> list[str]:
    drift = []
    if current is None:
        return ["protection: not configured"]
    ea = (current.get("enforce_admins") or {}).get("enabled")
    if ea is not None and ea != desired["enforce_admins"]:
        drift.append(f"protection.enforce_admins={ea} want {desired['enforce_admins']}")
    cur_rsc = current.get("required_status_checks")
    if cur_rsc is None:
        drift.append("protection.required_status_checks: not configured")
    else:
        if cur_rsc.get("strict") != desired["required_status_checks"]["strict"]:
            drift.append(f"protection.strict={cur_rsc.get('strict')} want {desired['required_status_checks']['strict']}")
        if (cur_rsc.get("contexts") or []) != desired["required_status_checks"]["contexts"]:
            drift.append(f"protection.contexts={cur_rsc.get('contexts')} want {desired['required_status_checks']['contexts']}")
    for k in ("allow_force_pushes", "allow_deletions"):
        cur = (current.get(k) or {}).get("enabled")
        want = desired[k]
        if cur is not None and cur != want:
            drift.append(f"protection.{k}={cur} want {want}")
    has_rpr = current.get("required_pull_request_reviews") is not None
    if has_rpr != (desired["required_pull_request_reviews"] is not None):
        drift.append(f"protection.required_pull_request_reviews configured={has_rpr} want False")
    return drift


def main() -> int:
    ap = argparse.ArgumentParser()
    mode_group = ap.add_mutually_exclusive_group()
    mode_group.add_argument("--dry-run", action="store_true", help="report only (the default without --apply)")
    mode_group.add_argument("--apply", action="store_true", help="fix drift (default: dry-run report)")
    ap.add_argument("--owner", default="codeo1io")
    args = ap.parse_args()
    mode = "APPLY" if args.apply else "DRY-RUN"

    cfg = yaml.safe_load((ROOT / "common-settings.yaml").read_text())
    excludes = read_list(ROOT / "exclude-repos.txt")
    protected = read_list(ROOT / "protection-opt-in.txt")
    expect_public = read_list(ROOT / "expect-public.txt")
    excludes_cf = casefold_set(excludes)
    protected_cf = casefold_set(protected)
    expect_public_cf = casefold_set(expect_public)
    merge_want = {k: bool(cfg["merge"][k]) for k in MERGE_KEYS}
    prot_want = protection_body(cfg)
    expect_private = bool(cfg["visibility"]["expect_private"])
    # Forks of public upstreams are structurally public on a personal account;
    # when true they are treated as conformant instead of visibility drift.
    expect_public_forks = bool(cfg["visibility"].get("expect_public_forks", True))

    errors = 0
    fixed = drifted = 0
    reports: list[str] = []

    try:
        repos = list_repos(args.owner)
    except RuntimeError as exc:
        print(f"FATAL: listing repos for {args.owner} failed: {exc}")
        return 1
    if not repos:
        print("FATAL: repo list empty or gh failed")
        return 1
    if len(repos) >= 300:
        print(f"WARN: repo list hit the gh --limit 300 cap ({len(repos)} repos) — "
              f"newer repos may be missing from this run; raise the limit")

    for repo in sorted(repos, key=lambda r: r["name"]):
        name = repo["name"]
        if name.casefold() in excludes_cf:
            continue
        if repo.get("isArchived"):
            reports.append(f"{name}: SKIP (archived)")
            continue
        slug = f"{args.owner}/{name}"
        branch = (repo.get("defaultBranchRef") or {}).get("name") or "main"

        # --- merge settings (fleet-wide) ---
        # gh repo list does not return merge flags; fetch full repo object
        # allow_fail: one bad repo must not abort the whole fleet pass (rm-011 parity
        # with the list_repos FATAL handling; the None branch below is live).
        full = gh_json("api", f"repos/{slug}", allow_fail=True)
        if full is None:
            errors += 1
            reports.append(f"{name}: ERROR fetching repo")
            continue
        cur_merge = {k: bool(full.get(k, False)) for k in MERGE_KEYS}
        mdiff = [k for k in MERGE_KEYS if cur_merge[k] != merge_want[k]]
        if mdiff:
            drifted += 1
            detail = ", ".join(f"{k}={cur_merge[k]}->{merge_want[k]}" for k in mdiff)
            if args.apply:
                fields = []
                for k in mdiff:
                    fields += ["-f", f"{k}={str(merge_want[k]).lower()}"]
                if gh_json("api", "--method", "PATCH", f"repos/{slug}", *fields, allow_fail=True) is None:
                    errors += 1
                    reports.append(f"{name}: ERROR patching merge settings")
                    continue
                fixed += 1
                reports.append(f"{name}: FIXED merge settings ({detail})")
            else:
                reports.append(f"{name}: DRIFT merge settings ({detail})")

        # --- visibility (report-only) ---
        if bool(full.get("private", True)) != expect_private:
            if (bool(repo.get("isFork")) and expect_public_forks) or name.casefold() in expect_public_cf:
                # Forks of public upstreams cannot be private on a personal
                # plan (GitHub Team required), and expect-public.txt lists
                # originals acknowledged as intentionally public — conformant,
                # not drift, never worth a daily nag line.
                pass
            else:
                reports.append(
                    f"{name}: VISIBILITY DRIFT (report-only) private={full.get('private')} "
                    f"expect {expect_private} — review manually, never auto-flipped"
                )

        # --- branch protection (opt-in) ---
        if name.casefold() in protected_cf:
            if full.get("private"):
                # Free plan: branch protection on private repos returns 403
                # "Upgrade to GitHub Pro" — soft skip, not an error.
                reports.append(f"{name}: SKIP branch protection (private repo, free plan)")
            else:
                cur_prot = gh_json("api", f"repos/{slug}/branches/{branch}/protection", allow_fail=True)
                pdiff = protection_drift(cur_prot, prot_want)
                if pdiff:
                    drifted += 1
                    if args.apply:
                        r = gh("api", "--method", "PUT", f"repos/{slug}/branches/{branch}/protection",
                               "--input", "-", input=json.dumps(prot_want))
                        if r.returncode != 0:
                            errors += 1
                            reports.append(f"{name}: ERROR protecting {branch}: {r.stderr.strip()[:200]}")
                            continue
                        fixed += 1
                        reports.append(f"{name}: FIXED branch protection on {branch} ({'; '.join(pdiff)})")
                    else:
                        reports.append(f"{name}: DRIFT branch protection on {branch} ({'; '.join(pdiff)})")

    print(f"[{mode}] repos={len(repos)} excluded={len(excludes)} drift_found={drifted} "
          f"{'fixed=' + str(fixed) if args.apply else ''} errors={errors}")
    for label, entries in (("opt-in", protected), ("exclude", excludes), ("expect-public", expect_public)):
        for entry in unmatched_entries(entries, {r["name"] for r in repos}):
            print(f"  WARN unmatched {label} entry: {entry} (no such repo — rename, deletion, or typo)")
    for line in reports:
        print(f"  {line}")
    if errors:
        print(f"RESULT: FAIL ({errors} hard errors)")
        return 1
    print(f"RESULT: OK ({'all drift fixed' if args.apply else 'dry-run, no changes made'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
