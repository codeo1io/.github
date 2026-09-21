# .github — Roadmap

> Autonomously maintained by the roadmap sync (reliability-first). Items cite reproducible codebase signals; acceptance is proven by cited evidence.

**Vision**: A reliable, customer-friendly repository advanced by evidence-cited roadmap cycles owned by the autonomy loop

**Pillars**: reliability work outranks customer-experience work; every roadmap item cites reproducible codebase signals; acceptance is proven by cited evidence, never claimed

## Fleet context

- dependents (changes here affect): (host), dashboard
- graph: evidence-derived (imports/refs/deploy surfaces); advisory

## Open items

### Add test coverage for 2 untested module(s)
- id: `rm-002` | track: reliability | priority: 86.0 | status: candidate
- signals: reliability.no_tests:scripts/check_known_hosts.py, reliability.no_tests:scripts/sync_repo_settings.py
- acceptance: Every module in ['scripts/check_known_hosts.py', 'scripts/sync_repo_settings.py'] has a corresponding test file with at least one passing test
- evidence: CI: pytest collects the new test files and they pass

### Refactor 3 high-complexity function(s)
- id: `rm-001` | track: reliability | priority: 79.0 | status: candidate
- signals: reliability.complexity_hot:scripts/check_known_hosts.py::main, reliability.complexity_hot:scripts/sync_repo_settings.py::main, reliability.complexity_hot:scripts/sync_repo_settings.py::protection_drift
- acceptance: Each flagged function is decomposed below the branch threshold with behavior locked by characterization tests
- evidence: ast-based branch-count check passes in CI

<!-- managed by hermes-roadmap render; do not edit by hand -->
