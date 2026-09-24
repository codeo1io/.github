# OWNERS — Hermes board, profiles, code, services, automations

Task: t_851e7951 · 2026-09-17 · Owner-of-record: @default (review: @codeo1io)
Canonical until merged into the consolidated OWNERS.md (see "Relationship to sibling subtree").
Every component below carries exactly ONE primary owner and ONE fallback (≠ primary).

## 0. Ground truth this map is built on (evidence, not assumption)

- `task_runs` by profile: **default 1,985 · ops 12 (all crashed) · coder 3 (all crashed) · all others 0.**
- Profile dirs: `voice` born 2026-08-20, state.db 1.76 MB, 85 sessions — REAL. The other 8
  (`builder-auth coder demo ops secondary work worker yangyang`) were born 2026-09-13/14
  inside the dispatcher-test leak window (t_404376e6), hold template configs
  (`example.com` MCP URLs, `svc-a-bin` stubs), 0 sessions ever, and their names appear
  verbatim in repo test files (`tests/hermes_cli/test_web_server.py:2680`,
  `tests/gateway/test_pairing.py:605`). They are **fixture artifacts, not a staffed roster**.
- Board: 1,752 tasks; ~1,535 created_by NULL fixtures (assignees alpha/beta/w — profiles that
  do not exist). The existing `tasks.owner` column is sparsely populated by fixture probes
  (`alice`, `carol`, `dana`, `zoe`, `Team X`) — treat those values as void.
- One human operator exists: **@codeo1io** (git: codeolio@protonmail.com; GitHub user codeo1io).

**Roster rule (binding for children t_70892a6d / t_81a117fa):** an owner value is only valid
if it is one of `default`, `voice`, `codeo1io`. Any other profile name as an owner is a defect.

## 1. Profiles

| Component | Primary owner | Fallback | Notes |
|---|---|---|---|
| `default` profile (config, sessions, model glm-5.3) | default | codeo1io | Workhorse; only proven executor |
| `voice` profile (wyoming STT/TTS, wake, agent loop) | voice | default | Real since Aug-20; distinct model chain |
| 8 fixture profiles (builder-auth, coder, demo, ops, secondary, work, worker, yangyang) | default | codeo1io | Owner = disposition: archive after audit; NOT assignable as owners until they gain a configured model + one clean run |

## 2. Board & data

| Component | Primary | Fallback |
|---|---|---|
| kanban.db schema/dispatcher mechanics (`hermes_cli/kanban_db.py` — known hotspot) | default | codeo1io |
| Fixture-card corpus (~1,535 rows alpha/beta/w) — purge/quarantine | default | codeo1io |
| `tasks.owner` column semantics + backfill (t_70892a6d) | default | codeo1io |
| Attachment/workspace dirs under ~/.hermes/kanban/ | default | codeo1io |
| State DBs (state.db, conductor*.db, autonomy.db, projects.db, tracks.db …) | default | codeo1io |
| Secrets: ~/.hermes/.env, profile .env files, vault items | codeo1io (human-only) | — (never agent-owned; default may rotate under explicit instruction) |
| Backups (~/.hermes/backups, /work/projects/backups, gmail mbsync archive) | codeo1io | default |

## 3. Codebase (repo: hermes-agent; running install ~/.hermes/hermes-agent @ fork codeo1io/hermes-agent; dev checkout /work/projects/hermes-agent)

| Module/area | Primary | Fallback |
|---|---|---|
| agent/ core loop + model providers | default | codeo1io |
| gateway/ (+ tui_gateway, ui-tui) | default | codeo1io |
| hermes_cli/ (CLI, kanban_db.py, web server) | default | codeo1io |
| hermes_state_*.py (state/persistence, 30 modules) | default | codeo1io |
| tools/ + toolsets.py (tool runtime) | default | codeo1io |
| acp_adapter/ (ACP protocol adapter) | default | codeo1io |
| scripts/ + tests-js/ (repo scripts, JS test suite) | default | codeo1io |
| plugins/, skills/, optional-skills, optional-mcps, plugin-catalog | default | codeo1io |
| web/, website/, apps/ (dashboard & docs site) | default | codeo1io |
| tests/, evals/, CI workflows (self-hosted runners) | default | codeo1io |
| Voice stack touchpoints (audio, STT/TTS wiring) | voice | default |
| docs/ (incl. this OWNERS.md) | default | codeo1io |

Sibling project repos — hermes-infra, hermes-conductor, hermes-autonomy (+research,
+ecosystem-routing), hermes-gpt, hermes-control-ui, hermes-chat-journal, magic-hermes,
hermes-roadmap, hermes-curator-evolver, dashboard, embeddings-api, zen-proxy, glmplus,
chadgpt, agenttrace, jarvis, stonks, llm-wiki-cli, openclaw-strategy — all: primary
**default**, fallback **codeo1io**; stonks + jarvis carry personal/business data →
escalate data-handling decisions to **codeo1io** first.

## 4. Services & daemons (verified live 2026-09-17)

| Service | Primary | Fallback |
|---|---|---|
| Hermes gateway + dashboard (pid 1455502, :7860/:8642) | default | codeo1io |
| Conductor gateway + supervise-fleet + integration-fleet-run (pids 1644516/1646217/1646220) | default | codeo1io |
| Conductor maintenance-run campaigns (2 live) | default | codeo1io |
| hermes-gpt MCP server (1458519) + mcp_death_supervisor | default | codeo1io |
| hermes-webui (:8787), hermes-control-ui backend (:8765), public_ingress hypercorn (:4760), embeddings-api (:8320) | default | codeo1io |
| hermes-chat-journal (:8791) + Discord backfill Chrome/CDP (:9223) | default | codeo1io |
| codebase-memory MCP daemon (:9749), xiaohongshu-mcp (:18060, agent-reach) | default | codeo1io |
| Desktop remote access: x11vnc (:5900/5901) + websockify/noVNC (:8792) | default | codeo1io |
| Alexa voice bridge (hermes-alexa-bridge.py, :8788) | voice | default |
| stonks API (:8000) | default | codeo1io |
| glmplus node (:4567), zen-proxy | default | codeo1io |
| Wyoming STT bridge (pid 972, :10302) | voice | default |
| GitHub Actions self-hosted runners (~/actions-runner, ~/runners/hermes-agent, ~/runners/hermes-control-ui) | default | codeo1io |

## 5. Recurring automations

| Group (count) | Primary | Fallback |
|---|---|---|
| Autonomy suite crons (~16: discovery, self-improvement, digests, research, retention, roadmap-sync, convergence) | default | codeo1io |
| Infra watchdogs crons (~11: MCP/jarvis/runner-stall/disk/fleet/spool/pi-reaper/gateway-db-gc/repo-config-guard/magic-hermes) | default | codeo1io |
| Fix-queue drivers (~5: work driver, reland-r65 ×2, conductor-track, conductor-auto-promote) | default | codeo1io |
| Data-pipeline crons (discord-backfill-drain, ven-deletion-audit-watch) | default | codeo1io |
| systemd user timers (5: model-policy-guard, hermes-gpt-watchdog, tmp-cleanup, watchdog-sweep, gw-restart drain) | default | codeo1io |
| System crontab: stonks pipelines (ET 6:25/6:30/weekly) | default | codeo1io |
| System crontab: mbsync gmail backup (personal mailbox) | codeo1io | default |
| System crontab: workpool-guard (30m) | default | codeo1io |

## 6. Review cadence

- **Quarterly re-confirmation** of every table above (next: 2026-12-17). The consolidation
  pass audits the board for open cards whose owner is missing, plural, or not in
  {default, voice, codeo1io}.
- **Event-triggered re-review** (don't wait for the quarter): a profile is created/retired,
  a new long-lived service or cron job is added, or a primary owner misses the 4h SLA
  defined in OWNERSHIP-POLICY.md twice in a row.
- Escalation ladder (from OWNERSHIP-POLICY.md): primary → area fallback → `default`;
  human-owned items escalate to codeo1io → default.

## 7. Discrepancies / open questions (flagged, not silently resolved)

1. **Duplicate decomposition roots.** This subtree (t_851e7951 → t_70892a6d + t_81a117fa →
   root t_51cd53eb) overlaps sibling subtree t_acd6a2e8 → (t_03029e73 ✓ + t_df530d06 ✓) →
   t_de598ac3 (running). Recommendation: t_de598ac3 merges BOTH maps; my children
   (backfill, CODEOWNERS) consume the merged doc. One canonical tree must be recorded.
2. **Sibling map assigns owners to fixture profiles** (coder/ops/demo/work/builder-auth/
   secondary/yangyang as area owners). task_runs proves they cannot execute (0 completed
   runs, 12/12 and 3/3 crashes, no model configured). Those assignments must not survive
   the merge — an owner that cannot run a card is an unowned card.
3. **tasks.owner already contains fixture values** (alice/carol/dana/zoe/Team X/worker).
   t_70892a6d's backfill must overwrite per the roster rule, not preserve them.
4. **CODEOWNERS translation** (t_81a117fa): GitHub reviewers must be real GitHub
   identities — only @codeo1io qualifies. CODEOWNERS should map paths → @codeo1io with
   comments carrying the board owner (default/voice) per this map.
5. `voice` as an owner is valid for board cards but has max_turns=4 / low reasoning —
   route only voice-scope cards to it; everything execution-heavy stays with default.
