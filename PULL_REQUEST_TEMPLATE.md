## What changes here?

- [ ] Settings changes edit `common-settings.yaml` (never hand-tuned in the
      GitHub UI) or the accompanying list files (`protection-opt-in.txt`,
      `exclude-repos.txt`, `expect-public.txt`).
- [ ] I ran `python3 scripts/sync_repo_settings.py --dry-run` and reviewed the
      drift report; it shows the intended change and no surprises.
- [ ] Script changes: `python3 -m pytest tests/` passes (29+ tests, hermetic).

## Conventions (AGENTS.md)

- [ ] `hermes-conductor` is NOT added to `protection-opt-in.txt` (its promote
      flow ff-pushes main by SHA; protection would wedge it).
- [ ] Visibility is never auto-flipped — `expect-private`/`expect-public.txt`
      stays report-only; no visibility change is part of this PR.
- [ ] Workflow templates keep `runs-on: ubuntu-latest`, carry no local
      environment specifics, and pin actions to commit SHAs (no bare `@vN`).
- [ ] No secrets, tokens, or machine-local paths (self-hosted runners, LAN
      hosts, `/home/...` or `/work/...` paths) are introduced.
