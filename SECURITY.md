# Security Policy

## Supported surfaces

This repository (`.github`) is the settings-as-code source of truth for the
codeo1io account: `common-settings.yaml`, the daily sync scripts, workflow
templates, and community health files. It is intentionally **public** (reusable
workflows must be reachable from other repositories).

## Reporting a vulnerability

Open a private security advisory on this repository (Security → Report a
vulnerability) or email the account owner directly. Please do not open a
public issue for anything secret- or credential-related.

## What this repo does about secrets

- **Never commit secrets.** All credentials live in the environment of the
  machines that run the sync (see `docs/SECRETS.md` conventions referenced in
  AGENTS.md), never in this repository.
- **Automated scanning.** The [`private-leak-sentinel`](.github/workflows/private-leak-sentinel.yaml)
  reusable workflow runs [gitleaks](https://github.com/gitleaks/gitleaks) via
  SHA-pinned `gitleaks-action` with the fleet [`gitleaks.toml`](gitleaks.toml)
  checked out at a pinned ref. This repository self-scans on pushes to
  `main` and on pull requests (new commits only), and weekly (full history)
  via
  [`leak-sentinel-self`](.github/workflows/leak-sentinel-self.yaml), using
  the exact config each pushed commit ships; `magic-hermes` calls the same
  reusable workflow on its own pushes and PRs. Other fleet repos have no
  sentinel yet — adoption is tracked as roadmap rm-016/rm-038.
- **Report-only posture sync.** `scripts/sync_repo_settings.py` reports
  GitHub-native security posture (secret scanning, push protection,
  Dependabot security updates) drift on public repos but never changes it
  automatically — posture changes are explicit owner decisions.
- **Host-key pinning.** `scripts/check_known_hosts.py` verifies the full pinned
  SSH key set for `github.com` and `[ssh.github.com]:443` against GitHub's
  published fingerprints and fails closed on any deviation.

## Mirrored operational data

The `data` branch mirrors a bounded tail of operational state (cron schedule
inventory, runner names, watchdog alerts) for continuity. Schedules and names
only — no scripts, tokens, or credential material are mirrored, by design.
