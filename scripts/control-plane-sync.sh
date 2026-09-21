#!/usr/bin/env bash
# control-plane-sync — mirror home-dir fleet state into codeo1io/.github data branch.
# fro-bot/.github pattern: autonomous writes land on the unprotected `data` branch;
# main stays human-gated. Cron-invoked (daily), idempotent.
set -euo pipefail

REPO_DIR="${CONTROL_PLANE_REPO:-/work/projects/.github}"
BRANCH="data"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Single-flight: a concurrent run means that run is already syncing; this
# one exits clean instead of racing on checkout/reset/push (rm-017).
LOCK_FILE="${CONTROL_PLANE_LOCK:-/tmp/control-plane-sync.lock}"
exec 9>"$LOCK_FILE"
flock -n 9 || { echo "control-plane-sync: lock held by another run; exiting" >&2; exit 0; }

cd "$REPO_DIR"

# Failure safety: this script checks out `data` inside the SHARED /work/projects/.github
# checkout. If anything under set -e fails before the final checkout, the 08:30
# repo-settings-sync would otherwise `git reset --hard` on the still-checked-out data
# branch. The trap restores the entry branch (main in the cron scenario) on every
# nonzero exit (rm-017).
RESTORE_BRANCH="$(git branch --show-current)"
[ "$RESTORE_BRANCH" = "$BRANCH" ] && RESTORE_BRANCH=main
trap 'rc=$?; if [ "$rc" -ne 0 ]; then if git checkout -q "$RESTORE_BRANCH" >/dev/null 2>&1; then echo "control-plane-sync: FAILED rc=$rc; restored checkout to $RESTORE_BRANCH" >&2; else echo "control-plane-sync: FAILED rc=$rc; RESTORE FAILED — checkout may still be on $BRANCH; fix before the 08:30 reset" >&2; fi; fi' EXIT
git fetch origin "$BRANCH" --quiet
git checkout -q "$BRANCH" 2>/dev/null || git checkout -q -b "$BRANCH" origin/"$BRANCH"
git reset -q --hard origin/"$BRANCH"

mkdir -p control-plane

# 1. Conductor track registry (name, db, repo, toml, roadmap)
if [ -f ~/.hermes/conductor-tracks.tsv ]; then
  cp ~/.hermes/conductor-tracks.tsv control-plane/conductor-tracks.tsv
fi

# 2. Watchdog alerts log (persistent record of relaunches/parked runs).
#    Bounded mirror: only the tail is committed so the data branch cannot
#    grow without limit (rm-017); the source log stays the full record.
WATCHDOG_MAX_LINES="${CONTROL_PLANE_WATCHDOG_MAX_LINES:-5000}"
if [ -f ~/.hermes/conductor-watchdog-alerts.log ]; then
  tail -n "$WATCHDOG_MAX_LINES" ~/.hermes/conductor-watchdog-alerts.log \
    > control-plane/conductor-watchdog-alerts.log
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

# Stage first, then test: `git diff --quiet` alone cannot see UNTRACKED files,
# so a fresh data branch would silently skip the mirror (found via shim test,
# cycle-2 B2).
git add control-plane/
if git diff --staged --quiet; then
  echo "no control-plane changes"
  git checkout -q main
  exit 0
fi

git -c user.name="fleet-bot" -c user.email="fleet-bot@users.noreply.github.com" \
  commit -qm "chore(control-plane): mirror fleet state $TS"
git push -q origin "$BRANCH"
echo "pushed control-plane mirror $TS"
git checkout -q main
