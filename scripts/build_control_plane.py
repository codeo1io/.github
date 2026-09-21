#!/usr/bin/env python3
"""Build control-plane/cron-inventory.json + runners.txt on the data branch."""
import json
import os
import subprocess
from datetime import datetime, timezone

rows = []
jobs_path = os.path.expanduser('~/.hermes/cron/jobs.json')
if os.path.exists(jobs_path):
    with open(jobs_path) as f:
        jobs = json.load(f)
    for j in (jobs if isinstance(jobs, list) else jobs.get('jobs', [])):
        rows.append({
            'name': j.get('name'),
            'schedule': j.get('schedule'),
            'enabled': j.get('enabled', True),
            'deliver': j.get('deliver'),
        })

with open('control-plane/cron-inventory.json', 'w') as f:
    json.dump(rows, f, indent=2, sort_keys=True)

ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
runners_dir = os.path.expanduser('~/runners')
lines = [f'# generated {ts}']
if os.path.isdir(runners_dir):
    for d in sorted(os.listdir(runners_dir)):
        if os.path.isfile(os.path.join(runners_dir, d, '.runner')):
            lines.append(d)
with open('control-plane/runners.txt', 'w') as f:
    f.write('\n'.join(lines) + '\n')

print('cron rows:', len(rows), '| runners:', len(lines) - 1)
