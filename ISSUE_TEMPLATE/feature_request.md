---
name: Feature request
about: Extend the settings-as-code fleet or its automation
title: "[feat] "
labels: enhancement
assignees: ''
---

**Problem to solve**

What fleet-management problem does this solve? (Not the solution yet — the
problem.)

**Proposed approach**

The change you have in mind, and which surface it touches
(`common-settings.yaml`, a script, a workflow template, docs).

**Constraints to respect**

- Settings changes go through `common-settings.yaml`; the sync never flips
  visibility automatically.
- Free-plan account limits apply (e.g. branch protection only exists on
  public repos); anything plan-gated must be report-only.
- This repo is public: no secrets, no machine-local specifics in templates.

**Alternatives considered**

What else you tried or rejected, and why.
