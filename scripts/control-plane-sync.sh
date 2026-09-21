#!/usr/bin/env bash
# control-plane-sync — mirror home-dir fleet state into codeo1io/.github data branch.
# fro-bot/.github pattern: autonomous writes land on the unprotected `data` branch;
# main stays human-gated. Cron-invoked (daily), idempotent.
set -euo pipefail

REPO_DIR="${CONTROL_PLANE_REPO:-/work/projects/.github}"
BRANCH="data"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

cd "$REPO_DIR"
git fetch origin "$BRANCH" --quiet
git checkout -q "$BRANCH" 2>/dev/null || git checkout -q -b "$BRANCH" origin/"$BRANCH"
git reset -q --hard origin/"$BRANCH"

mkdir -p control-plane

# 1. Conductor track registry (name, db, repo, toml, roadmap)
if [ -f ~/.hermes/conductor-tracks.tsv ]; then
  cp ~/.hermes/conductor-tracks.tsv control-plane/conductor-tracks.tsv
fi

# 2. Watchdog alerts log (persistent record of relaunches/parked runs)
if [ -f ~/.hermes/conductor-watchdog-alerts.log ]; then
  cp ~/.hermes/conductor-watchdog-alerts.log control-plane/conductor-watchdog-alerts.log
fi

# 3. Kanban OWNERS canon reference (pointer + copy if present)
for f in ~/.hermes/kanban/attachments/t_acd6a2e8/OWNERS.md ~/.hermes/kanban/attachments/t_851e7951/OWNERS.md; do
  if [ -f "$f" ]; then
    dest="control-plane/kanban-$(basename "$(dirname "$f")")-OWNERS.md"
    cp "$f" "$dest"
  fi
done

# 4. Cron inventory (names + schedules only — never scripts, which may carry secrets)
if [ -f ~/.hermes/cron/jobs.json ]; then
  python3 - <<'PY'
import json
with open(__import__('os').path.expanduser('~/.hermes/cron/jobs.json')) as f:
    jobs = json.load(f)
rows = [{'name': j.get('name'), 'schedule': j.get('schedule'),
         'enabled': j.get('enabled', True), 'deliver': j.get('deliver')}
        for j in (jobs if isinstance(jobs, list) else jobs.get('jobs', []))]
with open('control-plane/cron-inventory.json', 'w') as f:
    json.dump(rows, f, indent=2, sort_keys=True)
PY
fi

# 5. Runners inventory (dirs holding a registration file)
{
  echo "# generated $TS"
  for d in ~/runners/*/; do
    [ -f "$d/.runner" ] && basename "$d"
  done
} > control-plane/runners.txt

if git diff --quiet && git diff --staged --quiet; then
  echo "no control-plane changes"
  git checkout -q main
  exit 0
fi

git add control-plane/
git -c user.name="fleet-bot" -c user.email="fleet-bot@users.noreply.github.com" \
  commit -qm "chore(control-plane): mirror fleet state $TS"
git push -q origin "$BRANCH"
echo "pushed control-plane mirror $TS"
git checkout -q main
