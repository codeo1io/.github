# codeo1io/.github — fleet defaults (settings-as-code)

Source of truth for repository settings across the codeo1io account, in the
spirit of marcusrbrown/.github: one `common-settings.yaml`, synced to every
repo daily, instead of per-repo manual clicking.

## Layout

- `common-settings.yaml` — fleet merge settings (squash-only, delete branch on
  merge), opt-in branch protection template, report-only visibility
  expectation. `allow_auto_merge` was removed 2026-09-21: it is plan-gated
  (GitHub only persists it where branch protection exists) so the sync could
  never drift-check it — squash-only, no-rebase, no-merge-commit, and
  delete-branch are the enforced invariants.
- `protection-opt-in.txt` — repos that receive branch protection (one per line).
  Requirements: default branch `main`, solo-merge workflow, no direct-push
  promote flow. `hermes-conductor` is permanently excluded (its promote flow
  ff-pushes main by SHA). Names match case-insensitively; entries matching no
  repo produce a WARN on every run.
- `exclude-repos.txt` — repos skipped entirely (archived / special case).
- `expect-public.txt` — originals acknowledged as intentionally public (one
  per line); silences the report-only VISIBILITY DRIFT line for them. Public
  forks are conformant without listing; anything else public is flagged for
  manual review. The sync never flips visibility.
- `scripts/sync_repo_settings.py` — the sync. `--dry-run` (default) reports
  drift; `--apply` fixes it via `gh api` PATCH/PUT. Visibility is never
  auto-flipped, only reported. Repo listing is paginated end-to-end (GraphQL,
  no `--limit` cap) so a fleet growing past any cap silently drops no repo.
  `security_and_analysis` posture (secret scanning, push protection,
  Dependabot) is reported as report-only drift on public repos and is never
  patched by the sync.
- `scripts/solutions-lint.py` — self-healing frontmatter/index lint for
  `docs/solutions/` trees in the fleet repos (paths resolve against the repo
  being linted, never the caller's CWD; override targets via
  `SOLUTIONS_LINT_REPOS`).
- `scripts/check_known_hosts.py` — verifies EVERY pinned `github.com` and
  `[ssh.github.com]:443` key in `~/.ssh/known_hosts` against GitHub's published
  fingerprints (live `api.github.com/meta`), comparing the FULL pinned set per
  algorithm: extra or stale pins FAIL (ssh would still accept them), not just
  missing ones. Algorithms are derived from meta, so when GitHub ships a new SSH
  algorithm the checker fails closed fleet-wide until pinned. Remediation runbook:
  `ssh-keyscan -t <newalgo> github.com` and `ssh-keyscan -p 443 -t <newalgo>
  ssh.github.com`, verify each key's fingerprint is published by
  `api.github.com/meta` (`ssh-keygen -lf -`), then append the verified entries to
  `~/.ssh/known_hosts`.
- `workflow-templates/deploy-router.yaml` — copy-paste template for
  path-filtered deploys (dorny/paths-filter) where each app deploys through its
  own GitHub Environment with approval gates and scoped secrets. Actions come
  pre-pinned to verified commit SHAs (actions/checkout, dorny/paths-filter) —
  keep them pinned when adopting.
- `docs/lessons.md` — evidence-derived prevention rules from the maintenance
  cycles; extend per cycle instead of re-learning.
- `SECURITY.md`, `PULL_REQUEST_TEMPLATE.md`, `ISSUE_TEMPLATE/` — community
  health files: reporting policy, PR checklist encoding the fleet
  conventions, and structured bug/feature templates.

## Automation

Cron job `repo-settings-sync` (daily 08:30 UTC, native hermes cron) runs
`~/.hermes/scripts/repo-settings-sync.sh`, which self-updates this repo to
`origin/main`, runs the known-hosts drift check, then applies the sync. Output
is logged to `~/.hermes/repo-settings-sync.log`.

## Manual use

    python3 scripts/sync_repo_settings.py --dry-run
    python3 scripts/sync_repo_settings.py --apply
    python3 scripts/check_known_hosts.py
    python3 -m pytest tests/        # 42 tests: hermetic unit + control-plane shims + gitleaks-config (2 of the latter are live-binary integrations, skipif-guarded)

## Inert until Renovate is installed

Any `renovate.json5` in fleet repos extending `github>codeo1io/renovate-config`
stays inert until the Renovate GitHub App is installed on the codeo1io account
(no Renovate PRs exist in any repo as of 2026-09-20). Install the app with
access to private repos, then the presets activate on the next run.
