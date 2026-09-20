# codeo1io/.github — fleet defaults (settings-as-code)

Source of truth for repository settings across the codeo1io account, in the
spirit of marcusrbrown/.github: one `common-settings.yaml`, synced to every
repo daily, instead of per-repo manual clicking.

## Layout

- `common-settings.yaml` — fleet merge settings (squash-only, delete branch on
  merge, auto-merge), opt-in branch protection template, report-only visibility
  expectation. `allow_auto_merge` is plan-gated: GitHub only persists it where
  branch protection exists (public repos on the free plan), so the sync does
  not drift-check it — squash-only, no-rebase, no-merge-commit, and
  delete-branch are the enforced invariants.
- `protection-opt-in.txt` — repos that receive branch protection (one per line).
  Requirements: default branch `main`, solo-merge workflow, no direct-push
  promote flow. `hermes-conductor` is permanently excluded (its promote flow
  ff-pushes main by SHA).
- `exclude-repos.txt` — repos skipped entirely (archived / special case).
- `scripts/sync_repo_settings.py` — the sync. `--dry-run` (default) reports
  drift; `--apply` fixes it via `gh api` PATCH/PUT. Visibility is never
  auto-flipped, only reported.
- `scripts/check_known_hosts.py` — verifies `~/.ssh/known_hosts` github.com
  keys against GitHub's published fingerprints (`api.github.com/meta`); exit 1
  on missing/mismatch (MITM / rotation drift).
- `workflow-templates/deploy-router.yaml` — copy-paste template for
  path-filtered deploys (dorny/paths-filter) where each app deploys through its
  own GitHub Environment with approval gates and scoped secrets. Pin actions to
  commit SHAs before adopting.

## Automation

Cron job `repo-settings-sync` (daily 08:30 UTC, native hermes cron) runs
`~/.hermes/scripts/repo-settings-sync.sh`, which self-updates this repo to
`origin/main`, runs the known-hosts drift check, then applies the sync. Output
is logged to `~/.hermes/repo-settings-sync.log`.

## Manual use

    python3 scripts/sync_repo_settings.py --dry-run
    python3 scripts/sync_repo_settings.py --apply
    python3 scripts/check_known_hosts.py

## Inert until Renovate is installed

Any `renovate.json5` in fleet repos extending `github>codeo1io/renovate-config`
stays inert until the Renovate GitHub App is installed on the codeo1io account
(no Renovate PRs exist in any repo as of 2026-09-20). Install the app with
access to private repos, then the presets activate on the next run.
