# .github — Roadmap

> Autonomously maintained by the roadmap sync (reliability-first). Items cite reproducible codebase signals; acceptance is proven by cited evidence.

**Vision**: A reliable, customer-friendly repository advanced by evidence-cited roadmap cycles owned by the autonomy loop

**Pillars**: reliability work outranks customer-experience work; every roadmap item cites reproducible codebase signals; acceptance is proven by cited evidence, never claimed

## Fleet context

- dependents (changes here affect): dashboard, fleet-status, hermes-agent
- graph: evidence-derived (imports/refs/deploy surfaces); advisory

## Open items

### Fix the empty cron-inventory mirror (dict-shaped jobs.json) + fixture + canary
- id: `rm-046` | track: reliability | priority: 96.0 | status: in_progress
- acceptance: (1) dict-tolerant parse (payload.get("jobs", payload if isinstance(payload, list) else [])); (2) tests gain a realistic jobs.json fixture (BOTH shapes, ≥2 jobs each) asserting the mirrored inventory contains exactly the fixture job ids — the empty mirror becomes a failing test; (3) class-guard canary: generated inventory headers carry record counts and the sync exits nonzero when a generated inventory comes out empty or schema-mismatched (loud, not silent); (4) the first post-landing daily run's origin/data copy is non-empty with the true job count
- evidence: campaign-recorded in .github ROADMAP.md

### Add test coverage for 5 untested module(s)
- id: `rm-036` | track: reliability | priority: 95.0 | status: in_progress
- signals: reliability.no_tests:scripts/check_known_hosts.py, reliability.no_tests:scripts/solutions-lint.py, reliability.no_tests:scripts/sync_data_branch.py, reliability.no_tests:scripts/sync_repo_settings.py, reliability.no_tests:scripts/verify_deployed_artifacts.py
- acceptance: Every module in ['scripts/check_known_hosts.py', 'scripts/solutions-lint.py', 'scripts/sync_data_branch.py', 'scripts/sync_repo_settings.py', 'scripts/verify_deployed_artifacts.py'] has a corresponding test file with at least one passing test
- evidence: full suite green (python -m pytest -q) at HEAD; conductor validation digest validation:v1:<sha> recorded in the shipping PR

### Deployed-artifact verification: pin the cron-wired scripts in MANIFEST.sha256
- id: `rm-042` | track: reliability | priority: 91.0 | status: in_progress
- acceptance: MANIFEST.sha256 covers both sync entrypoints (deployed wrapper AND repo-side script digests); a drift check compares deployed vs manifest digests on the daily schedule (wrapper pre-step or a repo test invoking the comparison) and reports nonzero on divergence; a deliberately planted divergence fails the check; works for wrapper-style deployments (digest of the wrapper + digest of its declared delegate)
- evidence: campaign-recorded in .github ROADMAP.md

### Refactor 8 high-complexity function(s)
- id: `rm-001` | track: reliability | priority: 90.0 | status: candidate
- signals: reliability.complexity_hot:scripts/check_known_hosts.py::main, reliability.complexity_hot:scripts/solutions-lint.py::lint_file, reliability.complexity_hot:scripts/solutions-lint.py::lint_repo, reliability.complexity_hot:scripts/sync_data_branch.py::main, reliability.complexity_hot:scripts/sync_repo_settings.py::list_repos (+3 more)
- acceptance: Each flagged function is decomposed below the branch threshold with behavior locked by characterization tests
- evidence: ast-based branch-count check passes at HEAD (full suite green; conductor validation digest validation:v1:<sha> recorded in the shipping PR)

### Sentinel detection integrity: retire blanket tree allowlists, restore unquoted-value coverage
- id: `rm-037` | track: reliability | priority: 90.0 | status: in_progress
- acceptance: blanket tree exemptions replaced by targeted per-file triage (pattern proven at gitleaks.toml:62-71) and/or .gitleaksignore fingerprints; a generic-rule variant covers unquoted assignment values; fleet-triage runs on magic-hermes + hermes-agent report 0 actionable findings after narrowing
- evidence: campaign-recorded in .github ROADMAP.md

### Cycle-7 maintenance batch (assess P2 + P3 sweep)
- id: `rm-045` | track: reliability | priority: 88.0 | status: in_progress
- acceptance: every sub-fix lands with a locking test where applicable (a: wrapper-present/manifest-missing graded drift rc=1 + delegation parse for the repo-settings wrapper; b: allowlist test; c: entry-branch restore on success; e: unique-repo count test; f: env override test; h: parity decision recorded — mirror claims.yaml or document main-only); full suite green and README test count updated; scripts/build_control_plane.py absent from scripts/; grep finds no dangling docs/SECRETS.md reference
- evidence: campaign-recorded in .github ROADMAP.md

### Daily enforcement of the deployed-artifact contract
- id: `rm-048` | track: reliability | priority: 88.0 | status: candidate
- acceptance: a report-only daily verify step (jobs.json entry or a wrapper pre-step) runs scripts/verify_deployed_artifacts.py against canonical and journals rc + drift names (log line survives); the immediate rm-042 rider executes as part of this item (re-pin the three delegates from canonical, re-prove rc=0); a shim/monitor test locks the journaling path; AGENTS.md documents the daily expectation
- evidence: campaign-recorded in .github ROADMAP.md

### Enforce action SHA pinning fleet-wide via sha_pinning_required
- id: `rm-043` | track: reliability | priority: 86.0 | status: in_progress
- acceptance: one-repo probe result recorded (PUT sha_pinning_required=true on .github, capture rc + revert path) BEFORE any fleet attempt; if accepted: common-settings.yaml gains the key, sync --dry-run shows per-repo drift lines, --apply sets it fleet-wide; private-repo/plan-gated behavior documented; README/AGENTS note the enforcement
- evidence: campaign-recorded in .github ROADMAP.md

### Sentinel self-scan + fleet adoption: close the owner-repo blind spot
- id: `rm-038` | track: reliability | priority: 84.0 | status: candidate
- acceptance: a sentinel caller workflow (push/PR) lands in codeo1io/.github and runs green; openai-embedding-proxy gains the caller (post rm-036); SECURITY.md wording matches actual coverage; corrections.yaml inventory reflects the added caller
- evidence: campaign-recorded in .github ROADMAP.md

### Enable private vulnerability reporting on the public repos
- id: `rm-049` | track: reliability | priority: 84.0 | status: in_progress
- acceptance: probe-first (PUT on .github, capture rc + revert path) before any fleet attempt; then enabled:true on all 3 public repos; SECURITY.md notes the channel is live; convention recorded for future public repos (enable at creation)
- evidence: campaign-recorded in .github ROADMAP.md

### Workflow static-analysis gate (zizmor + optional actionlint)
- id: `rm-044` | track: reliability | priority: 82.0 | status: candidate
- acceptance: pinned, no-network-trust invocation (version-locked install or SHA-pinned action) runs over all 3 workflow surfaces in the repo's validation path (full_tests command or a workflow gate); initial findings triaged — fixed or documented-with-reason; README documents the convention; no unpinned execution introduced (rm-031 lesson)
- evidence: campaign-recorded in .github ROADMAP.md

### Native Dependabot version updates for github-actions pins
- id: `rm-039` | track: reliability | priority: 78.0 | status: candidate
- acceptance: canonical dependabot.yml (github-actions ecosystem, weekly, scoped) shipped as a template and adopted in codeo1io/.github; README documents the convention; a Dependabot PR observed on a drifted pin or a no-drift API check
- evidence: campaign-recorded in .github ROADMAP.md

### Anchor the gitleaks dist/ allowlist to a path boundary
- id: `rm-047` | track: reliability | priority: 78.0 | status: in_progress
- acceptance: allowlist entry anchored to a component boundary (`'''(^|/)dist/'''` or equivalent); live-binary A/B re-run shows the planted token detected under mydist/ AND, if a true vendored dist/ exemption is intended, that it still matches (decision recorded either way); tests/test_gitleaks_config.py extended to lock the anchored pattern against the live binary
- evidence: campaign-recorded in .github ROADMAP.md

### Security-posture convergence: report-only drift lanes need an actor
- id: `rm-050` | track: reliability | priority: 74.0 | status: in_progress
- acceptance: a recorded decision (README + corrections.yaml); if apply-path: one-repo enablement + revert-capture experiment first, then expect-list-driven fleet apply; if manual-by-decision: drift rows re-graded INFO (not DRIFT) and corrections.yaml names the posture owner; either way the daily output stops asserting a want nobody acts on
- evidence: campaign-recorded in .github ROADMAP.md

### Control-plane toolchain-freshness record (versions.json)
- id: `rm-040` | track: reliability | priority: 70.0 | status: candidate
- acceptance: the mirror path emits versions.json (gh version, gitleaks latest vs deployed, template action pins vs upstream latest, size-bounded) to the data branch; shim test locks the emitter; a cron run lands the file
- evidence: campaign-recorded in .github ROADMAP.md

### Sync/docs micro-corrections
- id: `rm-041` | track: reliability | priority: 55.0 | status: in_progress
- acceptance: drift message derives from the actual desired value; README test count matches live pytest output
- evidence: campaign-recorded in .github ROADMAP.md

### Code scanning default setup on the public code repos
- id: `rm-051` | track: reliability | priority: 55.0 | status: in_progress
- acceptance: enable default setup on the two public code repos (.github optional); first analysis observed and false-positive triage decision recorded; disable path documented
- evidence: campaign-recorded in .github ROADMAP.md

## Closed items

- `rm-016` Correct the sentinel-coverage claim / cover openai-embedding-proxy — done
- `rm-017` control-plane-sync hardening (trap, lock, rotation, timeouts) — done
- `rm-018` Sentinel supply-chain hardening + tool refresh — superseded
- `rm-019` Consolidate the three control-plane mirror implementations — superseded
- `rm-020` Sync N+1 elimination via GraphQL (45 API calls -> 1 query) — superseded
- `rm-021` Documentation currency (README/AGENTS cover the shipped surface) — superseded
- `rm-022` solutions-lint.py: fix the dead self-heal or retire the orphan — superseded
- `rm-023` sync: apply the live merge-settings drift on repo `agent` — superseded
- `rm-024` tests: persist the control-plane-sync shim matrix as a pytest regression — done
- `rm-025` Land the cycle-2 batch on current main (resolve the ROADMAP.md conflict via this file) — done
- `rm-026` Public-repo runner exposure: stop fork-PR jobs on the fleet self-hosted runner — superseded
- `rm-027` Per-repo security_and_analysis enablement (close rm-016's residual exposure) — done
- `rm-028` Actions least-privilege drift-check + platform SHA-pinning enforcement — superseded
- `rm-029` Rulesets v2 for public opt-in repos — superseded
- `rm-030` Community health files from the personal-account .github repo — done
- `rm-031` Sentinel supply chain: pin config ref, refresh scanner, narrow the .md blanket allowlist — superseded
- `rm-032` sync_repo_settings.py robustness: gh timeouts, pagination, dead code, lint portability — done
- `rm-033` Cron wrapper hardening: branch safety, ordered host-key check, failure propagation — superseded
- `rm-034` Renovate shared default preset — superseded
- `rm-035` OSSF Scorecard on the public repos — superseded

<!-- managed by hermes-roadmap render; do not edit by hand -->
