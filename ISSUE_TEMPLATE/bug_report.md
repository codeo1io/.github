---
name: Bug report
about: Something in the fleet settings / sync / templates is wrong
title: "[bug] "
labels: bug
assignees: ''
---

**Which surface**

- [ ] `common-settings.yaml` (fleet settings)
- [ ] `scripts/sync_repo_settings.py` (the daily sync)
- [ ] `scripts/check_known_hosts.py` (SSH host-key pinning)
- [ ] `scripts/control-plane-sync.sh` (data-branch mirror)
- [ ] `workflow-templates/deploy-router.yaml`
- [ ] other: ______

**What happened**

A clear description of the wrong behavior. For sync issues, paste the
relevant `--dry-run` output block (redact anything sensitive first).

**What you expected**

The desired behavior.

**How to reproduce**

Commands, in order, with any list-file changes. Example:

    python3 scripts/sync_repo_settings.py --dry-run

**Environment**

- Date/time of the run (the sync runs daily at 08:30 UTC):
- `gh --version`:
