#!/usr/bin/env python3
"""Sync fleet control-plane state to the codeo1io/.github `data` branch.

Same logic as control-plane-sync.sh but expressed in Python (git via
subprocess with simple arg lists) so it runs cleanly under any executor.
Idempotent: exits quietly when nothing changed.
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

REPO = os.environ.get('CONTROL_PLANE_REPO', '/work/projects/.github')
BRANCH = 'data'


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(['git', '-C', REPO, *args], capture_output=True, text=True, check=check)


def main() -> int:
    os.chdir(REPO)
    git('fetch', 'origin', BRANCH)
    cur = git('rev-parse', '--abbrev-ref', 'HEAD').stdout.strip()
    if cur != BRANCH:
        git('checkout', BRANCH)
    git('reset', '--hard', f'origin/{BRANCH}')

    os.makedirs('control-plane', exist_ok=True)
    home = os.path.expanduser('~')

    copies = {
        f'{home}/.hermes/conductor-tracks.tsv': 'control-plane/conductor-tracks.tsv',
        f'{home}/.hermes/conductor-watchdog-alerts.log': 'control-plane/conductor-watchdog-alerts.log',
        f'{home}/.hermes/kanban/attachments/t_acd6a2e8/OWNERS.md': 'control-plane/kanban-t_acd6a2e8-OWNERS.md',
    }
    for src, dst in copies.items():
        if os.path.isfile(src):
            shutil.copyfile(src, dst)

    jobs_path = f'{home}/.hermes/cron/jobs.json'
    rows = []
    if os.path.isfile(jobs_path):
        with open(jobs_path) as fh:
            jobs = json.load(fh)
        for j in (jobs if isinstance(jobs, list) else jobs.get('jobs', [])):
            rows.append({
                'name': j.get('name'),
                'schedule': j.get('schedule'),
                'enabled': j.get('enabled', True),
                'deliver': j.get('deliver'),
            })
    with open('control-plane/cron-inventory.json', 'w') as fh:
        json.dump(rows, fh, indent=2, sort_keys=True)

    ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    runners_dir = f'{home}/runners'
    lines = [f'# generated {ts}']
    if os.path.isdir(runners_dir):
        for d in sorted(os.listdir(runners_dir)):
            if os.path.isfile(os.path.join(runners_dir, d, '.runner')):
                lines.append(d)
    with open('control-plane/runners.txt', 'w') as fh:
        fh.write('\n'.join(lines) + '\n')

    diff = git('status', '--porcelain', 'control-plane/', check=False).stdout.strip()
    if not diff:
        git('checkout', 'main')
        return 0  # quiet: nothing to report (watchdog pattern)

    git('add', 'control-plane/')
    git('-c', 'user.name=fleet-bot', '-c', 'user.email=fleet-bot@users.noreply.github.com',
        'commit', '-m', f'chore(control-plane): mirror fleet state {ts}')
    git('push', 'origin', BRANCH)
    git('checkout', 'main')
    print(f'control-plane mirrored: {diff.count(chr(10)) + 1} changed files')
    return 0


if __name__ == '__main__':
    sys.exit(main())
