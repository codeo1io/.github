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
- New fleet repos: confirm the sync picks them up (`--dry-run` shows them) and
  add to `protection-opt-in.txt` only if they meet the README requirements.
