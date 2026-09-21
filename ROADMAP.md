# .github — Roadmap

> Autonomously maintained by the roadmap sync (reliability-first). Items cite reproducible codebase signals; acceptance is proven by cited evidence.

**Vision**: A reliable, customer-friendly repository advanced by evidence-cited roadmap cycles owned by the autonomy loop

**Pillars**: reliability work outranks customer-experience work; every roadmap item cites reproducible codebase signals; acceptance is proven by cited evidence, never claimed

## Fleet context

- dependents (changes here affect): (host), dashboard
- graph: evidence-derived (imports/refs/deploy surfaces); advisory

## Open items

### Add test coverage for 2 untested module(s)
- id: `rm-002` | track: reliability | priority: 86.0 | status: done
- signals: reliability.no_tests:scripts/check_known_hosts.py, reliability.no_tests:scripts/sync_repo_settings.py
- acceptance: Every module in ['scripts/check_known_hosts.py', 'scripts/sync_repo_settings.py'] has a corresponding test file with at least one passing test
- evidence: CI: pytest collects the new test files and they pass

### Refactor 3 high-complexity function(s)
- id: `rm-001` | track: reliability | priority: 79.0 | status: candidate
- signals: reliability.complexity_hot:scripts/check_known_hosts.py::main, reliability.complexity_hot:scripts/sync_repo_settings.py::main, reliability.complexity_hot:scripts/sync_repo_settings.py::protection_drift
- acceptance: Each flagged function is decomposed below the branch threshold with behavior locked by characterization tests
- evidence: ast-based branch-count check passes in CI

<!-- cycle-1 extension (2026-09-21, conductor run 52072e19204f4fb3a83d9abdd4d4f625; items rm-003..rm-013 sourced from the cycle assess + research phases; existing items preserved verbatim) -->

### Verify the complete pinned-key set in check_known_hosts.py (security blind spot)
- id: `rm-003` | track: reliability | priority: 98.0 | status: done
- signals: correctness.last_key_wins:scripts/check_known_hosts.py:41 (dict assignment `out[parts[-1].strip("()")] = parts[1]` keeps only the LAST fingerprint per algorithm; ssh accepts ANY pinned key so a stale/extra pinned key is a silent MITM window the checker reports clean); dynamically proven 2026-09-21: synthetic known_hosts with a generated stale ed25519 first + live valid key last -> checker prints OK while the stale key stays pinned; valid-first/stale-last -> false FAIL; ssh.github.com:443 fallback host unpinned (`ssh-keygen -F "[ssh.github.com]:443" -f ~/.ssh/known_hosts` -> no match); /tmp leak: tempfile.NamedTemporaryFile(delete=False) at scripts/check_known_hosts.py:33 never unlinked (3 leaked .kh files observed during 3 test runs)
- acceptance: checker collects ALL pinned fingerprints per host+algorithm and requires the pinned set to exactly match api.github.com/meta (extra/unknown pinned key = FAIL); missing algorithm still FAILs; [ssh.github.com]:443 added to HOSTS; temp files deleted on every path (delete=True or unlink in finally)
- evidence: pytest on fixture known_hosts files (exact-set -> OK; stale-extra -> FAIL; missing-algo -> FAIL); `python3 scripts/check_known_hosts.py` live-OK; `ls /tmp/*.kh` empty after runs

### Case-insensitive opt-in/exclude matching + unmatched-entry validation
- id: `rm-004` | track: reliability | priority: 97.0 | status: done
- signals: correctness.case_sensitive_membership:scripts/sync_repo_settings.py:187 (`if name in protected`); live 2026-09-21: protection-opt-in.txt:6 lists `chadgpt` but canonical repo name is `ChadGPT` (gh repo view codeo1io/chadgpt -> {"name":"ChadGPT"}, private, default=main) so the repo silently receives NO protection handling; `'ChadGPT' in {'chadgpt'}` -> False; same comparison serves exclude-repos.txt via read_list()
- acceptance: opt-in/exclude membership compared casefolded; --dry-run/--apply WARN on every opt-in/exclude entry matching no fleet repo (catches renames/deletions/typos); ChadGPT gets an explicit decision line (protected when eligible, or SKIP with reason) instead of silence
- evidence: unit tests cover the casefold/unmatched helpers (case-mismatched opt-in fixture); main()-level membership+WARN wiring verified live — `python3 scripts/sync_repo_settings.py --dry-run` prints a decision line for every protection-opt-in entry and zero unmatched-entry warnings once the file is corrected; main()-level unit tests deferred to the complexity-refactor cycle (rm-001)

### Propagate sync failures through the cron wrapper (no silent OK)
- id: `rm-005` | track: reliability | priority: 96.0 | status: candidate
- signals: reliability.masked_failure:~/.hermes/scripts/repo-settings-sync.sh:23 (unconditional `exit 0` — cron-level failure invisible; outcome only in ~/.hermes/repo-settings-sync.log); README.md:33-36 documents this wrapper as the enforcement path; log holds a single run (2026-09-20T18:43Z, rc=0); wrapper also runs `git reset --hard` + `clean -qfd` on the shared /work/projects/.github checkout (destroys uncommitted work; note clean already endangers the untracked rendered ROADMAP.md)
- acceptance: wrapper exits nonzero when the --apply sync or check_known_hosts fails (report-only VISIBILITY DRIFT lines still OK); log gains a one-line RESULT summary per run; README documents the rc contract
- evidence: PATH-shimmed gh exiting 2 -> wrapper rc=2; normal run -> rc=0 + RESULT line in log

### Visibility acknowledgment list (stop permanent drift noise)
- id: `rm-006` | track: reliability | priority: 95.0 | status: done
- signals: alert_fatigue:scripts/sync_repo_settings.py:182 — .github, magic-hermes, openai-embedding-proxy flagged `VISIBILITY DRIFT` on EVERY run with no ack mechanism (live dry-run 2026-09-21: 3 lines; the 2026-09-20 logged run emitted 9 before the fork-conformance fix cut it)
- acceptance: optional expect-public.txt (same format as exclude-repos.txt) acks intended-public repos; listed repos not flagged; unlisted visibility drift still reported; README documents the mechanism
- evidence: expect-public.txt seeded with the 3 intended-public repos -> live --dry-run shows 0 VISIBILITY DRIFT lines; unlisted drift still reported (3 lines pre-seed); main()-level ack unit test deferred to the complexity-refactor cycle (rm-001)

### End the dependency-update vacuum (Renovate or Dependabot)
- id: `rm-007` | track: customer-experience | priority: 94.0 | status: candidate
- signals: research 2026-09-21: `gh api 'search/issues?q=org:codeo1io+author:app/renovate' --jq .total_count` -> 0 (app never installed although README anticipates activation and renovate-config/renovate.json is staged); dependabot.yml absent in 3/3 sampled fleet repos (stonks, magic-mcp, hermes-infra contents API -> 404) — fleet has ZERO dependency automation
- acceptance: decision recorded in README; either Renovate app installed (first renovate PR visible fleet-wide) OR zero-install Dependabot defaults shipped from this repo (canonical template + adoption guide) and committed in >=1 fleet repo
- evidence: renovate PR link, or `gh api repos/codeo1io/<repo>/contents/.github/dependabot.yml` -> 200

### Refresh and SHA-pin workflow-template actions
- id: `rm-008` | track: reliability | priority: 92.0 | status: done
- signals: deps.stale_major:workflow-templates/deploy-router.yaml:28,49 (actions/checkout@v4 vs latest v7.0.1 released 2026-07-20) and :30 (dorny/paths-filter@v3 vs v4.0.3 released 2026-08-05); the template header already demands SHA pinning BEFORE FIRST USE but ships mutable tags
- acceptance: template pins full-SHA refs of the current majors (checkout v7 line, paths-filter v4 line) with version comments; BEFORE-FIRST-USE note reduced to verify-SHAs
- evidence: `git ls-remote https://github.com/dorny/paths-filter refs/tags/v4.0.3` resolves to the pinned SHA; grep shows no bare `@vN` action refs in workflow-templates/

### Community health files + dedicated profile README
- id: `rm-009` | track: customer-experience | priority: 90.0 | status: candidate
- signals: research 2026-09-21: `gh api repos/codeo1io/.github/contents/ISSUE_TEMPLATE` -> 404 (no default community health files despite the .github special-repo distributing them account-wide per docs.github.com 'Creating a default community health file'); root README.md of the PUBLIC .github repo renders as the codeo1io profile page (docs.github.com profile-README rule) and is currently internal fleet-ops documentation
- acceptance: ISSUE_TEMPLATE/, PULL_REQUEST_TEMPLATE.md, SECURITY.md committed in the .github repo; ops documentation moved under docs/ and linked from a short dedicated profile README.md
- evidence: contents API 200 for ISSUE_TEMPLATE; github.com/codeo1io renders the new profile README; ops docs reachable under docs/

### Actions least-privilege drift-check (allowed_actions)
- id: `rm-010` | track: reliability | priority: 88.0 | status: candidate
- signals: research 2026-09-21: `gh api repos/codeo1io/stonks/actions/permissions` -> {"allowed_actions":"all"} (permissive; same on .github) — REST PATCHable per docs.github.com/rest/actions/permissions; sync ignores this surface today (defaultWorkflowPermissions is NOT in the public GraphQL schema — undefinedField probed — use the REST endpoints)
- acceptance: common-settings.yaml gains an actions_permissions section; sync drift-checks allowed_actions (+ allowed patterns when selected) following the MERGE_KEYS pattern; fleet default (all vs local_only) decision recorded; private/plan-gated repos report-only
- evidence: live --dry-run reports per-repo actions-permission drift; --apply on one repo verified by re-GET

### Hygiene batch (assess small fixes)
- id: `rm-011` | track: reliability | priority: 86.0 | status: done
- signals: assess 2026-09-21: dead assignment scripts/sync_repo_settings.py:148 (cur_merge from gh repo list fields gh never returns; overwritten at 151); --dry-run/--apply not mutually exclusive (:112-113 — both flags silently run APPLY); --limit 300 hard cap with no saturation warning (:56); viewerPermission requested but unused (:57); read_list ignores inline comments (:67); gh failure in list_repos raises uncaught RuntimeError (:54 -> traceback instead of the clean FATAL at :133); allow_auto_merge declared common-settings.yaml:12 but no code path applies or verifies it (README.md:10-13 overstates it as a synced default)
- acceptance: argparse mutually-exclusive group rejects --dry-run --apply; WARN when repo count hits the limit; viewerPermission dropped or used; read_list strips inline comments; clean FATAL on repo-list failure; dead assignment removed; allow_auto_merge either applied where plan-permitted or removed from yaml+README with an honest note
- evidence: pytest unit tests (read_list, arg handling); live --dry-run unchanged (repos=43, drift=0) and now rejects the flag combo; config/README consistent on allow_auto_merge

### Protection endgame decision (Pro upgrade vs public-only opt-in)
- id: `rm-012` | track: customer-experience | priority: 62.0 | status: candidate
- signals: research 2026-09-21: GET /rulesets and classic /protection both return the identical 403 "Upgrade to GitHub Pro or make this repository public" on private repos (probed stonks + ChadGPT) while rulesets return 200 on the public fork dashboard — 7/9 protection-opt-in repos are private hence permanently dormant on the free plan; account shape is User/free (users/codeo1io -> type=User, plan=null), so org-only features are structurally unavailable and rulesets migration alone fixes nothing
- acceptance: README documents the 403-parity evidence and records the decision (upgrade to Pro -> activate the 7 dormant opt-ins and evaluate rulesets; or re-scope opt-in policy to public repos); protection-opt-in.txt header states the current reality
- evidence: README section citing the probe commands; opt-in header updated; if Pro lands: `gh api repos/codeo1io/stonks/branches/main/protection` no longer 403

### Host tooling currency (gh CLI)
- id: `rm-013` | track: reliability | priority: 55.0 | status: candidate
- signals: research 2026-09-21: host gh is 2.83.2 (2025-12-10) vs latest v2.101.0 (~16 minors behind; nothing currently broken)
- acceptance: host gh upgraded to the current release; sync + known-hosts checker re-verified post-upgrade
- evidence: `gh --version` current; `python3 scripts/sync_repo_settings.py --dry-run` and `python3 scripts/check_known_hosts.py` both clean after upgrade

## Cycle-1 compound addendum (2026-09-21, pre-review)

Status ledger for run 52072e19204f4fb3a83d9abdd4d4f625 (repository-maintenance cycle 1,
"enforcement-tool correctness + signal quality" batch). Materialized during the
independent-review fix step after the compound step's writes were lost (review P1:
status flips absent on disk at review time; mtime still at the roadmap phase). Evidence
base is pre-review by contract; review/shipping outcomes are the next cycle's assess
inputs.

**Closed (implemented + validated, pending landing):** rm-002 (tests/test_check_known_hosts.py
9 passing + tests/test_sync_repo_settings.py 6 passing — every module test-file covered),
rm-003 (exact pinned-set semantics; [ssh.github.com]:443 pinned with meta-verified keys;
temp-leak fixed), rm-004 (casefold membership + unmatched-entry WARN; chadgpt->ChadGPT),
rm-006 (expect-public.txt ack list; 0 VISIBILITY DRIFT lines), rm-008 (deploy-router.yaml
SHA-pinned to commit-verified tags), rm-011 (all 7 hygiene fixes; residuals below).
**Still open:** rm-001 (complexity refactor — only its test deliverable landed), rm-005,
rm-007, rm-009, rm-010, rm-012, rm-013.

**Independent review (READY WITH FIXES) disposition:** P1 closed here (this materialization
+ the ROADMAP.md rider at commit makes the roadmap tracked, surviving the daily clean
-qfd — see rm-005). P2 (per-repo gh api uncaught failure) and the P3 docstring/mode-rename
items fixed in the same fix step (allow_fail=True at the repos/{slug} fetch; docstring
drops the auto-merge claim; mode_group no longer shadowed). Acceptance wording for
rm-004/rm-006 amended above to match delivered evidence (main()-level unit tests deferred
to rm-001's cycle). Advisory README runbook for new SSH algorithms added.

**Lessons:** docs/lessons.md (L1-L8) — exact-set pin verification for security checkers,
casefold + unmatched WARN for fleet lists, dead plan-gated config removal, ack lists for
report-only signals, commit-SHA pinning with commit-typed tag verification, per-phase
live re-probes (fleet moved 43->44 mid-run), temp-file unlink hygiene, phase results must
be materialized before the turn ends (this addendum's own P1 lesson).

**Context for the next cycle:** lead = rm-001 (complexity refactor, now unblocked on the
green 15-test suite; fold in the two deferred main()-level tests). Host-side rm-005
(wrapper rc propagation) stays outside the repo. Decision-gated: rm-007 (dependency
automation), rm-010 (allowed_actions), rm-012 (protection endgame — rulesets are 403-parity
gated on the free plan; only Pro upgrade or public repos unlock private-repo protection).
New full_tests observations for the next assess: fleet grew 43->44 (new repo `agent` shows
correctly-detected merge drift; decide opt-in/exclude membership or let the daily cron
apply), and the report loop still raises BrokenPipeError when piped to an early-closing
reader (pre-existing; harmless to the cron, worth hardening alongside rm-001).

*End of cycle-1 compound addendum.*

<!-- managed by hermes-roadmap render; do not edit by hand -->
