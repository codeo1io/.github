# AGENTS.md — codeo1io/.github

Fleet settings-as-code repo for the codeo1io account.

## Conventions

- Edit `common-settings.yaml` (never hand-tune repo settings in the GitHub UI);
  changes take effect on the next daily sync or a manual `--apply` run.
- After changing merge/protection settings here, run
  `python3 scripts/sync_repo_settings.py --dry-run` first, review the drift
  report, then `--apply`.
- Branch protection is opt-in via `protection-opt-in.txt`. `hermes-conductor`
  is NEVER added: its promote flow ff-pushes main by SHA and protection would
  wedge it. `enforce_admins` stays false for the same reason.
- Visibility (`expect_private`) is report-only by design — the sync must never
  flip a repo public/private on its own.
- No secrets in this repo, ever (HASS_TOKEN and friends stay in ~/.hermes/.env;
  see docs/SECRETS.md conventions).
- Workflow templates must keep `runs-on: ubuntu-latest` and carry no local
  environment specifics (self-hosted runners, LAN hosts, /home/agent or
  /work/projects paths, fork remotes).

## Control-plane data mirror

- The daily 08:40 UTC cron runs the deployed wrapper
  (`~/.hermes/scripts/control-plane-sync.sh`), which execs
  `scripts/sync_data_branch.py` FROM THIS CHECKOUT — repo edits to that file
  go live at the next cron run with no host-side deployment. It is the
  single mirror implementation (the old twin `scripts/control-plane-sync.sh`
  was retired in cycle-5; do not resurrect a second copy).
- Hardening properties that must survive any edit: single-flight `flock`,
  entry-branch restore on failure, bounded watchdog tail
  (`CONTROL_PLANE_WATCHDOG_MAX_LINES`, default 5000), stage-before-diff,
  and bounded git timeouts. `tests/test_control_plane_shims.py` locks them.
- Copy-set parity matters: conductor tracks, watchdog tail, BOTH kanban
  OWNERS canon references, cron + runners inventories, and
  `control-plane/corrections.yaml` mirrored from the canonical main-tree
  copy. The data branch must never carry a stale corrections claim.
- `scripts/verify_deployed_artifacts.py` checks the deployed wrapper +
  manifest against this repo (rc 0 clean / 1 drift / 2 not a deployed host);
  today the deployed `MANIFEST.sha256` pins neither cron-wired entrypoint —
  run it after any host-side script deployment and add the missing pins.
- New fleet repos: confirm the sync picks them up (`--dry-run` shows them) and
  add to `protection-opt-in.txt` only if they meet the README requirements.
