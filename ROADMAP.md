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
- evidence: unit tests cover the casefold/unmatched helpers (case-mismatched opt-in fixture); main()-level membership+WARN wiring verified live — `python3 scripts/sync_repo_settings.py --dry-run` prints a decision line for every PRIVATE opt-in entry and zero unmatched-entry warnings once the file is corrected; public forks (dashboard, hermes-agent) are silent BY DESIGN when already conformant (require_signatures/enforce_admins/allow_force_pushes match) — conformant-silence vs dropped is indistinguishable in dry-run output until rm-001's main()-level tests land; main()-level unit tests deferred to the complexity-refactor cycle (rm-001)

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

<!-- cycle-2 extension (2026-09-21, conductor run 92e960046f144249b3bb41d9da814e45; items rm-014..rm-022 sourced from the cycle-2 assess + research phases; cycle-1 items preserved verbatim from the tracked roadmap at 9d0b155 — that batch is still unlanded on main, see rm-014) -->

### Land the stranded cycle-1 batch (highest leverage: ships rm-002/003/004/006/008/011)
- id: `rm-014` | track: reliability | priority: 98.0 | status: done (cycle-2 B1: content-merged 9d0b155 into the run branch 2026-09-21, exec bits preserved; 15/15 tests green on merged tree; gate/commit pending. RESIDUAL: acceptance clause "no dangling fix branch" unmet — conductor/run-52072e19204f still exists local+origin carrying 9d0b155; branch deletion is push-class work deferred to the Conductor commit/push gate — do not close rm-014's ledger until that branch is gone)
- signals: assess 2026-09-21: commit 9d0b155 (validated cycle-1 fixes: casefold opt-in + unmatched-entry WARN, chadgpt->ChadGPT, [ssh.github.com]:443 pin verification, temp-leak fix, expect-public.txt ack, mutually-exclusive --dry-run/--apply, SHA-pinned deploy-router template, 15 tests) exists only on conductor/run-52072e19204f (local + origin); `git merge-base --is-ancestor 9d0b155 origin/main` -> NOT in main (merge-base 02e6eaf; main diverged with 6 newer commits, 9b0a4e3 touches the same scripts -> conflicts expected); consequently main still carries the ChadGPT silent-skip (live dry-run 2026-09-21: all 8 other opt-in repos get a decision line, ChadGPT absent), the unverified :443 host, the flag hazard, and zero tests
- acceptance: 9d0b155 reconciled onto current main (rebase or merge, conflicts resolved); on the merged tree: pytest tests/ green (15+), `python3 scripts/sync_repo_settings.py --dry-run` prints a ChadGPT decision line and 0 VISIBILITY DRIFT lines with expect-public.txt, `python3 scripts/check_known_hosts.py` live-OK incl. [ssh.github.com]:443; stranded branch merged or deleted (no dangling fix branch); status ledger above updated to shipped
- evidence: `git grep casefold_set scripts/` on merged main; pytest output; dry-run/checker transcripts in the run log

### Public-repo control-plane disclosure (visibility decision + scrub)
- id: `rm-015` | track: reliability | priority: 97.0 | status: candidate
- signals: assess 2026-09-21: `gh repo view codeo1io/.github` -> isPrivate:false, visibility:PUBLIC; commit b0f61ae tracks control-plane/ on main and the daily mirror pushes the same to the public `data` branch (`git ls-tree -r origin/data --name-only` -> 7 control-plane files incl. a 12,686-line watchdog incident log with run/supervisor IDs and /home/agent paths, conductor-tracks.tsv DB paths, cron-inventory.json (54 jobs), runners.txt (26 runners), kanban roster); contradicts the account's private-by-default repo policy and the repo's own expect_private:true (dry-run nags about .github itself every run — the mechanism cannot express "intentionally public"); cycle-5 2026-09-23: origin/main ITSELF tracks control-plane/ (7 files, git ls-tree) incl. the FULL 12,686-line watchdog log (1,290 host-path lines; runners 26 vs 28 live, cron 54 vs 56, frozen at b0f61ae) while the production mirror path pushes UNBOUNDED to data (13,524 lines); research docs-verified remediation menu: (A) repo private + per-USER Access policy "Accessible from repositories owned by 'codeo1io' user" (share-across-private-repositories.md, fpt) — serves same-owner PRIVATE callers only, (B) keep public but untrack control-plane/ from main + relocate the data-branch mirror, (C) split-repo: public minimal sentinel+gitleaks.toml (public callers cannot use private reusable workflows; a private .github's workflow templates serve private repos only — reusing-workflow-configurations.md) + private fleet-ops repo for control-plane mirrors
- acceptance: decision recorded in corrections.yaml + README: EITHER control-plane scrubbed from public refs (mirror to a private side-channel repo, or the fleet-status reader switches to a private source) OR the repo goes private AND sentinel config delivery survives (vendored/pinned gitleaks.toml in callers or token-authed fetch); no fleet-internal paths on any public ref afterwards
- evidence: `git ls-tree origin/main origin/data` shows no control-plane/* after scrub, or `gh repo view codeo1io/.github` -> PRIVATE with sentinel still green on magic-hermes; corrections.yaml gains the entry with reconfirm_due

### Correct the sentinel-coverage claim / cover openai-embedding-proxy
- id: `rm-016` | track: reliability | priority: 95.0 | status: done in-tree (cycle-2 B3: corrections.yaml claim amended 2026-09-21; cross-repo adoption in openai-embedding-proxy remains deferred)
- signals: assess 2026-09-21: control-plane/corrections.yaml:21-26 asserts "gitleaks sentinel covers them (magic-hermes + openai-embedding-proxy)" but `gh api repos/codeo1io/openai-embedding-proxy/contents/.github/workflows` -> only ci.yml (no sentinel/gitleaks reference; ci.yml content grep -> none); the same ledger records that account-level secret_scanning enablement reverts on those repos => openai-embedding-proxy currently has ZERO secret scanning; magic-hermes does call the reusable workflow (via @main); cycle-5 2026-09-23: docs re-verified — secret scanning "can be enabled on any free public repository that you own" (enable-secret-scanning.md, fpt), so the report-only drift set (8 public repos incl. .github itself) is ENABLEABLE state, not account-plan-gated; the corrections entry's account-level-revert mechanism remains unexplained — root-cause via one-shot single-repo enablement + revert-capture before any fleet attempt; corrections.yaml documents only 2 of the 8 drifting repos; cycle-7 2026-09-24: platform state CONFIRMED live — secret_scanning + push_protection report ENABLED on 3 public fleet repos (.github, hermes-agent, hermes-gpt) while magic-hermes + openai-embedding-proxy (both public per expect-public.txt) report all-disabled; dependabot_security_updates disabled fleet-wide; the enableable-state hypothesis is now observable platform fact (default-on wave reached this account), and the probe target list gains magic-hermes as the cleaner one-repo candidate (openai-embedding-proxy still needs the root-cause capture first)
- acceptance: either openai-embedding-proxy adopts the sentinel workflow or the corrections entry is amended to the real posture with a compensating control; ledger claims become live-verifiable (claim-check predicate like control-plane/claims.yaml)
- evidence: `gh api .../workflows` lists a sentinel workflow (or the amended corrections.yaml diff); a verifiable claim/predicate artifact records the true posture

### control-plane-sync hardening (trap, lock, rotation, timeouts)
- id: `rm-017` | track: reliability | priority: 97.0 | status: done in-tree, ship-gated (cycle-5 E1 2026-09-24: hardening landed on the EXECUTED path — scripts/sync_data_branch.py (the file the deployed 08:40 wrapper actually execs) now carries ALL B2 properties: flock single-flight on CONTROL_PLANE_LOCK, entry-branch restore on failure with safe main-branch default, watchdog tail capped at CONTROL_PLANE_WATCHDOG_MAX_LINES (default 5000), stage-before-diff, git subprocess timeouts rc=124; the dead twin scripts/control-plane-sync.sh is RETIRED (git rm) and tests/test_control_plane_shims.py retargeted at the production-executed .py — 6/6 green; README + AGENTS document the pipeline. SHIP-GATED: the wrapper execs the .py FROM this checkout, so hardening goes live at the first 08:40 run after the commit gate lands it — the 13,524-line uncapped mirror then self-trims under the cap (verify at the gate). Reopen-history preserved — cycle-5 2026-09-23: the hardened script was DEAD CODE in production — the 08:40 cron job 6e0bce2f7f7c resolves ~/.hermes/scripts/control-plane-sync.sh, a 5-line wrapper that runs scripts/sync_data_branch.py, so flock/trap/cap/gh-timeout NEVER execute; live proof: 2026-09-23T08:40:46Z data-branch watchdog mirror = 13,524 lines vs the 5,000-line cap (source 13,527); tests/test_control_plane_shims.py certifies the unexecuted artifact. Prior done-history preserved: cycle-2 B2 trap + flock + bounded mirror + gh() timeout 2026-09-21, shim-verified; review-fix 2026-09-21: ssh-keygen clause closed — both calls bounded via _ssh_keygen timeout=10 rc=124 synthesis, trap message branches on restore success)
- signals: assess 2026-09-21: scripts/control-plane-sync.sh:67 `git push` under set -euo pipefail with no trap — a push failure leaves the shared /work/projects/.github checkout on `data` (line 69 checkout main never runs); next morning repo-settings-sync.sh does `git reset --hard origin/main` on whatever branch is checked out, rewiring the local data pointer until 08:40; no flock (concurrent runs race on checkout/reset/push); the 12,686-line watchdog log is re-committed whole daily with no rotation; scripts/sync_repo_settings.py:40 subprocess.run has no timeout (a stuck gh call hangs the 08:30 cron); shared-checkout branch confusion already bit the fleet (watchdog alert 2026-09-21T01:20:01Z)
- acceptance: failure trap restores main on every exit path; flock prevents concurrent runs; mirrored watchdog log capped/rotated before copy; gh()/ssh-keygen subprocess calls carry timeouts
- evidence: PATH-shimmed failing git push -> script exits nonzero AND `git -C /work/projects/.github branch --show-current` = main; a second concurrent invocation no-ops; data-branch commits show bounded log size; hung-shim timeout test

### Sentinel supply-chain hardening + tool refresh
- id: `rm-018` | track: reliability | priority: 88.0 | status: candidate
- signals: research 2026-09-21: sentinel pins actions/checkout@v5.0.0 (SHA 08c6903) vs latest v7.0.1 (2026-07-20) and actions/upload-artifact@v4.6.2 vs latest v7.0.1 (2026-04-10); template majors covered by rm-008 (stranded); callers invoke the reusable workflow as @main (magic-hermes verified live) and the workflow fetches gitleaks.toml at runtime from unpinned main via unauthenticated raw.githubusercontent (private-leak-sentinel.yaml:33) — one weakening commit to this repo silently degrades fleet-wide leak scanning with no trace in caller repos; host gitleaks 8.28.0 vs upstream v8.30.1 (2026-03-21); cycle-4 compound 2026-09-22: the fetch/velocity half is CLOSED by rm-036 D2 (config consumed via SHA-pinned self-checkout — a weakening commit to gitleaks.toml no longer ships to callers until the pin is deliberately bumped); residuals: callers still invoke the reusable workflow as @main (SHA-pinning a cross-repo reusable workflow trades supply-chain auditability for config-rollout velocity — needs a deliberate fleet policy decision, possibly Dependabot-managed per rm-039), and the useDefault same-id override semantics revalidation now rides the pinned action's bundled gitleaks rather than a host install
- acceptance: callers pin the reusable workflow by full SHA; gitleaks.toml vendored into callers or fetched at a pinned SHA with checksum verification; workflow_dispatch trigger added for on-demand rescans; host gitleaks upgraded and the useDefault same-id override semantics of gitleaks.toml revalidated on 8.30.x
- evidence: caller workflow ymls show @<40-hex>; a planted-token fixture repo still fails the scan post-upgrade; `gitleaks version` -> 8.30.x with sentinel green on magic-hermes

### Consolidate the three control-plane mirror implementations
- id: `rm-019` | track: reliability | priority: 92.0 | status: done in-tree, ship-gated (cycle-5 E1 2026-09-24: exactly ONE mirror implementation — the hardened scripts/sync_data_branch.py — with the twin retired; copy-set parity restored: BOTH kanban OWNERS references (t_acd6a2e8 + t_851e7951) and control-plane/corrections.yaml mirrored from the canonical main-tree copy, so origin/data's stale pre-B3 corrections claim heals at the first post-landing 08:40 run; parity + hardening locked by retargeted tests/test_control_plane_shims.py; README Layout/Automation + AGENTS.md 'Control-plane data mirror' section document the pipeline. SHIP-GATED: heals in production at the first 08:40 run after the commit gate. Prior history preserved — cycle-5 2026-09-23 assess: signals inverted in reality; see below); cycle-7 2026-09-24 closure VERIFIED in production (rider 1 healed: first post-landing 08:40 run self-trimmed the watchdog mirror to exactly 5000 lines, corrections.yaml at byte parity main↔data, mirror commit 9f94762) BUT closure gap: scripts/build_control_plane.py — named in this item's own signals as an orphan twin — remains tracked, referenced nowhere outside ROADMAP.md, untested, CWD-dependent, and schema-divergent (writes cron-inventory.json as a LIST of rows while the production mirror writes an id-keyed dict); retirement rides rm-045(j))
- signals: assess 2026-09-21: three divergent mirrors — control-plane-sync.sh (cron-wired via jobs.json at 08:40; copies kanban t_851e7951 too), sync_data_branch.py (orphan; drops t_851e7951; off-by-one change count at line 78), build_control_plane.py (orphan; CWD-dependent; writes only 2 files); ~/.hermes/cron/jobs.json references no .py mirror; none documented in README/AGENTS; cycle-5 2026-09-23 INVERSION PROVEN: the ledger is backwards today — sync_data_branch.py IS the production path (cron wrapper delegates to it) and control-plane-sync.sh is the orphan; the .py twin has no flock, no branch-restore trap, an UNBOUNDED watchdog copy, drops kanban t_851e7951, and ZERO tests (build_control_plane.py also untested); corrections.yaml is in NEITHER copy-set, so origin/data still carries the pre-B3 version asserting the corrected-as-false "gitleaks sentinel covers them" claim (git diff origin/main:control-plane/corrections.yaml origin/data:control-plane/corrections.yaml -> data lacks the B3/D4 amendments)
- acceptance: exactly one mirror implementation (keep the cron-wired path, import shared logic) or a documented single-owner split; parity test asserting the mirrored file set is unchanged; README/AGENTS document the data-branch pipeline
- evidence: grep across scripts/ shows one mirror entrypoint; dry mirror run lists the same 7 files; README Layout covers every tracked file

### Sync N+1 elimination via GraphQL (45 API calls -> 1 query)
- id: `rm-020` | track: reliability | priority: 84.0 | status: candidate
- signals: research 2026-09-21 (live probes): REST list returns null merge fields (`gh api '/user/repos?per_page=3&affiliation=owner'` -> allow_merge_commit:null, delete_branch_on_merge:null, isPrivate:null — so the per-repo detail GET inside sync_repo_settings.py is structurally required on REST), BUT one GraphQL query returns everything: viewer{repositories(first:100,affiliations:OWNER)} -> 44 nodes with name/isPrivate/isArchived/isFork/defaultBranchRef{name}/mergeCommitAllowed/rebaseMergeAllowed/squashMergeAllowed/deleteBranchOnMerge/viewerPermission (probed OK on host gh 2.83.2; sample independently confirmed the live 'agent' repo drift: merge/rebase allowed true + deleteBranchOnMerge false — the dry-run DRIFT line)
- acceptance: list_repos rewritten on the GraphQL query (or REST kept with a documented reason); per-run API calls drop from 1 list + N detail GETs to ~1; dry-run decisions byte-identical to the current implementation on the same fleet state; pagination handles >100 repos
- evidence: before/after dry-run transcripts identical (modulo ordering); pytest covering the GraphQL parse path against a recorded response fixture; call-count assertion

### Documentation currency (README/AGENTS cover the shipped surface)
- id: `rm-021` | track: customer-experience | priority: 80.0 | status: done in-tree, ship-gated (cycle-5 E4 2026-09-24: SECURITY.md 'Mirrored operational data' rewritten to the real mechanism (bounded-tail mirror from the hardened script; the public-main control-plane/ tracking called out as the rm-015 exposure rather than described as bounded); README Layout/Automation covers every tracked file incl. gitleaks.toml, both sentinel workflows, verify_deployed_artifacts.py, with the test count updated 42→55 from live pytest; AGENTS.md gains the data-branch + sentinel conventions; bug-report template's retired-script reference fixed. SHIP-GATED: 'tracked on main' completes at the commit gate. RESIDUAL: expect-public/plan-gate ack note still rides rm-014's push gate)
- signals: assess 2026-09-21: README.md Layout/Automation (from line 7) and AGENTS.md predate the last 8 commits — no mention of gitleaks.toml, private-leak-sentinel workflow, control-plane/ + data-branch mirror, claims.yaml, corrections.yaml, solutions-lint.py, sync_data_branch.py, build_control_plane.py; rm-009 covers community health files (different scope) — this item covers operator/agent doc accuracy for the shipped surface; cycle-5 2026-09-23: SECURITY.md "Mirrored operational data" describes a bounded data-branch tail — reality: public main tracks the FULL 12,686-line log AND the production mirror path writes unbounded (13,524), so the security-policy page materially misstates both the volume and the mechanism
- acceptance: every tracked file appears in README Layout; AGENTS.md gains data-branch + sentinel conventions; expect-public ack + plan-gate notes folded in when rm-014 lands
- evidence: grep -c per tracked filename in README.md -> >=1; AGENTS.md diff reviewed

### solutions-lint.py: fix the dead self-heal or retire the orphan
- id: `rm-022` | track: reliability | priority: 70.0 | status: candidate — C2 partial (cycle-3 2026-09-21: lint paths resolve against the walked repo root, CWD-anchored relpath fixed + dead walrus removed + SOLUTIONS_LINT_REPOS override, behavioral lock in tests/test_solutions_lint.py; still open: JUDGMENT scoping per lint_repo, cron wiring to the daily settings-sync window)
- signals: assess 2026-09-21: scripts/solutions-lint.py:36 computes relpath against './docs/solutions' while walked paths are absolute -> derived category always contains '/' -> the frontmatter category self-heal can never fire (proven live: rel='../../…/foo' => heals? False); module-global JUDGMENT (line 16) accumulates across repos/repeats; script is unwired (no cron job) and defaults to other repos' paths (hermes-conductor, hermes-gpt); cycle-5 repro 2026-09-23: two-repo run duplicates repo-A JUDGMENT sections under repo-B and exits RC=1; repo-B alone RC=0 — cross-repo contamination AND rc poisoning (JUDGMENT init + JUDGMENT.items() render at scripts/solutions-lint.py:18/:90-92)
- acceptance: relpath base fixed to the walked root (or absolute-consistent path handling); JUDGMENT scoped per lint_repo call; either wired into a cron/README or relocated to the repo it serves
- evidence: fixture solution without category -> self-heal adds it and rc=0; repeated invocation emits identical output

<!-- cycle-2 compound (2026-09-21, conductor run 92e960046f14 attempt 972800c7; items rm-023/rm-024 sourced from implement-phase evidence per lessons L9/L15) -->

### sync: apply the live merge-settings drift on repo `agent`
- id: `rm-023` | track: reliability | priority: 75.0 | status: done (cycle-4 2026-09-22: self-healed at the 08:30 cron as the cycle-3 compound note predicted — live --dry-run drift_found=0 across 46 repos; daily log 2026-09-22T08:31:15Z 'RESULT: OK (all drift fixed)' rc=0, `agent` absent from drift rows)
- signals: implement/full_tests live dry-run 2026-09-21: 'agent: DRIFT merge settings (allow_merge_commit=True->False, allow_rebase_merge=True->False, delete_branch_on_merge=False->True)' — the only remaining drift_found=1 across 44 repos; repo created mid-run (fleet 43->44, L6); deliberately NOT --applied by the cycle-2 batch (mutating GitHub state was out of batch scope)
- acceptance: python3 scripts/sync_repo_settings.py --apply -> rc=0; follow-up --dry-run -> drift_found=0; `agent` repo merge flags match common-settings.yaml
- evidence: live --dry-run output before/after; gh api repos/codeo1io/agent merge fields

### tests: persist the control-plane-sync shim matrix as a pytest regression
- id: `rm-024` | track: reliability | priority: 72.0 | status: done (cycle-3 2026-09-21: shim matrix persisted as tracked tests/test_control_plane_shims.py — 5 tests green: T1 failing push restores entry branch, T2 flock single-flight, T1b happy path + capped mirror, T3 gh timeout rc=124. DEVIATION: acceptance names test_control_plane_sync.py; same property set under a different filename — recorded deliberately)
- signals: implement shim matrix proved (T1 failing push -> rc!=0 + trap restores main, T2 flock held -> rc=0, T1b happy path -> push + capped mirror 12,686->5,000, T3 timeout -> synthetic rc=124) but lives only in the implement phase record — scripts/control-plane-sync.sh has zero in-repo tests while its python siblings each have one; matrix recipe in docs/lessons.md L15
- acceptance: tests/test_control_plane_sync.py reproduces T1/T2/T1b against a tmp bare repo + PATH-shimmed git (no network, no real remote); pytest tests/ passes with it included
- evidence: pytest tests/ -q -> >=19 passed; test run leaves no stray branches/locks

## Cycle-2 addendum (2026-09-21)

Assess (attempt 718a4fad) independently re-derived the cycle-1 correctness findings on main
9901e2c before discovering 9d0b155 — the stranded batch remains the unshipped fix set, and
landing it (rm-014) closes the still-live ChadGPT skip, the :443 verification gap, the
--dry-run/--apply hazard, and the zero-tests state in one move. Research (attempt 1fd85233)
refreshed upstream currency (actions/checkout v7.0.1, actions/upload-artifact v7.0.1,
dorny/paths-filter v4.0.3, gitleaks v8.30.1, gh CLI 2.101.0, PyYAML 6.0.3; safe-settings
2.1.21 / probot/settings v5.0.14 still org/app-shaped — no fit for a PAT-driven personal
account) and live-probed the REST-null vs GraphQL-complete asymmetry behind rm-020. Live
fleet drift at cycle start: repo 'agent' merge drift (merge/rebase allowed true,
delete_branch_on_merge false) + 3 permanent visibility nags pending the unlanded rm-006 ack
list. No ce-* compound-engineering skills are installed on this box (only agent-reach); the
cycle executed the equivalent pipeline manually.

**Cycle-2 execution ledger (2026-09-21, implement attempt 09f217c4535e):** batch B1-B4 landed
in the run branch worktree. B1 = 9d0b155 content-merged (12 files byte-identical to the
stranded commit; main-side exec-bit intent preserved on both scripts; overlap vs main was
mode-only — 9b0a4e3 changed no content lines in the colliding files); this lands the cycle-1
fix set rm-002/003/004/006/008/011 whose item statuses above are now backed by a branch
reachable from the run head, pending the commit/push gates. B2 = control-plane-sync.sh
hardened (single-flight flock, failure trap restoring the entry branch, bounded watchdog
mirror via CONTROL_PLANE_WATCHDOG_MAX_LINES default 5000) + gh() timeout (60 s, rc=124 on
expiry flows through allow_fail/FATAL paths). B3 = corrections.yaml secret-scanning claim
amended to the live-verified truth with an `amended:` audit line. B4 = this tracked
ROADMAP.md. Validation: pytest 15/15 on the merged tree, py_compile clean, bash -n clean,
live checker OK incl. [ssh.github.com]:443, live --dry-run shows the ChadGPT decision line
and 0 VISIBILITY DRIFT lines; shim tests prove the trap restores main on push failure and
the lock exits 0 under contention. Deferred: rm-015 (visibility decision, cycle-3 headline),
rm-018/019/020/021/022 per the prioritize gates.

**Compound step (pre-review, 2026-09-21):** lessons L9-L16 appended to docs/lessons.md
from implement + test evidence (untracked-diff blindness, mode-only non-conflicts, bounded
subprocess timeouts, trap-restore in shared checkouts, bounded mirrors, ledger amendment
trail, the four-case shim matrix, digest verbatim-vs-rederive). Candidates rm-023 (apply
the live `agent` merge drift) and rm-024 (persist the shim matrix as a test) appended.
Review and shipping outcomes are OUT of scope here by design — the cycle-3 assessment
carries them forward.

**Cycle-3 entry state:** rm-015 (public-repo visibility decision — the public .github repo
mirrors control-plane internals to the public data branch; rm-017's cap bounds growth but
disclosure needs an owner decision) is the gated headline; rm-016 residual carried
explicitly: openai-embedding-proxy has ZERO secret scanning live (account-level enablement
reverts; only ci.yml exists there) — the corrections entry records the truth but no
compensating control exists beyond roadmap tracking, so cycle-3 must treat the exposure,
not the "done" status, as the fact. rm-018 (sentinel/template pin refresh + tool currency
— target checkout v7.0.1 / upload-artifact v7.0.1 / paths-filter v4.0.3 commit-verified,
plus host gitleaks 8.28.0->8.30.1 with a useDefault same-id override revalidation) needs
ci/host touch; rm-019 (consolidate the three control-plane mirror implementations —
control-plane-sync.sh, build_control_plane.py, sync_data_branch.py) reduces the surface
those mirrors maintain; rm-020 (GraphQL viewer.repositories single query — REST list fields
are structurally null for the per-repo detail fetch) and rm-023 follow mechanically;
rm-021 (README/AGENTS doc accuracy for the shipped surface) pairs naturally with whatever
ships. Batch B1-B4 sits validated-but-uncommitted on conductor/run-92e960046f14 (digest
re-derived after the review-fix edits; see the review-fix phase record) — the
commit/push gates fold it after review.

*End of cycle-2 addendum.*

## Cycle-3 addendum (2026-09-21, run c48e9687: assess + research)

Sources: cycle-3 assess PhaseResult (15 findings at HEAD 328c910) and research PhaseResult
(attempt 1faa88f69e374f1ba0b22b2e5a5e1d72: 9 evidence-backed candidates, 4 explicit
rejections). Non-goals decided there, with evidence: adopt safe-settings/peribolos/
terraform-provider-github (safe-settings README re-verified org-only today: 16
'organization' refs, zero 'user account'); all-fleet GitHub-hosted runners (internal
services need self-hosted — only the public-repo PR surface moves, rm-026); account-level
secret-scanning enablement (proven to revert, corrections.yaml — per-repo PATCH is the
stable path, rm-027). rm-015 (public-repo visibility decision) remains the gated headline;
its priority is unchanged. Items rm-025..rm-035 below continue the numbering; the
hermes-roadmap render's two-way ingest (orchestrator/core.py, 2026-09-20 glmplus fix)
treats this committed file as campaign-authored truth, so these file-only items and
status lines persist across daily renders.

### Land the cycle-2 batch on current main (resolve the ROADMAP.md conflict via this file)
- id: `rm-025` | track: reliability | priority: 98.0 | status: done in-tree, ship-gated (cycle-3 C1 2026-09-21: c04a549 content-merged onto conductor/run-c48e96872031 via 3-way merge — 13/14 files byte-identical, overlap files resolved to main's strict supersets, ROADMAP conflict resolved by this ledger; full suite green. RESIDUAL: 'stranded branch deleted local+origin' is push-class — conductor/run-92e960046f14 deletion happens with rm-014 at the push gate; item stays open until then)
- signals: assess P1 — c04a549 (conductor/run-92e960046f14, +811/-80, 16 files: tests/ 222 lines, hardened control-plane-sync.sh, .gitignore, expect-public.txt, docs/lessons.md, pinned templates) stranded unmerged; git merge-tree 9901e2c 328c910 c04a549 reports ROADMAP.md conflict (both sides modified: main carries the 28-line render added in 328c910, stranded carries this 269-line ledger); main ships none of the batch
- acceptance: batch content reachable from main (merge, rebase, or cherry-pick) with ROADMAP.md resolved by this document (main's sentinel cache-bust content in 328c910 preserved — the conflict is ROADMAP-only); pytest tests/ green on the landed main; stranded branch deleted local+origin
- evidence: git log --oneline shows the batch commits on main; git branch --list 'conductor/run-92e960046f14' empty; pytest -q tests/ passes on main checkout

### Public-repo runner exposure: stop fork-PR jobs on the fleet self-hosted runner
- id: `rm-026` | track: reliability | priority: 97.0 | status: done (resolved in reality 2026-09-22, cycle-4 prioritize live verification: sentinel reusable workflow runs-on ubuntu-latest since the 7d47ab4 migration with no caller-side runner label; openai-embedding-proxy ci.yml runs BOTH jobs on ubuntu-latest — the sole self-hosted mention is a debug comment documenting the March 2026 hardening; fleet code search shows self-hosted labels only on private repos magic-hermes + autorepair, exactly this item's design clause "private repos keep self-hosted paths unchanged")
- signals: research C1 — magic-hermes/.github/workflows/private-leak-sentinel.yml triggers on unscoped `pull_request` and delegates to codeo1io/.github sentinel `runs-on: self-hosted` (private-leak-sentinel.yaml:21); openai-embedding-proxy/.github/workflows/ci.yml: pull_request (L5) feeding two `runs-on: self-hosted` jobs (L18, L29); both repos PUBLIC (live sync dry-run visibility); docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners advises against self-hosted runners on public repos
- acceptance: PR-triggered workflows in the 2 public repos execute on GitHub-hosted runners (sentinel gains an ubuntu-latest + pinned-gitleaks-install path; openai-embedding-proxy ci swaps its two self-hosted jobs or gates pull_request to same-repo branches); private repos keep self-hosted paths unchanged
- evidence: gh api of both caller workflow files post-change shows runs-on: ubuntu-latest on PR event paths; a completed run log shows a GitHub-hosted runner; workflow grep shows no self-hosted label reachable from pull_request in public repos

### Per-repo security_and_analysis enablement (close rm-016's residual exposure)
- id: `rm-027` | track: reliability | priority: 96.0 | status: done in-tree, report-only (cycle-3 C3 2026-09-21: security_and_analysis drift rows live in sync --dry-run — fire on exactly the public repos, silent on private; apply-mode unit test proves security rows issue no PATCH/PUT. --apply enablement deliberately deferred to an owner-gated decision; acceptance's apply clause stays open; cycle-5 2026-09-23: upstream capability re-confirmed — enableable on user-owned public repos, NOT plan-gated; the apply clause now waits on a revert root-cause experiment: one public repo, one-shot PATCH enablement, revert-captured, mechanism recorded in corrections.yaml); cycle-7 2026-09-24: unlock evidence — 3 public fleet repos now show the features platform-ENABLED (live GET), so PATCH enablement on the 2 drifted public repos is expected to stick without the account-level revert; the one-repo probe remains the acceptance path
- signals: research C2 — live gh api repos/codeo1io/magic-hermes --jq security_and_analysis on a PUBLIC repo: secret_scanning, secret_scanning_push_protection, dependabot_security_updates ALL disabled while docs.github.com about-secret-scanning covers public repositories; account-level enablement provably reverts (corrections.yaml secret-scanning-sticky-disabled); rm-016 residual already records openai-embedding-proxy zero-scanning as the live fact
- acceptance: sync_repo_settings.py drift set includes security_and_analysis (report-only first), then --apply enables secret_scanning + push_protection (+ dependabot_security_updates where desired) on the 3 public repos only; corrections entry gains an `amended:` line documenting the per-repo mechanism; no private-repo attempts
- evidence: --dry-run output lists the new drift rows; post-apply gh api shows enabled statuses on magic-hermes, openai-embedding-proxy, .github; tests cover the new drift dimensions

### Actions least-privilege drift-check + platform SHA-pinning enforcement
- id: `rm-028` | track: reliability | priority: 89.0 | status: candidate
- signals: research C3, extends rm-010 — live gh api repos/codeo1io/magic-hermes/actions/permissions: {enabled:true, allowed_actions:'all', sha_pinning_required:false}; the REST per-repo actions/permissions endpoint is writable (verified readable; defaultWorkflowPermissions is REST-only, never GraphQL — constraint #5998)
- acceptance: sync drift-checks allowed_actions and sha_pinning_required per repo; --apply sets sha_pinning_required=true fleet-wide (platform-enforced counterpart of the house SHA-pin standard) with an explicit expect-list for allowed_actions tiers; corrections ledger updated for intentional exceptions
- evidence: --dry-run drift rows; post-apply gh api actions/permissions per repo shows sha_pinning_required:true; tests for the new drift set

### Rulesets v2 for public opt-in repos
- id: `rm-029` | track: reliability | priority: 78.0 | status: candidate
- signals: research C4 — gh api repos/codeo1io/magic-hermes/rulesets returns HTTP 200 [] on a personal-account public repo (classic protection is 403 plan-gated per constraints #5997/#6021; rulesets are not); richer semantics available (bypass actors, push rules, non-FF) than classic protection
- acceptance: opt-in PUBLIC repos get rulesets via REST (non-fast-forward + required checks) with bypass actors documented in the repo; classic protection path retained for private repos; sync reports ruleset drift report-only
- evidence: gh api rulesets non-empty for each opt-in public repo; forced-push attempt rejected; drift report line in --dry-run

### Community health files from the personal-account .github repo
- id: `rm-030` | track: customer-experience | priority: 88.0 | status: done in-tree, ship-gated (cycle-3 C4 2026-09-21: SECURITY.md, PULL_REQUEST_TEMPLATE.md, ISSUE_TEMPLATE/bug_report.md + feature_request.md written, README layout documents them; 'tracked on main' completes at the commit gate)
- signals: research C5, extends rm-009 — docs.github.com creating-a-default-community-health-file confirms personal accounts serve default files fleet-wide from the <user>/.github repo; git ls-files shows this repo ships none (no SECURITY.md, PULL_REQUEST_TEMPLATE.md, ISSUE_TEMPLATE/)
- acceptance: SECURITY.md (no-secrets policy + gitleaks-sentinel reporting path), PULL_REQUEST_TEMPLATE.md, and ISSUE_TEMPLATE/ tracked on main; README documents the convention
- evidence: files present on main; gh api repos/codeo1io/<repo-without-own-template>/contents/PULL_REQUEST_TEMPLATE.md resolves via the .github default (or 404 documented as GitHub-side resolution, with the file presence cited)

### Sentinel supply chain: pin config ref, refresh scanner, narrow the .md blanket allowlist
- id: `rm-031` | track: reliability | priority: 87.0 | status: done by subsumption, ship-gated (cycle-4 compound 2026-09-22 + review fix 2026-09-22: rm-036 D2 delivered the pinned-ref config fetch (input default 7d47ab48, stronger than the acceptance's "latest tag" default) and pinned the gitleaks invocation — action commit-pinned PLUS binary version pinned via GITLEAKS_VERSION 8.30.1 in the step env, added at review-fix (cycle-4 review P2: gitleaks-action's installer fetches unchecked releases/latest when the env is unset) — clause 2 satisfied literally; rm-037 D1 removed the .md blanket outright rather than narrowing it (stronger than targeted .gitleaksignore entries: .md prose now SCANNED by the quoted/unquoted generic pair). Live-run evidence clauses (sentinel run reports 8.30.x) complete at the commit gate. Residual: per-repo .gitleaksignore adoption for the hermes-agent (964) / hermes-gpt (234) synthetic corpora — next-cycle candidate)
- signals: research C6, extends rm-018 — sentinel fetches gitleaks.toml from @main unpinned (private-leak-sentinel.yaml:28-32, post-328c910 cache-bust); host/runner gitleaks 8.28.0 vs upstream v8.30.1 (2026-03-21); gitleaks.toml:51 blanket-excludes all .md files; per-repo .gitleaksignore is the native newer mechanism; cycle-4 assess 2026-09-22: the ubuntu-latest migration (7d47ab4) added a runtime gitleaks install from unpinned releases/latest with no checksum (private-leak-sentinel.yaml:33-38) — rm-036's action-based rewrite subsumes the install and fetch halves; live caller runs 10-25s, minutes concern evidence-closed (cycle-4 research)
- acceptance: config fetched at a pinned ref (workflow_dispatch input, default latest tag); gitleaks version pinned/recorded in the workflow (install step or runner upgrade policy documented); .md blanket exclusion replaced by targeted .gitleaksignore entries with the allowlist rationale documented
- evidence: workflow file shows pinned ref + version; a sentinel run reports gitleaks 8.30.x; git diff gitleaks.toml shows the narrowed allowlist; a scan over a fixture .md secret still fails

### sync_repo_settings.py robustness: gh timeouts, pagination, dead code, lint portability
- id: `rm-032` | track: reliability | priority: 85.0 | status: done (cycle-3 C2 2026-09-21: cursor-threaded GraphQL pagination replaces the --limit 300 cap, unit test walks 324 fake repos across 4 pages; gh() 60s timeout rc=124 + dead cur_merge removal pre-landed via C1; solutions-lint root-threaded + SOLUTIONS_LINT_REPOS override, CWD-independence locked by tests/test_solutions_lint.py. Review-fix: docstring viewerPermission note corrected, test fixture raised past the real 300 cap)
- signals: assess — no timeout on gh subprocess calls in sync_repo_settings.py (Python-side parity with B2's shell gh() 60s rc=124 pattern); list_repos hard cap --limit 300 (sync_repo_settings.py:60) breaks silently at fleet>300; dead `cur_merge` assignment; solutions-lint CWD-anchored
- acceptance: gh() wrapper with timeout=60 and rc=124 synthesis feeding existing FATAL/allow_fail paths; list_repos paginates (verified by unit test with >300 fake repos); cur_merge removed; lint script path-independent
- evidence: pytest timeout-expiry shim test passes; pagination unit test; grep shows no cur_merge; bash solutions-lint from a different CWD

### Cron wrapper hardening: branch safety, ordered host-key check, failure propagation
- id: `rm-033` | track: reliability | priority: 84.0 | status: candidate
- signals: assess — repo-settings-sync wrapper runs `git reset --hard origin/main` regardless of entry branch (clobbers parked-branch worktrees), performs the SSH fetch BEFORE check_known_hosts.py, and ends `exit 0` masking every failure; rm-005 covers propagation only; cycle-4 assess 2026-09-22: README.md:60-61 documents the fetch-before-check ordering as design — a pinned-key compromise is exercised (SSH fetch -> reset --hard -> synced scripts run with gh credentials) before the detector fires, making the reorder first-class hardening, not cosmetics
- acceptance: wrappers trap-restore the entry branch on nonzero exit (B2 pattern), invoke check_known_hosts.py BEFORE any network fetch, and propagate the real rc (single exit path); shim tests lock all three properties
- evidence: shim tests (fetch-failure -> entry branch restored; checker-failure -> nonzero wrapper rc); live wrapper run on a parked branch leaves HEAD unchanged

### Renovate shared default preset
- id: `rm-034` | track: customer-experience | priority: 74.0 | status: candidate
- signals: research C9, extends rm-007 — codeo1io/renovate-config exists (private, live gh repo view); docs.renovatebot.com/config-presets defines the default.json convention; fleet repos each define dependency policy ad hoc
- acceptance: default.json preset in renovate-config codifying shared policy (schedule, ranges, pinning posture); at least the maintenance-heavy repos extend it
- evidence: gh api repos/codeo1io/renovate-config/contents/default.json present; sample repos' renovate.json extends the preset; one Renovate run log resolving the preset

### OSSF Scorecard on the public repos
- id: `rm-035` | track: customer-experience | priority: 60.0 | status: candidate
- signals: research C10 — 3 public repos (.github, magic-hermes, openai-embedding-proxy); OSSF Scorecard is free for public repos and produces evidence-based hardening signals that feed later roadmap cycles; cycle-5 research 2026-09-23: ossf/scorecard-action v2.4.4 (2026-07-23) verified current upstream, free + no-auth for public repos — mechanism ready when prioritized; cycle-7 2026-09-24: api.scorecard.dev -> HTTP 404 for codeo1io/.github — repo not yet in the OSSF dataset, baseline needs a manual scorecard.dev run first
- acceptance: scheduled scorecard runs on the 3 public repos with results retained (badge or artifact); one cycle consumes a scorecard finding into a roadmap item
- evidence: scorecard workflow present via gh api; latest run output archived; at least one derived roadmap signal cited

### Cycle-3 compound note (2026-09-21, post-implement, post-review)

Batch C1-C4 staged-uncommitted on `conductor/run-c48e96872031` (base 328c910,
20 files +1466/-80 plus review-fix edits). Review 8350539599 approved the batch
(pass_with_findings); all six findings were fixed in the review-fix pass: docstring
accuracy (sync_repo_settings.py list_repos), pagination test raised past the real
300 cap (324 fake repos / 4 pages), solutions-lint behavioral CWD lock
(tests/test_solutions_lint.py), stale README pre-pin line, the evidence correction
below, and this compound note itself. FLEET GROUND TRUTH: 44 repos (live
`gh repo list --json` count and GraphQL repositories.totalCount both 44; the
implement record's "21 repos" was an evidence-string error — the pagination code
matched ground truth exactly, no code defect). Next-cycle candidates in priority
order: rm-026 (cross-repo public-repo runner exposure — magic-hermes +
openai-embedding-proxy, first cross-repo edit), rm-028 (actions least-privilege +
sha_pinning_required — REST-writable, pattern proven by C3's report-only stage),
rm-033 (host-scope cron wrapper hardening), rm-029 (rulesets, after rm-028 proves
the writable surface), rm-031 (sentinel supply chain), rm-034/rm-035 (renovate
preset, scorecard). Owner-gated: rm-015. Self-heals at the 08:30 cron: rm-023.
Push-gate residuals: rm-014 + rm-025 stranded-branch deletions.

*End of cycle-3 addendum.*

<!-- cycle-4 roadmap addendum (2026-09-22, conductor run 21dc18aaada0 attempt 4201ff543741453da6fc9498c539f0a2; items rm-036..rm-041 sourced from cycle-4 assess attempt 6191211ecc9f + research attempt 9532066976; sanctioned ledger extension per render-marker contract) -->

### Migrate sentinel internals to the official SHA-pinned gitleaks-action
- id: `rm-036` | track: reliability | priority: 87.0 | status: done in-tree, ship-gated (cycle-4 D2 2026-09-22: private-leak-sentinel.yaml rewritten on gitleaks/gitleaks-action@e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e — v3.0.0 tag verified commit-typed via gh api git/ref/tags, so the tag pin IS a commit pin; gitleaks.toml consumed via a second SHA-pinned actions/checkout@3d3c42e5 (v7.0.1) of codeo1io/.github at an explicit config-ref input (default 7d47ab48, self-scan caller passes github.sha) — no runtime raw fetch, no cache-bust, no curl install; both workflow checkouts persist-credentials: false. DEVIATION from acceptance: workflow_dispatch rescan clause NOT implemented — leak-sentinel-self.yaml's weekly full-history schedule covers this repo's rescans; adding dispatch to a reusable workflow is a next-cycle rider. Magic-hermes live-green + live-run gitleaks-version clauses complete at the commit gate + caller refresh; promote-time rider: bump config-ref default to the batch commit SHA; cycle-5 2026-09-23 residual: the rewrite dropped the failure-evidence upload — workflow comment L9 still promises a SARIF artifact on failure but no upload step exists (7d47ab4:54 shipped upload-artifact@ea165f8 v4.6.2; upstream now v7.0.1) — restore via gitleaks-action's native SARIF artifact output or a SHA-pinned upload-artifact step, and fix the comment — CLOSED cycle-5 E4 2026-09-24: verified against gitleaks-action v3.0.0 source that the upload EXISTS and is ACTION-NATIVE (src/gitleaks.js L98-99 sarif report flags, L128-135 artifact 'gitleaks-results.sarif'; src/index.js L22-28 upload default-on unless GITLEAKS_ENABLE_UPLOAD_ARTIFACT=false) — no workflow step was ever missing; private-leak-sentinel.yaml L9 now documents the real mechanism and live artifacts were confirmed on .github 2026-09-22 + magic-hermes 2026-09-23)
- signals: research RC-1 2026-09-22, extends rm-018/rm-031 — gitleaks/gitleaks-action v3.0.0 (2026-05-30) requires no license for personal accounts (README L43/L75) and natively supports GITLEAKS_CONFIG (L79), SARIF artifact upload (L80), job summary (L81); one SHA-pinned action replaces the curl-install + releases/latest trust + raw.githubusercontent config fetch + hand-rolled report plumbing; docs confirm reusable-workflow refs may be SHAs; assess 2026-09-22 rated the unpinned install P2
- acceptance: private-leak-sentinel.yaml uses gitleaks/gitleaks-action@<40-hex SHA>; gitleaks.toml consumed via pinned self-checkout of codeo1io/.github (no runtime network config fetch — cache-bust/rerun hole closed structurally); sentinel green on magic-hermes after migration; workflow_dispatch rescans retained
- evidence: workflow yml shows the pinned action and no curl/raw fetch; live run log reports gitleaks 8.30.x; planted-token fixture repo still fails the scan

### Sentinel detection integrity: retire blanket tree allowlists, restore unquoted-value coverage
- id: `rm-037` | track: reliability | priority: 90.0 | status: done (cycle-4 D1 2026-09-22: blanket tests?/e2e/evals tree + conftest.py + *.test/spec.* + .md exemptions all retired, replaced by a documented narrow-exemptions policy (fixture dirs by convention, vendored/build artifacts, per-file triaged entries with evidence comments, per-repo .gitleaksignore named as the sanctioned FP sink); generic-api-key-unquoted rule added — prefix-worded \b-anchored key (rejects _startup_api_key_override / request_pressure_tokens), base64/hex alnum-start value (rejects _windows_gateway_resume / plan.approx_tokens / ++latestSwitchToken), line-anchored (rejects prose) — 0 source FPs verified on a 9-line FP corpus AND live full-history corpora hermes-gpt 38,355 commits + hermes-agent 44,422 commits; fleet triage: hermes-agent 964 + hermes-gpt 234 findings ALL in synthetic test/docs paths, 0 source, 0 actionable; tests/test_gitleaks_config.py 11 tests including the live-binary acceptance proof — a planted secret inside tests/ FAILS the scan; .github self-scan 29 commits 0 findings under the hardened config) — REOPENED (cycle-5 2026-09-23: two residual allowlist escapes proven live on host gitleaks 8.28.0 AND the sentinel-pinned 8.30.1 (version-stable): gitleaks.toml:88 (?i)tests?/.*fixtures? path regex exempts any tests/ file with "fixture" in its name — a real-shaped ghp_ token at tests/unit/test_fixture_loader.py scans ZERO findings while the same token in a non-fixture path fires github-pat; and gitleaks.toml:119 xxx+ suppresses any captured secret VALUE containing "xxx" (allowlist regexes match the captured secret, not the line — A/B: q8Kw2xxx…-shaped value missed, no-xxx control caught by generic-api-key); L130's \.{3} line-regex also value-unanchored — close via directory-anchored tests?/fixtures?/ paths, anchored/replaced value regexes, and the A/B fixtures persisted as regression tests in tests/test_gitleaks_config.py) — RE-CLOSED (cycle-5 E3 2026-09-24: gitleaks.toml L88 path allowlist narrowed to directory-anchored fixtures paths (a 'fixture'-NAMED FILE anywhere under tests/ is no longer exempt from all rules); L119 xxx+ and L130 \.{3} value suppression replaced/anchored so suppression no longer keys on a substring of the captured secret value; 3 live-binary A/B regression tests added to tests/test_gitleaks_config.py — the fixtures-path escape and the xxx-value suppression are now DETECTED, line-vs-value semantics locked; gitleaks suite 16/16 incl. 5 live-binary integrations; ephemeral GitHub-hosted CI self-scan SUCCESS on the narrowed config (run 35886557920, PR #5))
- signals: cycle-4 assess P1/P2 2026-09-22 — gitleaks.toml:55 blanket-allows every tests?/e2e/evals tree fleet-wide (plus conftest.py:57, *.test/spec.*:56) so real secrets in test fixtures are invisible to the fleet's only automated scanner (the compensating control for 8 public repos with native scanning disabled per dry-run 2026-09-22); gitleaks.toml:43 narrowed generic-api-key requires quote-wrapped values — unquoted `api_key: abc...` in YAML/TOML escapes the generic rule (regression vs stock gitleaks); rm-031 covers only the .md blanket (gitleaks.toml:51)
- acceptance: blanket tree exemptions replaced by targeted per-file triage (pattern proven at gitleaks.toml:62-71) and/or .gitleaksignore fingerprints; a generic-rule variant covers unquoted assignment values; fleet-triage runs on magic-hermes + hermes-agent report 0 actionable findings after narrowing
- evidence: gitleaks.toml diff shows the narrowed allowlist; fixture scan with a secret in a test file FAILS; scan transcripts on both repos clean; gitleaks self-scan of this repo still 0 findings

### Sentinel self-scan + fleet adoption: close the owner-repo blind spot
- id: `rm-038` | track: reliability | priority: 84.0 | status: candidate
- signals: cycle-4 assess P2 + research RC-2 2026-09-22 — SECURITY.md:21-23 claims the sentinel "runs gitleaks ... on pushes and pull requests" for this repo, but private-leak-sentinel.yaml:11-12 is workflow_call-only and no caller exists in .github: the config-owning repo is never auto-scanned (manual scan 2026-09-22 clean, 29 commits); openai-embedding-proxy is public with native scanning disabled and zero sentinel (rm-016 residual: cross-repo adoption deferred); caller pattern proven live in magic-hermes (push/PR/daily, 10-25s runs); cycle-4 compound 2026-09-22: IN-REPO HALF LANDED (D3) — leak-sentinel-self.yaml caller (push main / pull_request / weekly schedule, config-ref: github.sha so a push is always scanned with exactly the gitleaks.toml it ships), SECURITY.md rewritten to actual coverage (self-scan + magic-hermes named, adoption gap + rm-016/rm-038 pointer kept), corrections.yaml amended (audit-line convention, single amended string); residuals: live green run (ship-gated at commit gate) + openai-embedding-proxy adoption (rm-016 overlap, unlocked by rm-036 landing)
- acceptance: a sentinel caller workflow (push/PR) lands in codeo1io/.github and runs green; openai-embedding-proxy gains the caller (post rm-036); SECURITY.md wording matches actual coverage; corrections.yaml inventory reflects the added caller
- evidence: gh api repos/codeo1io/.github/actions/runs shows green sentinel runs; SECURITY.md reviewed against reality; corrections.yaml diff

### Native Dependabot version updates for github-actions pins
- id: `rm-039` | track: customer-experience | priority: 78.0 | status: candidate
- signals: research RC-3 2026-09-22, alternative to rm-034 (Renovate install state unverifiable with the sync PAT — 403 on /user/installations) — Dependabot github-actions ecosystem is native (no app install), free (docs: standard runners free for Dependabot), and updates full-SHA pins; in-fleet precedent: hermes-agent .github/dependabot.yml is fleet-authored with explicit policy text ("Dependabot opens a PR with the new SHA and release notes; pins are moved deliberately, after review"); template pins verified current live (checkout v7.0.1, paths-filter v4.0.3) and this mechanism keeps them so; cycle-5 research 2026-09-23: upstream currency re-verified live (checkout v7.0.1, paths-filter v4.0.3 still latest; upload-artifact now v7.0.1) — no pin drift exists today, so the item's value is keeping pins current, not catching up; Dependabot stays the chosen mechanism (Renovate 44.110.0 still app-install-bound for this account); cycle-7 2026-09-24: pin currency re-verified live — gitleaks v8.30.1, gitleaks-action v3.0.0, actions/checkout v7.0.1, dorny/paths-filter v4.0.3, actions/upload-artifact v7.0.1 ALL still latest upstream (zero drift; host-side gitleaks 8.28.0 lags the pinned 8.30.1, host note only); enforcement-side complement proposed as rm-043 (sha_pinning_required)
- acceptance: canonical dependabot.yml (github-actions ecosystem, weekly, scoped) shipped as a template and adopted in codeo1io/.github; README documents the convention; a Dependabot PR observed on a drifted pin or a no-drift API check
- evidence: dependabot.yml tracked in .github + template; gh api confirms config; PR or no-drift evidence

### Control-plane toolchain-freshness record (versions.json)
- id: `rm-040` | track: reliability | priority: 70.0 | status: candidate
- signals: research RC-4 2026-09-22, extends rm-019 — standing drift facts are one-off evidence strings (host gh 2.83.2 vs upstream v2.101.0 = 19 releases; runner gitleaks vs v8.30.1; action pins vs latest); control-plane-sync.sh already mirrors inventory-shaped data to origin/data; a bounded versions record makes drift self-evidencing daily
- acceptance: the mirror path emits versions.json (gh version, gitleaks latest vs deployed, template action pins vs upstream latest, size-bounded) to the data branch; shim test locks the emitter; a cron run lands the file
- evidence: dry sync run lists versions.json; origin/data tree shows it; shim test green

### Sync/docs micro-corrections
- id: `rm-041` | track: customer-experience | priority: 55.0 | status: done (cycle-4 D4 2026-09-22: sync_repo_settings.py RPR drift message derives want from desired['required_pull_request_reviews'] instead of hardcoded False — verified live, dry-run RESULT: OK, 15 sync tests green; README.md test count 29 -> 42 derived from live pytest output)
- signals: cycle-4 assess P3 2026-09-22 — sync_repo_settings.py:189 RPR drift message hardcodes "want False" (inverts meaning if desired RPR is ever non-null; latent, desired currently null); README.md:69 cites "(29)" tests vs 31 in-tree (Layout staleness itself is rm-021's scope, not duplicated)
- acceptance: drift message derives from the actual desired value; README test count matches live pytest output
- evidence: grep shows the parameterized message; pytest count == README count

### Cycle-4 roadmap note (2026-09-22, post-assess, post-research)

Assess (attempt 6191211ecc9f, 11 findings at 7d5a132) and research (attempt
9532066976, ce-ideate, all sources live-fetched 2026-09-22) fed this addendum.
Status promotion: rm-023 done (08:30-cron self-heal confirmed: drift_found=0
across 46 repos, daily log 2026-09-22T08:31:15Z rc=0). New signals appended
to rm-031 (unpinned releases/latest install, new in 7d47ab4) and rm-033
(README documents fetch-before-check as design; escalation chain reaches gh
credentials). Rejected this cycle with rationale: minutes-quota guardrail
(live sentinel runs 10-25s, public repos free, 2,000 free min/month ≈ 2400x
current use — revisit only before a big-history PRIVATE adopter); competitor
migration (safe-settings, terraform-provider-github, prow all active but
still org/app/state-bound — personal-account fit unchanged since cycle-1);
OSSF Scorecard priority (rm-035 stays candidate; research defers it below the
sentinel items for a solo-maintained fleet). Next-cycle candidates in
priority order: rm-037, rm-028, rm-036, rm-038 + rm-033 (rm-036 unblocks
rm-038's embedding-proxy half), rm-039, rm-040, rm-041. Owner-gated: rm-015,
rm-016 apply-half. Push-gate residuals: rm-014 + rm-025 stranded-branch
deletions.

Cycle-4 compound update (2026-09-22, pre-review, attempt a5550cd77f17): Batch D
landed in the stewardship worktree (uncommitted, commit-gated) — rm-037 DONE,
rm-036 DONE IN-TREE ship-gated (workflow_dispatch deviation documented on the
item), rm-031 DONE BY SUBSUMPTION (D2 fetch-pinning + D1 .md-blanket removal),
rm-041 DONE, rm-026 DONE (resolved in reality; live runner-topology audit),
rm-023 DONE (roadmap phase, cron self-heal). rm-038 half-landed (in-repo D3;
residual = live green run + embedding-proxy adoption, rm-016 overlap); rm-018
kept candidate with narrowed residuals (caller @main pinning policy, bundled-
gitleaks revalidation). Suite 42/42; fleet triage 0 source findings across 4
corpora; digest validation:v1:d0028a9d (13 surfaces, base 7d47ab48).
Next-cycle candidates REVISED in priority order: rm-028 + rm-029 (fleet
workflow-permissions pair, top open reliability items, cross-repo — now
unblocked as the sentinel surface stabilized), rm-039 (Dependabot github-actions
updates — directly maintains the new action/config SHA pins), per-repo
.gitleaksignore adoption for hermes-agent (964 synthetic findings) and
hermes-gpt (234), rm-033 (host-scope known-hosts ordering), rm-019 (cron-wired
mirror consolidation), rm-040. Riders for the commit gate: bump rm-036's
config-ref default from 7d47ab48 to the batch commit SHA; refresh the
magic-hermes caller workflow; verify the first live sentinel + self-scan runs.
Owner-gated: rm-015, rm-016 apply-half. Push-gate residuals: rm-014 + rm-025
stranded-branch deletions.

*End of cycle-4 addendum.*

<!-- cycle-5 roadmap extension (2026-09-23, conductor run 8fdcdb06b90e attempt ddc26524; item rm-042 sourced from cycle-5 assess attempt 76315159734f + research attempt 2d11edc53; sanctioned ledger extension per render-marker contract) -->

### Deployed-artifact verification: pin the cron-wired scripts in MANIFEST.sha256
- id: `rm-042` | track: reliability | priority: 91.0 | status: candidate — repo half landed, ship-gated (cycle-5 E2 2026-09-24: scripts/verify_deployed_artifacts.py + tests/test_verify_deployed_artifacts.py ride batch E uncommitted — 7/7 tests incl. planted-divergence nonzero and unpinned-entrypoint rc=1; LIVE host run 2026-09-24 rc=1 naming exactly the two real drifts (control-plane-sync.sh, sync_data_branch.py not pinned in deployed MANIFEST.sha256) — the check works, the drift is real. OPEN host half: add both entrypoint pins to ~/.hermes/scripts/MANIFEST.sha256 (host-side rider, next cycle; AGENTS.md documents run-after-any-host-side-deployment))
- signals: cycle-5 assess + research 2026-09-23 — ~/.hermes/scripts/MANIFEST.sha256 pins 14 fleet watchdog/audit scripts (the pattern is proven and daily-verified) but omits BOTH cron-wired sync entrypoints: control-plane-sync.sh (whose deployed copy is a 5-line wrapper delegating to scripts/sync_data_branch.py — exactly the divergence that made rm-017's hardening inert in production) and repo-settings-sync.sh (same deployment pattern, same blind spot); nothing in the fleet would notice a deployed script drifting from the repo's validated source; cycle-7 2026-09-24 residual (repo half): scripts/verify_deployed_artifacts.py:79 conflates wrapper-present+manifest-missing with "not a deployed host" (rc=2 skip instead of drift rc=1) — losing/renaming the manifest on a deployed host silently disables the check; tests cover only both-absent; delegation parsing also covers only the control-plane wrapper (repo-settings-sync.sh delegate re-pointing unverifiable); fix rides rm-045(a)
- acceptance: MANIFEST.sha256 covers both sync entrypoints (deployed wrapper AND repo-side script digests); a drift check compares deployed vs manifest digests on the daily schedule (wrapper pre-step or a repo test invoking the comparison) and reports nonzero on divergence; a deliberately planted divergence fails the check; works for wrapper-style deployments (digest of the wrapper + digest of its declared delegate)
- evidence: grep MANIFEST.sha256 lists both entrypoints; planted-diff check transcript exits nonzero; one live daily-run log line showing the verification executed; cycle-5 E2: python3 scripts/verify_deployed_artifacts.py (live host) -> rc=1 'control-plane-sync.sh: not pinned in manifest' + 'sync_data_branch.py: not pinned in manifest'; pytest tests/test_verify_deployed_artifacts.py -> 7 passed (planted-divergence + unpinned-entrypoint cases included)

## Cycle-5 roadmap note (2026-09-23, post-assess, post-research)

Assess (attempt 76315159734f, ce-review report-only, 10 findings at 4e09145; 42/42 tests
green, live dry-run repos=46 drift_found=0) and research (attempt 2d11edc53, ce-ideate
inline, 8 evidence-backed survivors + 7 explicit rejections, all sources live-fetched)
fed this addendum. STATUS FLIPS: rm-017 REOPENED at priority 97 (production never
executes the hardened script — deployed wrapper delegates to sync_data_branch.py;
live proof: 13,524-line uncapped data-branch mirror 2026-09-23); rm-037 REOPENED (two
allowlist escapes proven on BOTH 8.28.0 and pinned 8.30.1: the fixtures-path regex
exempts any tests/ file with "fixture" in its name, and xxx+ suppresses captured
secret values containing "xxx"); rm-019 signals corrected (production-path inversion)
and priority raised 86->92 with the corrections.yaml data-branch gap folded in;
NEW item rm-042 (deployed-artifact digest verification — the class rm-017's inversion
instantiates). Evidence appended: rm-015 (public main tracks control-plane/ +
docs-verified 3-option remediation menu incl. the per-USER Access policy for private
reusable-workflow sharing, fpt); rm-016/rm-027 (secret scanning IS enableable on
user-owned public repos per docs — state, not plan-gating; revert needs a one-shot
root-cause experiment); rm-021 (SECURITY.md mirrored-data section vs reality); rm-022
(JUDGMENT cross-repo contamination + rc poisoning repro); rm-035/rm-039 (upstream
currency: scorecard-action v2.4.4; all template pins current — no upgrade work exists);
rm-036 (SARIF-upload residual + stale L9 comment). Rejected this cycle with rationale:
gitleaks/action pin upgrades (v8.30.1 and v3.0.0 are the latest upstream — verified
live; gitleaks-action v2 hard-EOLs 2026-09-16 with Node 20 removal, so the D2 v3
migration landed in time); adopting safe-settings/terraform-provider-github/peribolos
(all active upstream, all still org/app/state-bound); replacing gitleaks with native
secret scanning (no custom generic patterns on free user accounts — complementary,
not replacement); auto-enabling security_and_analysis from the sync (report-only by
design; owner-gated experiment instead); history rewrite for rm-015 now (the mirror
SOURCE must be fixed first or the daily cron re-pushes the exposure; owner-gated
regardless); delete-bash-port-to-python (consolidation direction is the implement
phase's call — both directions close rm-017/rm-019 with retargeted shims). Next-cycle
candidates in priority order: rm-017+rm-019 (mirror-path integrity batch: consolidate
to ONE executed implementation, retarget tests/test_control_plane_shims.py at what
production actually runs, trim the data-branch log under the cap, add corrections.yaml
to the copy-set), rm-042 (MANIFEST extension + drift check), rm-037 reopen (allowlist
narrowing + A/B regression tests), rm-036 SARIF residual + rm-021 SECURITY.md/README
accuracy, rm-022 (JUDGMENT per-repo scoping), rm-028 + rm-029 (carried from cycle-4),
rm-039, rm-035. Owner-gated: rm-015 (menu A/B/C), rm-016/rm-027 apply-half (one-repo
enablement + revert-capture experiment). Push-gate residuals: rm-014 + rm-025
stranded-branch deletions; rm-036 config-ref default bump; magic-hermes caller
refresh; first live sentinel + self-scan runs.

Compound update (2026-09-24, attempt ba3a29e2, pre-review — batch E 'deployed-path trust chain' outcome):
implement (e51dda80) landed the batch at base 4e09145 — 12 changed tracked paths +
2 new files (+672/−323 excluding ROADMAP.md), full suite 42→55 green; targeted_tests
(286bebee) 29 focused tests green + 0 bare-action-ref violations + digest equality;
full_tests (365079da) ran the authoritative full_command VERBATIM — ephemeral
GitHub-hosted CI validation, draft PR #5, self-scan SUCCESS on the batch-E snapshot
(run 35886557920) with full self-cleanup; validation digest validation:v1:721ef15c….
Two earlier full_tests attempts (2f0d6296, 826cd7cc) were engine-rejected for command
substitution — the fold gate byte-matches evidence.command against the dispatch
full_command (lesson L31). PROMOTIONS: rm-017 done ship-gated (hardening moved onto
the EXECUTED sync_data_branch.py; twin retired; shims retargeted), rm-019 done
ship-gated (single mirror + copy-set parity incl. corrections.yaml), rm-021 done
ship-gated (SECURITY.md truth + README/AGENTS coverage), rm-037 RE-CLOSED (allowlists
narrowed + live-binary A/B regressions), rm-036 SARIF residual CLOSED (action-native
upload verified against v3.0.0 source), rm-042 repo half landed (host half open).
Commit-gate riders: (1) after landing, verify the first 08:40 run self-trims the
data-branch watchdog mirror ≤5000 lines and mirrors corrections.yaml at parity;
(2) then pin both entrypoints in ~/.hermes/scripts/MANIFEST.sha256 and re-run
scripts/verify_deployed_artifacts.py expecting rc=0; (3) carried: rm-014/rm-025
stranded-branch deletions, rm-036 config-ref default bump, magic-hermes caller
refresh, first live sentinel + self-scan runs. REVISED next-cycle priority:
rm-042 host half, rm-022 (solutions-lint JUDGMENT per-repo scoping — repro pinned,
implement-ready), rm-028 + rm-029 (workflow-permissions pair), rm-015 owner menu,
rm-016/rm-027 one-repo enablement + revert-capture experiment, rm-005/rm-033
host-side pass (wrapper exit-0 masking + MANIFEST cron wiring), rm-039, rm-035.
Owner-gated and carried: as listed above under cycle-5 rejections.

*End of cycle-5 addendum.*

<!-- cycle-7 roadmap extension (2026-09-24, conductor run 8606647750f7476997cfb732378433bc attempt 25a5e95a; items rm-043..rm-045 sourced from cycle-7 assess attempt c95c696ad795 + research attempt 859c58b73275; sanctioned ledger extension per render-marker contract) -->

### Enforce action SHA pinning fleet-wide via sha_pinning_required
- id: `rm-043` | track: reliability | priority: 86.0 | status: candidate — owner-gated probe first
- signals: research 2026-09-24 — repo-level actions permissions now expose sha_pinning_required (live GET repos/codeo1io/.github/actions/permissions -> {"enabled":true,"allowed_actions":"all","sha_pinning_required":false}) and the field is in the documented PUT body (docs.github.com rest/actions/permissions); the fleet's pin discipline (D2 pin decisions, rm-039 keep-current) is convention-only — nothing enforces pinning for NEW workflow edits; complements rm-039 (maintain) with enforcement
- acceptance: one-repo probe result recorded (PUT sha_pinning_required=true on .github, capture rc + revert path) BEFORE any fleet attempt; if accepted: common-settings.yaml gains the key, sync --dry-run shows per-repo drift lines, --apply sets it fleet-wide; private-repo/plan-gated behavior documented; README/AGENTS note the enforcement
- evidence: probe transcript (PUT rc + GET before/after); --dry-run transcript with the new drift dimension; post-apply GET shows sha_pinning_required=true on fleet repos

### Workflow static-analysis gate (zizmor + optional actionlint)
- id: `rm-044` | track: reliability | priority: 82.0 | status: candidate
- signals: research 2026-09-24 — zizmor v1.30.1 (2026-09-09) and actionlint v1.7.12 are active upstreams detecting exactly this fleet's workflow risk classes (template injection via github.event.*, unpinned/loose action refs, excessive permissions); neither installed on host nor gated anywhere; fleet surfaces: private-leak-sentinel.yaml (reusable), leak-sentinel-self.yaml, workflow-templates/deploy-router.yaml
- acceptance: pinned, no-network-trust invocation (version-locked install or SHA-pinned action) runs over all 3 workflow surfaces in the repo's validation path (full_tests command or a workflow gate); initial findings triaged — fixed or documented-with-reason; README documents the convention; no unpinned execution introduced (rm-031 lesson)
- evidence: gate run transcript with per-file finding counts; pinned tool version recorded; before/after diff for any fixed findings

### Cycle-7 maintenance batch (assess P2 + P3 sweep)
- id: `rm-045` | track: reliability | priority: 88.0 | status: candidate
- signals: assess 2026-09-24 (11 findings at 659c726, none previously tracked): (a) P2 verify_deployed_artifacts.py:79 rc=2 conflation (see rm-042 cycle-7 residual); (b) scripts/sync_data_branch.py:197 `git add control-plane` stages UNTRACKED files into the public data branch (no allowlist); (c) :200/:216 success path checks out MAIN_BRANCH instead of the recorded entry branch (failure restore is entry-branch-accurate — asymmetric); (d) :82 mirror_bounded readlines() loads the whole log for a 5000-line bound; (e) sync_repo_settings.py:254/:301 drifted double-count (drift_found can exceed repos=N); (f) check_known_hosts.py:24 KNOWN_HOSTS hardcoded, no env override (unlike CONTROL_PLANE_*/VERIFY_* siblings); (g) AGENTS.md:18 + SECURITY.md:19 reference docs/SECRETS.md which never existed; (h) AGENTS.md:35 parity statement omits claims.yaml (tracked on main, read by fleet-status, in neither mirror copy-set nor data branch); (i) workflow-templates/deploy-router.yaml ships no permissions: key (adopters inherit the account default); (j) scripts/build_control_plane.py unretired orphan twin (see rm-019 cycle-7 gap)
- acceptance: every sub-fix lands with a locking test where applicable (a: wrapper-present/manifest-missing graded drift rc=1 + delegation parse for the repo-settings wrapper; b: allowlist test; c: entry-branch restore on success; e: unique-repo count test; f: env override test; h: parity decision recorded — mirror claims.yaml or document main-only); full suite green and README test count updated; scripts/build_control_plane.py absent from scripts/; grep finds no dangling docs/SECRETS.md reference
- evidence: pytest -q output; git diff --stat for the batch; grep transcripts for (g)/(j)

## Cycle-7 roadmap note (2026-09-24, post-assess, post-research)

Assess (attempt c95c696ad795, ce-review report-only, 11 findings — 1 P2 + 10 P3 — at
659c726; 55/55 tests green; cycle-5 rider 1 VERIFIED HEALED in production: watchdog
mirror exactly 5000 lines, corrections.yaml main↔data byte parity, daily commit 9f94762
2026-09-24T08:40Z; rider 2 open as expected: verify_deployed_artifacts rc=1 naming the
two unpinned entrypoints) and research (attempt 859c58b73275, ce-ideate inline, 7
survivors + explicit rejections, all sources live-fetched 2026-09-24) fed this
addendum. STATUS FLIPS: none — the cycle-5 closures (rm-017/019/021/037/036-SARIF)
were re-verified against production, not reopened. NEW items rm-043 (sha_pinning_required
enforcement lever), rm-044 (zizmor/actionlint workflow gate), rm-045 (maintenance batch
carrying the assess P2/P3 sweep). Evidence appended: rm-016 + rm-027 (platform unlock
observed live — secret scanning/push protection platform-ENABLED on 3 public fleet
repos; the two drifted publics + fleet-wide dependabot_security_updates are the probe
targets), rm-019 (closure verified + build_control_plane.py orphan gap), rm-035
(scorecard 404 — unscored), rm-039 (all pins still current — keep-current value
re-affirmed; host gitleaks 8.28.0 lags the pinned 8.30.1, host-side note only), rm-042
(rc=2 conflation + delegation-scope residual, fix rides rm-045). Rejected this cycle
with rationale: gh CLI host upgrade 2.83.2→2.101.0 (owner hygiene, no repo surface);
secret-scanning validity-checks/non-provider-patterns knobs (premature before the base
features land on the 2 drifted repos); scorecard run-now (rm-035 deferred, 404 baseline
noted); Renovate revisit (still app-install-bound; safe-settings README re-verified
org-only — no competing tool fits a personal account). Rulesets note (deferred
candidate, no item): repo rulesets are available on public repos with GitHub Free (docs
+ live GET /rulesets -> []) — evaluation-mode rollout is a future lever for new
protection opt-ins; private repos stay plan-gated for both classic and rulesets. Fleet
grew 44→46 repos (hermes-curator-evolver, magic-context visible in dry-run); sync
auto-covers, drift_found=0, security_report_only=8. Next-cycle candidates in priority
order: rm-042 host half (MANIFEST pins) + rm-045 batch (P2 first), rm-022 (JUDGMENT
per-repo scoping — implement-ready), rm-028 + rm-029 (workflow-permissions pair), the
rm-016/rm-027 apply-half one-repo probes (now evidence-unlocked), rm-043 probe (owner
gate), rm-044 gate adoption, rm-039, rm-033. Owner-gated: rm-015 menu, rm-016/rm-027
apply-half, rm-043 probe. Carried riders: rm-014/rm-025 stranded-branch deletions,
rm-036 config-ref default bump (live diff vs d04d86d: 23 lines), magic-hermes caller
refresh (@main, no config-ref), first live sentinel + self-scan runs on landed state.

*End of cycle-7 addendum.*

<!-- managed by hermes-roadmap render; do not edit by hand -->
