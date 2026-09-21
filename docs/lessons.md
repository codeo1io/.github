# Lessons & prevention rules — codeo1io/.github maintenance cycles

Evidence-derived rules from repository-maintenance cycle 1 (run 52072e19204f4fb3a83d9abdd4d4f625,
2026-09-21). Each rule cites where it was learned; extend per cycle, don't re-learn.

## L1 — Security checkers verify pin SETS, not "any correct pin"
`known_fingerprints()` originally kept only the LAST key per algorithm. A stale
pinned key earlier in known_hosts was silently accepted while the checker reported
OK — a MITM window inside the MITM detector (ssh accepts any pinned key for the
host; an extra pin is as dangerous as a wrong one). Fix: collect every same-algorithm
pin (`dict[str, set]`) and FAIL on any deviation class (stale pin, extra pin, stale
algorithm, missing algorithm, mismatch). Prevention: any "does the pinned set match
the published set" checker must be exact-set bidirectionally, and its tests must
include the stale-alongside-valid direction, not only the all-wrong direction.
(evidence: assess attempt 1c279f56 synthetic known_hosts proof; tests/test_check_known_hosts.py)

## L2 — Compare GitHub names casefolded, and WARN on unmatched list entries
GitHub renames preserve identity but change canonical casing (`chadgpt` ->
`ChadGPT`), and exact membership checks silently drop the repo from protection
handling. Fix: `casefold_set()` for membership + `unmatched_entries()` WARN for any
opt-in/exclude entry matching no fleet repo (catches renames, deletions, typos).
Prevention: every name crossing the GitHub API boundary is compared casefolded, and
every fleet list ships with an unmatched-entry warning. (evidence: sync dry-run pre-fix
showed chadgpt absent from handling; post-fix explicit `ChadGPT: SKIP` decision line)

## L3 — Config keys that cannot be enforced are dead config; remove or gate them
`allow_auto_merge` in common-settings.yaml was plan-gated (403 on free accounts),
never enforced, and silently diverged from truth in docs. Fix: remove the key, state
the plan-gate honestly in README, and guard with a test that fails if the dead key
returns (MERGE_KEYS). Prevention: the settings file carries only keys the sync can
actually read/apply on the current plan; plan-gated desires live in the roadmap with
their decision gate named, not in the config.

## L4 — Report-only signals need an ack mechanism or they become noise
VISIBILITY DRIFT lines for three intended-public repos fired on every run with no way
to acknowledge — training operators to ignore output. Fix: `expect-public.txt` (same
format as exclude-repos.txt) acks intended-public originals; unlisted drift still
reported. Prevention: any report-only check ships with an explicit, reviewed ack list;
silence must mean "conformant or acknowledged", never "ignored".

## L5 — Pin actions to commit SHAs and verify the tag is commit-typed
Tag-name refs are mutable. When pinning, resolve the tag to an object and require
`object.type == commit` (`gh api repos/<owner>/<repo>/git/ref/tags/<tag>`) — an
annotated tag's SHA is a tag object, not a commit, and breaks `uses:`. Verified pins
for deploy-router.yaml: actions/checkout v7.0.1 -> 3d3c42e5aac5ba805825da76410c181273ba90b1,
dorny/paths-filter v4.0.3 -> ceb8a2b8f2d89434be7ff52d3de7ec3738c5cc9d (both commit-typed,
independently re-verified at review; the cycle-1 draft of this line dropped 9 middle
chars — always re-derive a SHA from `gh api git/ref/tags` at paste time, never from
a prior prose record).

## L6 — Re-probe live state every phase; never cite an earlier phase's count
The fleet moved 43 -> 44 repos mid-run (new repo `agent`, correctly reported as
merge drift by the tool). Ground truth drifts under you: probe git/gh/system state at
the top of each phase instead of citing stale numbers. Corollary: a drift report is a
success of the detector, not a failure of the batch.

## L7 — Temporary files are unlinked in `finally`, always
`mkstemp(delete=False)` without an unlink leaked one temp file per run into /tmp for
every cron execution (checker fingerprints). Fix: write via `TemporaryDirectory`/`finally`
unlink; test asserts zero leftovers under an isolated TMPDIR. Prevention: audit every
`delete=False` and long-lived CLI temp path; add a no-leak test next to it.

## L8 — A phase result is only as durable as its writes; materialize before the turn ends
Cycle 1's compound step described roadmap status flips that were never written to
disk (terminal interruption class): the review caught ROADMAP.md unchanged and the
spool record absent, i.e. two contradicting records of the same phase. Prevention:
every artifact a phase result names must exist on disk (or in the spool) BEFORE the
result message is emitted; re-verify with `stat`/`grep` as the last pre-send step.
This file and the ROADMAP.md addendum were materialized during the review-fix step
that closed that gap.

---

# Cycle 2 lessons (2026-09-21, pre-review evidence: implement B1-B4 + targeted/full test outcomes)

## L9 — `git diff --quiet` is blind to untracked files; stage first, then test
The control-plane mirror's no-change check (`git diff --quiet && git diff --staged
--quiet`) reported "no control-plane changes" on a fresh `data` branch while files
WERE copied: untracked files don't appear in `git diff`. Any script whose job is
"detect changes then maybe commit" must `git add` first and test the STAGED diff.
Found by running the script against a scratch repo in the implement shim matrix —
not by reading it; two readers missed it.

## L10 — Mode-only commits look like merge conflicts but aren't
The stranded cycle-1 batch overlapped main's 9b0a4e3 on both scripts, which the
assessment flagged as conflict risk. `git show 9b0a4e3` revealed the overlap was
0 content lines — only exec-bit flips. Cost of the "merge": one `git checkout
<sha> -- <paths>` plus `chmod`. Before planning merge effort, separate content from
mode (`git diff --stat`, `--summary`); a 0-line overlap needs a content-take, not a
rebase plan.

## L11 — Cron-driven helpers must bound every subprocess call
The old `gh()` had no timeout: one hung gh/network call would wedge the 08:30 cron
silently (watchdog only fires on conductor relaunches). Fix pattern: wrap
`subprocess.run(..., timeout=N)`, and on `TimeoutExpired` return a synthetic
`CompletedProcess(rc=124)` so EXISTING error paths (allow_fail per-repo skip, FATAL
on listing) handle it — no new exception pathway. A timeout that raises bypasses
the caller's graded handling; a timeout that synthesizes the failure shape flows
through it.

## L12 — Scripts that switch branches in a SHARED checkout must trap-restore
scripts/control-plane-sync.sh checks out `data` inside /work/projects/.github. Any
failure under `set -e` before the final checkout leaves the worktree stranded on
`data`, and the next 08:30 run would `git reset --hard` onto the wrong branch.
Pattern: capture `RESTORE_BRANCH=$(git branch --show-current)` at entry (defaulting
to main when already on the target branch), `trap ... EXIT` restoring it on nonzero
rc. Companion: single-flight `flock` so concurrent cron invocations exit 0 instead
of racing checkout/reset/push.

## L13 — Mirror exactly what you must, bounded; the source stays the record
The watchdog mirror copied a 12,686-line ever-growing log into a public data
branch. Bounded mirror (`tail -n ${VAR:-5000}`) caps the exposure; the header of
the source log still declares itself the persistent record. Design question for any
cron mirror: is the destination the archive, or a window? If a window, cap it.

## L14 — Ledger claims must cite live-verified evidence, and corrections carry an audit line
corrections.yaml claimed "gitleaks sentinel covers them" for two repos; live
`gh api .../contents/.github/workflows` showed one has no sentinel at all. When a
ledger entry is found half-false, don't rewrite it silently: keep the entry, add an
`amended:` line with date + what the audit showed + which run corrected it. The
ledger's value is the trail, not just the current truth.

## L15 — A four-case shim matrix is enough to test a cron shell script
No pytest harness existed for control-plane-sync.sh; the implement phase built one
scratch bare repo + a PATH-shimmed `git` (push -> exit 1) and proved all four
behaviors in minutes: (T1) failing push -> rc!=0 + branch restored to main,
(T2) flock held -> rc=0 + lock message, (T3) tiny timeout constant -> synthetic 124,
(T1b) happy path -> push + back on main + mirror capped. Persisting this matrix as
tests/test_control_plane_sync.py is a standing candidate (rm-024).

## L16 — Re-probe the validation digest, and copy verbatim only when nothing executable changed
Two consecutive phases (targeted_tests, full_tests) changed zero executable
surfaces and copied the dispatch digest verbatim — correct per rule — but each
RE-DERIVED it first to prove currency (validation_policy.validation_digest on base
9901e2c reproduced the dispatch value byte-for-byte). The verbatim copy is a claim
about the tree; verify the claim mechanically before declaring it.
