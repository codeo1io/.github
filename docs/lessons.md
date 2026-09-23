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

## L17 — Pin wall-clock in hermetic tests when the generator stamps time
(cycle-3, run c48e9687) control-plane-sync mirrors a `# generated $TS` header;
tests comparing mirror output went intermittent when runs straddled a second
boundary. Fix the harness — a `date` shim in the hermetic env — never the
script: the stamp is provenance by design. 8/8 consecutive green runs after
the shim.

## L18 — After a content-merge, re-read the landed file before layering fixes
The assess phase had read main's pre-batch scripts; the C1 merge landed c04a549,
which already carried the gh() timeout and the dead cur_merge removal. Editing
against stale reads would have duplicated work. Re-read every file a merge
touches before editing it.

## L19 — Persist ad-hoc shim validation as tracked tests the same cycle
The cycle-2 shim matrix existed only as throwaway scripts; the cycle-3 fix
re-built it as tests/test_control_plane_shims.py. Ad-hoc validation that
isn't a test is validation you will re-perform (or skip) next cycle.

## L20 — Land stranded validated batches before layering same-file edits
C2-C4 edited the same files the stranded cycle-2 batch touched; landing C1
first made every later edit apply to the true final content. A stranded batch
under a same-file edit becomes a merge-conflict factory.

## L21 — Count evidence from the machine, not the eyeball
The implement record claimed "21 repos listed"; live ground truth was 44
(`gh repo list --json` count and GraphQL repositories.totalCount agree). The
code was right; the evidence string was wrong. Derive every number you cite
from a command output, never from a recollection of scrolling.

---

# Cycle 4 lessons (2026-09-22, pre-review evidence: Batch D implement + targeted/full test outcomes)

## L22 — A "clean" scan proves nothing unless the invocation demonstrably ran
The first hermes-agent fleet scan reported "clean, 537 commits". The command had
an unquoted empty `$WT` variable, so gitleaks ran with a wrong `--config` path
(and would have failed loudly, not quietly, on a missing one). A clean result
without proof the tool ran is a false negative wearing a green badge. Prevention:
every scan verdict must be accompanied by invocation proof — commit count,
config path echo, or exit-code capture — and a suspiciously fast/empty "clean"
is a bug report, not a pass. (evidence: authoritative rescan: 44,422 commits,
964 findings; the 537 figure came from the failed invocation's stderr)

## L23 — Secret-scanner generic rules over CODE corpora need an identifier-proof shape
The stock-derived generic-api-key regex fired 29 times on hermes-gpt source
files: `token = _windows_gateway_resume` (value looks base64), compound YAML
keys (`export_token:`), and JS `++latestSwitchToken` (prefix + is
base64-charset-legal). The working shape: key must have the secret word as its
last word-segment before the separator (`_startup_api_key_override` excluded,
`export_token:` caught), value must start alphanumeric and stay base64/hex.
Both classes were found in LIVE corpora, not invented. Prevention: any new
generic rule ships with (a) an FP corpus of real-looking benign lines and
(b) a TP corpus, both asserted in tests. (evidence: tests/test_gitleaks_config.py;
9-line FP / 6-line TP corpora from hermes-gpt + hermes-agent)

## L24 — Blanket exemptions are how scanners go blind; exempt narrowly, at a named scope
`(?i)(tests?|e2e|evals)/.*` fleet-wide meant any secret committed under tests/
was invisible to the fleet's ONLY automated scanner — and test fixtures are
exactly where real-looking credentials accumulate. The fix inverts the default:
no tree is exempt by category; exemptions are per-path with a triage comment,
synthetic-secret test/docs hits go to per-repo `.gitleaksignore` (the scanner's
native mechanism, fingerprint-stable), and the fleet config itself carries a
test that plants a secret inside tests/ and asserts DETECTION. Prevention: an
allowlist entry must name its subject (path or fingerprint) and carry its
rationale; a category-shaped allowlist is a standing finding.

## L25 — "No bare action refs" greps are false-negative factories; match the ref shape exactly
`grep 'uses:.*@[a-zA-Z]'` looks like a pin check but matched our own SHA pins
(any SHA starting with a letter) and, piped through `grep -v '# '`, silently
dropped every pinned line carrying a trailing version comment — reporting "all
pinned" from a check that couldn't see the difference. Correct matcher: extract
the `uses:` value and require `owner/repo[@path]@<exactly 40 hex>` or a local
`./` workflow path. Prevention: pin lints assert the ALLOWED shape, never
grep-for-the-disallowed substring; test the lint against a letter-leading SHA.
(evidence: cycle-4 targeted_tests, strict matcher found 7/7 clean where the
loose one was structurally blind)

## L26 — Delivery loss after completed work: verify-and-deliver, never redo
Six consecutive implement attempts were voided by provider 429s AFTER the work
was done — the envelope arrived failed/phase_result-absent. The correct response
to a re-issued attempt is: re-verify the worktree state matches the claimed
result (git status/diff digest), complete any unit genuinely still open, and
deliver the SAME PhaseResult to the NEW spool path. Redoing finished work or
re-litigating decisions multiplies drift risk on every retry. Prevention: end
each attempt with the result materialized on disk (spool JSON written and
validated) before the final message, so a lost message costs one turn, not the
work. (evidence: attempts faf49621..fd940430, all delivering the same tree)

## L27 — The executed path is ground truth, not the tracked twin
For two cycles the B2 hardening lived in scripts/control-plane-sync.sh while
production never ran it — the 08:40 cron resolved a deployed wrapper that execs
scripts/sync_data_branch.py, and the shim tests happily certified the unexecuted
twin. Prevention: before calling deployment hardening "done", resolve the
production wiring end-to-end (cron jobs.json -> deployed wrapper -> the file it
actually execs), put the hardening on THAT file, retire the twin, and retarget
the tests at the executed artifact. One implementation, one test target.
(evidence: cycle-5 assess — 13,524-line uncapped mirror vs the 5,000 cap while
the hardened script sat dead in-tree; closed by cycle-5 E1)

## L28 — A manifest that omits the entrypoints certifies nothing
MANIFEST.sha256 pinned 14 fleet scripts but NEITHER cron-wired sync entrypoint —
so the one artifact meant to catch deployed drift was blind to exactly the
divergence that made rm-017's hardening inert. Prevention: build verification
from the wiring inventory (cron jobs.json), not from the manifest's existing
set; cover wrapper-style deployments with BOTH digests (wrapper + declared
delegate); prove the check with a planted divergence, and run it live before
declaring the gap known-and-real.
(evidence: cycle-5 research — grep MANIFEST for both entrypoints -> 0; E2 live
run rc=1 naming exactly the two unpinned entrypoints)

## L29 — Scanner allowlist semantics must be proven, not assumed
gitleaks allowlist regexes behave differently per field: a PATH allowlist exempts
whole files from ALL rules, while stopword/value regexes match the CAPTURED
SECRET VALUE, not the line they visually sit next to. Both were learned by live
A/B with the real binary after a wrong line-regex assumption survived two reads.
Prevention: for every allowlist entry, write the minimal A/B pair (secret that
must fire, variant the entry would suppress), run it with the pinned binary, and
persist the pair as a regression test before narrowing.
(evidence: cycle-5 assess+research A/B on 8.28.0 AND pinned 8.30.1 — ghp_ token
invisible under tests/unit/test_fixture_loader.py; q8Kw2xxx… value suppressed;
closed by cycle-5 E3 + tests/test_gitleaks_config.py regressions)

## L30 — Documentation claims must name the mechanism that exists
The sentinel workflow comment promised "uploads the SARIF report as an artifact
on failure" — but no upload step existed, because the upload was action-NATIVE
(gitleaks-action v3 uploads gitleaks-results.sarif itself unless disabled) and
therefore invisible in the workflow file. The assess finding "SARIF absent" was
itself half-wrong: absent from the YAML, present in reality. Prevention: read
the action's source before writing (or acting on) a claim about what a workflow
"does"; state the mechanism, not the shape; take live counts in docs from the
run, never from estimates (README said 42 tests, the run said 55).
(evidence: cycle-5 E4 — src/gitleaks.js L128-135 + src/index.js L22-28 vs the
L9 comment; live artifacts on .github + magic-hermes confirmed)

## L31 — An authoritative command in the work order is byte-matched, not interpreted
full_tests rejected two correct-in-substance local-suite substitutions because
the fold gate string-matches validation_evidence.command against the dispatch
full_command verbatim; the named github_ci_validate.py route is the SANCTIONED
mechanism (everything happens in a temp clone: ephemeral conductor/ci-* refs,
draft PR, polls checks, full self-cleanup — the run worktree is never touched).
Prevention: when a work order names a command AND prohibits stages, read the
command's source to see which side effects belong to the deliverable vs the
validation mechanism before substituting anything; the prohibition list binds
the deliverable's stages, not the phase's own sanctioned validation.
(evidence: cycle-5 full_tests — conductor.db records 2f0d6296/826cd7cc failed
"substitutions are not accepted"; attempt 365079da ran it verbatim -> ok:true,
PR #5 self-scan SUCCESS, refs auto-deleted, worktree unchanged)
