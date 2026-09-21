# OWNERS — Hermes Agent Kanban Board (amended doc of record, v2)

Amended 2026-09-17 by t_acd6a2e8 (area-1/area-4 primary: default), supersedes the
v1 merge at `attachments/t_de598ac3/OWNERS.md`. v1's policy sections (§2 levels/SLA/
escalation, §3 `tasks.owner` storage convention) are reaffirmed unchanged. This
amendment corrects v1 §1 (area table) and resolves v1 §5 (open questions) under the
area-1 conflict rule, based on independently verified roster forensics.

## 0. Roster of record (binding)

An owner/assignee value is valid only if it is one of:

| Profile | Status | Evidence (verified 2026-09-17, live DB + filesystem) |
|---|---|---|
| `default` | REAL — primary executor | task_runs: 1,988 total, 161 completed (only profile with completed runs besides fixture `w`) |
| `voice` | REAL — voice-scope only | profile born 2026-08-20, distinct model chain (glm-5.3/cliproxyapi), 1.76 MB state.db; 0 task_runs to date, max_turns=4 — route only voice-scope cards |
| `codeo1io` | REAL — human operator | only real GitHub identity; secrets are human-only |
| builder-auth, coder, demo, ops, secondary, work, worker, yangyang | FIXTURE — **not assignable** | born 2026-09-13 (leak window of t_404376e6), no model key in config.yaml, 0 sessions ever, byte-identical 266,240-byte template state.db ×8; task_runs: ops 12/12 crashed, coder 3/3 crashed, rest 0; names verbatim in repo tests (tests/hermes_cli/test_web_server.py:2680 builder-auth/example.com) |

**Roster rule:** any open card whose `assignee` or `owner` is outside
{default, voice, codeo1io} is a defect. A fixture profile becomes assignable only
after it gains a configured model AND one clean completed run. Fixture profiles
remain as *archived-after-audit disposition* items owned by default (see component map).

## 1. Area → Owner map (corrected)

Scopes unchanged from v1; primaries/backups corrected to the roster of record.
With a two-executor roster, `default` is accountable for all non-voice areas; the
area rows remain the routing/scoping taxonomy for when the roster grows.

| # | Area | Scope | Accountable owner | Backup |
|---|------|-------|-------------------|--------|
| 1 | Board orchestration & triage | Decompose ambiguous cards, route work, wake/merge parents | default | codeo1io |
| 2 | Kanban feature engineering | owner field end-to-end, dispatcher, links, notifications (`kanban_db.py` hotspot) | default | codeo1io |
| 3 | Board hygiene & data integrity | purge fixture corpora, stop test leaks, reclaim stranded runs | default | codeo1io |
| 4 | Ownership policy & docs | OWNERS.md, CODEOWNERS-equivalent docs, escalation policy | default | codeo1io |
| 5 | Voice assistant | `voice` profile end-to-end, wake/STT/TTS pipeline | voice | default |
| 6 | Auth & builder tooling | MCP auth connectivity, profile/tool scaffolding | default | codeo1io |
| 7 | Work services & integrations | MCP service mesh, project service integrations | default | codeo1io |
| 8 | Demo & showcase | demo/showcase tasks | default | codeo1io |

Catch-all: unmapped area → `default` (rung 3). No orphans.

## 2. Ownership policy

Unchanged from v1 (t_de598ac3 §2, sourced from OWNERSHIP-POLICY.md t_03029e73):
four levels (Accountable = the assignee, exactly one per task; Contributor;
Reviewer; Backup active only during escalation), 4h mention/blocker SLA,
3-rung escalation ladder primary → area backup → `default` (human-owned items:
codeo1io → `default`), transfers require audit comments.

## 3. Board storage convention (`tasks.owner`)

Unchanged from v1 §3 (spec of record: t_eb466ece): owner = transferable,
routing-neutral accountability label; assignee = execution routing; created_by =
immutable provenance; default owner=created_by at creation; transfers emit
`owner_transferred` {"from","to"} into `task_events`; no COALESCE on any query path.
Invariant on open cards: owner == assignee == area primary's choice; divergence is
a defect flag, not a silent rewrite.

Note: the shipped `hermes_cli/kanban_db.py` (4,212 lines) has no owner API yet —
the column exists (tasks col 38) and was populated by audited raw-SQL passes
(run 2004 merge pass; run 2009 backfill). The schema/API implementation cards are
t_e13ba853 / t_c39dfaac (area 2, un-wedged to default by this ruling).

## 4. Component-level ownership

The component→owner→fallback map of record (40 components: profiles, board/data,
full codebase, 22 sibling repos, 16 live services, 36 crons + 5 timers + crontab)
is the tree-B map: `attachments/t_851e7951/OWNERS.md`
(sha256 e55552ce30b45feed0ce7ed2ce71d69bb64835ef1e0aa3ab2c58bf400ec281d5).
It is 100% roster-valid by construction and is adopted by reference as the
component appendix of this doc. Secrets: codeo1io primary, human-only.

## 5. Ruling log — v1 open questions resolved (area-1 decision, 2026-09-17)

1. **t_03239108** (ops, "Add ownership map docs") — CLOSED as superseded: its
   deliverable is this doc + the CODEOWNERS work live in t_81a117fa.
2. **Duplicate decomposition trees** — RULED: tree A (t_acd6a2e8) is canonical for
   the ownership doc/policy; tree B's map (t_851e7951) is adopted as the component
   appendix (§4). Root t_51cd53eb CLOSED as superseded by this ruling. Tree B's
   children were NOT killed: t_70892a6d (board-wide backfill, run 2009) and
   t81a117fa (CODEOWNERS + schema enforcement, run 2008) do real non-duplicate
   implementation work and are re-scoped into the area-2 lane, consumers of this doc.
3. **�1,535 fixture cards** (alpha/beta/w, created_by NULL) — disposition stays with
   area 3 via t_58dec5f0 (triage) and t950d4b99 (cleanup); both now owner/assignee
   default (un-wedged). Deliberately unowned until dispositioned.
4. **`tasks.owner`semantics** — spec t_eb466ece governs; implementation lane
   t_e13ba853/t_c39dfaac un-wedged to default (were assignee=coder, provably
   dead: 3/3 crashed runs).
5. **t_da696979 triple divergence** — resolved by the roster rule: assignee ops →
   default (ops dead); scope unchanged (auto-decomposer stub emission, area-2/3
   boundary); stored owner default stands.
6. **t_00d561ef** — CLOSED as superseded by completed t_404376e6 (conftest
   sandboxing verified 2026-09-15).
7. **t_1405ac5f / t_ee088c6c** — CLOSED as superseded by t_eb466ece
   (ownership-spec.md is the definition of record).

## 6. Review cadence

Quarterly re-confirmation (next **2026-12-17**), owner: area-4 primary (default).
Event-triggered re-review: roster change, new long-lived service/cron, or double
SLA miss. Changes to this doc require a comment on the changing card and
`owner_transferred` audit events for any stored-owner change.

— End of OWNERS.md v2. Sources: t_de598ac3 OWNERS.md (v1), t_851e7951 component
map, t_03029e73 policy, t_df530d06 area scopes, t_eb466ece storage spec.
