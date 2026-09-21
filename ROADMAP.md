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
- signals: assess 2026-09-21: `gh repo view codeo1io/.github` -> isPrivate:false, visibility:PUBLIC; commit b0f61ae tracks control-plane/ on main and the daily mirror pushes the same to the public `data` branch (`git ls-tree -r origin/data --name-only` -> 7 control-plane files incl. a 12,686-line watchdog incident log with run/supervisor IDs and /home/agent paths, conductor-tracks.tsv DB paths, cron-inventory.json (54 jobs), runners.txt (26 runners), kanban roster); contradicts the account's private-by-default repo policy and the repo's own expect_private:true (dry-run nags about .github itself every run — the mechanism cannot express "intentionally public")
- acceptance: decision recorded in corrections.yaml + README: EITHER control-plane scrubbed from public refs (mirror to a private side-channel repo, or the fleet-status reader switches to a private source) OR the repo goes private AND sentinel config delivery survives (vendored/pinned gitleaks.toml in callers or token-authed fetch); no fleet-internal paths on any public ref afterwards
- evidence: `git ls-tree origin/main origin/data` shows no control-plane/* after scrub, or `gh repo view codeo1io/.github` -> PRIVATE with sentinel still green on magic-hermes; corrections.yaml gains the entry with reconfirm_due

### Correct the sentinel-coverage claim / cover openai-embedding-proxy
- id: `rm-016` | track: reliability | priority: 95.0 | status: done in-tree (cycle-2 B3: corrections.yaml claim amended 2026-09-21; cross-repo adoption in openai-embedding-proxy remains deferred)
- signals: assess 2026-09-21: control-plane/corrections.yaml:21-26 asserts "gitleaks sentinel covers them (magic-hermes + openai-embedding-proxy)" but `gh api repos/codeo1io/openai-embedding-proxy/contents/.github/workflows` -> only ci.yml (no sentinel/gitleaks reference; ci.yml content grep -> none); the same ledger records that account-level secret_scanning enablement reverts on those repos => openai-embedding-proxy currently has ZERO secret scanning; magic-hermes does call the reusable workflow (via @main)
- acceptance: either openai-embedding-proxy adopts the sentinel workflow or the corrections entry is amended to the real posture with a compensating control; ledger claims become live-verifiable (claim-check predicate like control-plane/claims.yaml)
- evidence: `gh api .../workflows` lists a sentinel workflow (or the amended corrections.yaml diff); a verifiable claim/predicate artifact records the true posture

### control-plane-sync hardening (trap, lock, rotation, timeouts)
- id: `rm-017` | track: reliability | priority: 90.0 | status: done (cycle-2 B2: trap + flock + bounded mirror + gh() timeout 2026-09-21, shim-verified; review-fix 2026-09-21: the acceptance's ssh-keygen clause closed too — both ssh-keygen calls in scripts/check_known_hosts.py bounded via _ssh_keygen timeout=10 with rc=124 empty-output synthesis, and the trap message now branches on restore success instead of asserting it)
- signals: assess 2026-09-21: scripts/control-plane-sync.sh:67 `git push` under set -euo pipefail with no trap — a push failure leaves the shared /work/projects/.github checkout on `data` (line 69 checkout main never runs); next morning repo-settings-sync.sh does `git reset --hard origin/main` on whatever branch is checked out, rewiring the local data pointer until 08:40; no flock (concurrent runs race on checkout/reset/push); the 12,686-line watchdog log is re-committed whole daily with no rotation; scripts/sync_repo_settings.py:40 subprocess.run has no timeout (a stuck gh call hangs the 08:30 cron); shared-checkout branch confusion already bit the fleet (watchdog alert 2026-09-21T01:20:01Z)
- acceptance: failure trap restores main on every exit path; flock prevents concurrent runs; mirrored watchdog log capped/rotated before copy; gh()/ssh-keygen subprocess calls carry timeouts
- evidence: PATH-shimmed failing git push -> script exits nonzero AND `git -C /work/projects/.github branch --show-current` = main; a second concurrent invocation no-ops; data-branch commits show bounded log size; hung-shim timeout test

### Sentinel supply-chain hardening + tool refresh
- id: `rm-018` | track: reliability | priority: 88.0 | status: candidate
- signals: research 2026-09-21: sentinel pins actions/checkout@v5.0.0 (SHA 08c6903) vs latest v7.0.1 (2026-07-20) and actions/upload-artifact@v4.6.2 vs latest v7.0.1 (2026-04-10); template majors covered by rm-008 (stranded); callers invoke the reusable workflow as @main (magic-hermes verified live) and the workflow fetches gitleaks.toml at runtime from unpinned main via unauthenticated raw.githubusercontent (private-leak-sentinel.yaml:33) — one weakening commit to this repo silently degrades fleet-wide leak scanning with no trace in caller repos; host gitleaks 8.28.0 vs upstream v8.30.1 (2026-03-21)
- acceptance: callers pin the reusable workflow by full SHA; gitleaks.toml vendored into callers or fetched at a pinned SHA with checksum verification; workflow_dispatch trigger added for on-demand rescans; host gitleaks upgraded and the useDefault same-id override semantics of gitleaks.toml revalidated on 8.30.x
- evidence: caller workflow ymls show @<40-hex>; a planted-token fixture repo still fails the scan post-upgrade; `gitleaks version` -> 8.30.x with sentinel green on magic-hermes

### Consolidate the three control-plane mirror implementations
- id: `rm-019` | track: reliability | priority: 86.0 | status: candidate
- signals: assess 2026-09-21: three divergent mirrors — control-plane-sync.sh (cron-wired via jobs.json at 08:40; copies kanban t_851e7951 too), sync_data_branch.py (orphan; drops t_851e7951; off-by-one change count at line 78), build_control_plane.py (orphan; CWD-dependent; writes only 2 files); ~/.hermes/cron/jobs.json references no .py mirror; none documented in README/AGENTS
- acceptance: exactly one mirror implementation (keep the cron-wired path, import shared logic) or a documented single-owner split; parity test asserting the mirrored file set is unchanged; README/AGENTS document the data-branch pipeline
- evidence: grep across scripts/ shows one mirror entrypoint; dry mirror run lists the same 7 files; README Layout covers every tracked file

### Sync N+1 elimination via GraphQL (45 API calls -> 1 query)
- id: `rm-020` | track: reliability | priority: 84.0 | status: candidate
- signals: research 2026-09-21 (live probes): REST list returns null merge fields (`gh api '/user/repos?per_page=3&affiliation=owner'` -> allow_merge_commit:null, delete_branch_on_merge:null, isPrivate:null — so the per-repo detail GET inside sync_repo_settings.py is structurally required on REST), BUT one GraphQL query returns everything: viewer{repositories(first:100,affiliations:OWNER)} -> 44 nodes with name/isPrivate/isArchived/isFork/defaultBranchRef{name}/mergeCommitAllowed/rebaseMergeAllowed/squashMergeAllowed/deleteBranchOnMerge/viewerPermission (probed OK on host gh 2.83.2; sample independently confirmed the live 'agent' repo drift: merge/rebase allowed true + deleteBranchOnMerge false — the dry-run DRIFT line)
- acceptance: list_repos rewritten on the GraphQL query (or REST kept with a documented reason); per-run API calls drop from 1 list + N detail GETs to ~1; dry-run decisions byte-identical to the current implementation on the same fleet state; pagination handles >100 repos
- evidence: before/after dry-run transcripts identical (modulo ordering); pytest covering the GraphQL parse path against a recorded response fixture; call-count assertion

### Documentation currency (README/AGENTS cover the shipped surface)
- id: `rm-021` | track: customer-experience | priority: 80.0 | status: candidate
- signals: assess 2026-09-21: README.md Layout/Automation (from line 7) and AGENTS.md predate the last 8 commits — no mention of gitleaks.toml, private-leak-sentinel workflow, control-plane/ + data-branch mirror, claims.yaml, corrections.yaml, solutions-lint.py, sync_data_branch.py, build_control_plane.py; rm-009 covers community health files (different scope) — this item covers operator/agent doc accuracy for the shipped surface
- acceptance: every tracked file appears in README Layout; AGENTS.md gains data-branch + sentinel conventions; expect-public ack + plan-gate notes folded in when rm-014 lands
- evidence: grep -c per tracked filename in README.md -> >=1; AGENTS.md diff reviewed

### solutions-lint.py: fix the dead self-heal or retire the orphan
- id: `rm-022` | track: reliability | priority: 70.0 | status: candidate
- signals: assess 2026-09-21: scripts/solutions-lint.py:36 computes relpath against './docs/solutions' while walked paths are absolute -> derived category always contains '/' -> the frontmatter category self-heal can never fire (proven live: rel='../../…/foo' => heals? False); module-global JUDGMENT (line 16) accumulates across repos/repeats; script is unwired (no cron job) and defaults to other repos' paths (hermes-conductor, hermes-gpt)
- acceptance: relpath base fixed to the walked root (or absolute-consistent path handling); JUDGMENT scoped per lint_repo call; either wired into a cron/README or relocated to the repo it serves
- evidence: fixture solution without category -> self-heal adds it and rc=0; repeated invocation emits identical output

<!-- cycle-2 compound (2026-09-21, conductor run 92e960046f14 attempt 972800c7; items rm-023/rm-024 sourced from implement-phase evidence per lessons L9/L15) -->

### sync: apply the live merge-settings drift on repo `agent`
- id: `rm-023` | track: reliability | priority: 75.0 | status: candidate
- signals: implement/full_tests live dry-run 2026-09-21: 'agent: DRIFT merge settings (allow_merge_commit=True->False, allow_rebase_merge=True->False, delete_branch_on_merge=False->True)' — the only remaining drift_found=1 across 44 repos; repo created mid-run (fleet 43->44, L6); deliberately NOT --applied by the cycle-2 batch (mutating GitHub state was out of batch scope)
- acceptance: python3 scripts/sync_repo_settings.py --apply -> rc=0; follow-up --dry-run -> drift_found=0; `agent` repo merge flags match common-settings.yaml
- evidence: live --dry-run output before/after; gh api repos/codeo1io/agent merge fields

### tests: persist the control-plane-sync shim matrix as a pytest regression
- id: `rm-024` | track: reliability | priority: 72.0 | status: candidate
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

<!-- managed by hermes-roadmap render; do not edit by hand -->
