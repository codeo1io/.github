"""Tests for the fleet gitleaks configuration (cycle-4 rm-037 / batch D1).

Locks the detection-integrity properties the private-leak sentinel depends on:

- structural: the config parses, extends the default ruleset, and carries the
  fleet rule pair (quoted + unquoted generic-api-key);
- no blanket exemptions: the retired tree/extension allowlist patterns
  (``(?i)(tests?|e2e|evals)/.*``, ``\\.(test|spec)\\.[a-z]+$``, conftest.py,
  the ``\\.md`` extension blanket) must stay gone — exemptions are per-file or
  convention-scoped (fixture dirs) with triage comments;
- regex semantics: the unquoted generic rule must catch bare YAML/TOML secret
  assignments while rejecting the identifier-shaped code assignments observed
  in the 2026-09-22 fleet triage (hermes-gpt / hermes-agent corpora), and the
  quoted rule must require quote-wrapped values;
- allowlist escapes (cycle-5 rm-037 reopen): the fixture path exemption is
  directory-component anchored (files NAMED *fixture* under tests/ are
  scanned — a planted ghp_-shaped token in tests/unit/test_fixture_loader.py
  previously produced ZERO findings), and value suppression is shape-anchored
  (all-x placeholders and "prefix...suffix" redaction stubs only — values
  merely containing ``xxx`` are findings);
- integration (requires a local ``gitleaks`` binary): a synthetic secret in a
  scratch repository IS detected — including inside a ``tests/`` tree, which
  is the exact blind spot the retired blanket created — and a clean tree is not.

Secret-shaped literals in this file are assembled at runtime from inert
fragments so the sentinel scanning this repository itself stays at zero
findings without an exemption for this test file.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "gitleaks.toml"


def load_config() -> dict:
    with open(CONFIG_PATH, "rb") as fh:
        return tomllib.load(fh)


def rule_by_id(cfg: dict, rule_id: str) -> dict:
    matches = [r for r in cfg.get("rules", []) if r.get("id") == rule_id]
    assert matches, f"rule {rule_id!r} missing from config"
    return matches[0]


def assembled_secret(prefix: str = "Zr4k9Wm2", suffix: str = "Xp7Qv5Nt8Lb3") -> str:
    """High-entropy synthetic secret, assembled so no full literal sits in source."""
    return prefix + suffix + "9c"


# --------------------------------------------------------------------------
# Structural
# --------------------------------------------------------------------------


def test_config_parses_and_extends_defaults() -> None:
    cfg = load_config()
    assert cfg.get("title"), "config title missing"
    extend = cfg.get("extend", {})
    assert extend.get("useDefault") is True, (
        "fleet config must extend the default ruleset, not replace it"
    )


def test_fleet_rule_pair_present() -> None:
    cfg = load_config()
    ids = {r.get("id") for r in cfg.get("rules", [])}
    assert "generic-api-key" in ids
    assert "generic-api-key-unquoted" in ids, (
        "unquoted-value variant missing — quoted-only narrowing drops bare "
        "YAML/TOML secret coverage (cycle-4 assess rm-037)"
    )
    for fleet_id in ("hermes-hass-token", "wyoming-groq-key", "hermes-env-file-inline"):
        assert fleet_id in ids


def test_generic_rules_carry_entropy_floors() -> None:
    cfg = load_config()
    for rule_id in ("generic-api-key", "generic-api-key-unquoted"):
        rule = rule_by_id(cfg, rule_id)
        assert float(rule.get("entropy", 0)) >= 3.5, f"{rule_id} lost its entropy floor"


# --------------------------------------------------------------------------
# No blanket exemptions (the retired rm-037 patterns must stay retired)
# --------------------------------------------------------------------------

BLIND_SPOT_PATHS = [
    "tests/unit/test_payments.py",   # tests?/ tree blanket
    "e2e/scenario_login.py",        # e2e member of the same blanket
    "evals/bench_embed.py",         # evals member of the same blanket
    "src/app.test.ts",              # .test. extension blanket
    "src/widget.spec.ts",           # .spec. extension blanket
    "tests/conftest.py",            # conftest blanket
    "docs/runbook.md",              # .md extension blanket
    "README.md",
]


def _allowlist_paths(cfg: dict) -> list[str]:
    return list(cfg.get("allowlist", {}).get("paths", []))


def test_retired_blanket_patterns_are_gone() -> None:
    cfg = load_config()
    for pattern in _allowlist_paths(cfg):
        compiled = re.compile(pattern)
        hits = [p for p in BLIND_SPOT_PATHS if compiled.search(p)]
        assert not hits, (
            f"blanket allowlist pattern {pattern!r} matches {hits} — "
            "test/e2e/evals trees, test/spec extensions, conftest.py, and .md "
            "files must NOT be blanket-exempt (rm-037); use per-file triaged "
            "entries or the repo's own .gitleaksignore instead"
        )


def test_fixture_dir_convention_still_scopes_narrowly() -> None:
    cfg = load_config()
    patterns = [re.compile(p) for p in _allowlist_paths(cfg)]
    # The fixture-dir convention must not swallow ordinary test code.
    for pattern in patterns:
        assert not pattern.search("tests/unit/test_payments.py")
    # And a per-file triaged entry must still exist for a known fixture file.
    assert any(re.compile(p).search("test_ui_security.py") for p in _allowlist_paths(cfg)), (
        "triaged per-file entry for test_ui_security.py disappeared — if this "
        "was intentional, update the triage comment and this test together"
    )


def test_allowlist_entries_are_not_directory_trees() -> None:
    """Every paths entry must be an extension, a basename, or a scoped dir —
    never a bare source-tree wildcard like ``src/`` or ``tests/``."""
    cfg = load_config()
    for pattern in _allowlist_paths(cfg):
        assert not re.fullmatch(r"(?i)[a-z0-9_./-]+/\.\*", pattern), (
            f"{pattern!r} is a bare tree wildcard — not allowed"
        )


# --------------------------------------------------------------------------
# Regex semantics of the generic pair
# --------------------------------------------------------------------------

# Identifier-shaped code assignments observed as false positives in the
# 2026-09-22 fleet triage (hermes-gpt / hermes-agent full-history scans).
UNQUOTED_FALSE_POSITIVES = [
    "token = _windows_gateway_resume",
    "_coerce_threshold_tokens_cap = _coerce_max_tokens",
    "_new_tokens = plan.approx_tokens",
    "_startup_api_key_override = _startup_route.api_key",
    "request_pressure_tokens = _anchored_pressure",
    "preflight_tokens > _last",
    "const token = ++latestSwitchToken",
    "token = self.read_token_from_env()",
    "some_module.token",
]

UNQUOTED_TRUE_POSITIVES = [
    "api_key: {secret}",
    "password = {secret}",
    "secret: {secret}",
    "export_token: {secret}=",
    "auth-token = {secret}",
    "client_secret = {secret}",
]


def _render(lines: list[str], secret: str) -> list[str]:
    return [ln.format(secret=secret) for ln in lines]


def test_unquoted_rule_rejects_identifier_values() -> None:
    cfg = load_config()
    rule = rule_by_id(cfg, "generic-api-key-unquoted")
    rx = re.compile(rule["regex"])
    for line in UNQUOTED_FALSE_POSITIVES:
        assert not rx.search(line), f"unquoted rule FP on code line: {line!r}"


def test_unquoted_rule_catches_bare_assignments() -> None:
    cfg = load_config()
    rule = rule_by_id(cfg, "generic-api-key-unquoted")
    rx = re.compile(rule["regex"])
    secret = assembled_secret()
    for line in _render(UNQUOTED_TRUE_POSITIVES, secret):
        assert rx.search(line), f"unquoted rule missed bare assignment: {line[:24]!r}…"


def test_quoted_rule_requires_quote_wrapped_values() -> None:
    cfg = load_config()
    rule = rule_by_id(cfg, "generic-api-key")
    rx = re.compile(rule["regex"])
    secret = assembled_secret()
    assert rx.search(f'api_key = "{secret}"'), "quoted rule must catch quoted values"
    assert rx.search(f"token: '{secret}'")
    assert not rx.search(f"api_key = {secret}"), (
        "quoted rule must not fire on bare values — that is the unquoted "
        "rule's job (pair semantics)"
    )


# --------------------------------------------------------------------------
# Integration (real gitleaks binary; skipped when unavailable)
# --------------------------------------------------------------------------


def _gitleaks_bin() -> str | None:
    return os.environ.get("HERMES_GITLEAKS_BIN") or shutil.which("gitleaks")


def _run_gitleaks(bin_path: str, cwd: Path, report: Path) -> int:
    return subprocess.run(
        [bin_path, "git", ".", "--config", str(CONFIG_PATH), "--redact",
         "--report-format", "json", "--report-path", str(report)],
        cwd=cwd, capture_output=True, text=True, timeout=300,
    ).returncode


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.mark.skipif(_gitleaks_bin() is None, reason="no gitleaks binary on PATH")
def test_integration_synthetic_secret_detected_including_tests_tree(tmp_path: Path) -> None:
    """A real-shaped secret must be detected — even inside tests/, the exact
    blind spot the retired blanket pattern created."""
    bin_path = _gitleaks_bin()
    repo = tmp_path / "fixture-repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "sentinel-selftest@example.invalid")
    _git(repo, "config", "user.name", "sentinel-selftest")
    secret = assembled_secret()
    (repo / "tests").mkdir()
    (repo / "tests" / "test_api.py").write_text(
        'api_key = "%s"  # wired in test setup\n' % secret
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "fixture: synthetic secret in tests tree")

    report = tmp_path / "report.json"
    rc = _run_gitleaks(bin_path, repo, report)
    assert rc == 1, f"gitleaks must exit 1 on a synthetic secret (got {rc})"
    assert report.exists(), "no report written"

    import json

    findings = json.loads(report.read_text())
    assert findings, "secret inside tests/ was NOT detected — blanket exemption regression"
    assert any(f.get("RuleID") in ("generic-api-key", "generic-api-key-unquoted")
               for f in findings)


@pytest.mark.skipif(_gitleaks_bin() is None, reason="no gitleaks binary on PATH")
def test_integration_clean_tree_passes(tmp_path: Path) -> None:
    bin_path = _gitleaks_bin()
    repo = tmp_path / "clean-repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "sentinel-selftest@example.invalid")
    _git(repo, "config", "user.name", "sentinel-selftest")
    (repo / "app.py").write_text(
        "def main():\n"
        "    token = _latest_switch_token  # counter, not a secret\n"
        "    api_key = os.environ['API_KEY']  # env reference\n"
        "    return token\n"
    )
    (repo / "README.md").write_text("# fixture\nDocs may mention tokens and keys in prose.\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "fixture: clean tree")

    report = tmp_path / "clean-report.json"
    rc = _run_gitleaks(bin_path, repo, report)
    assert rc == 0, (
        f"clean fixture tree flagged (rc={rc}); report: "
        f"{report.read_text() if report.exists() else 'none'}"
    )


# --------------------------------------------------------------------------
# Cycle-5 rm-037 reopen: allowlist escape regression (path + value)
# --------------------------------------------------------------------------


def _allowlist_regexes(cfg: dict) -> list[str]:
    return list(cfg.get("allowlist", {}).get("regexes", []))


def test_fixture_path_allowlist_is_directory_anchored_only() -> None:
    """The fixture exemption covers DIRECTORIES named fixtures/fixture only.

    The retired `(?i)tests?/.*fixtures?` matched any tests/ path containing
    "fixture" — including tests/unit/test_fixture_loader.py, where a planted
    ghp_-shaped token produced zero findings under the fleet config (cycle-5
    assess, live-binary A/B on gitleaks 8.28.0 and 8.30.1).
    """
    cfg = load_config()
    patterns = [re.compile(p) for p in _allowlist_paths(cfg)]
    for exempt in (
        "tests/fixtures/dummy_home.py",
        "test/fixture/data.env",
        "fixtures/secrets.txt",
    ):
        assert any(p.search(exempt) for p in patterns), (
            f"{exempt} must stay exempt — fixture-directory convention"
        )
    for scanned in (
        "tests/unit/test_fixture_loader.py",
        "tests/test_fixtures.py",
        "src/test_fixture_loader.py",
    ):
        assert not any(p.search(scanned) for p in patterns), (
            f"{scanned} must NOT be path-exempt — filename-shaped escape"
        )


def test_value_suppression_is_shape_anchored() -> None:
    """Value allowlist entries match placeholder SHAPES, not substrings."""
    cfg = load_config()
    forms = _allowlist_regexes(cfg)
    assert "xxx+" not in forms, "unanchored xxx+ suppression must stay retired"
    assert r"\.\.\." not in forms, "bare ... suppression must stay retired"
    compiled = [re.compile(r) for r in forms]
    # placeholders stay exempt
    assert any(rx.search("xxxxx") for rx in compiled), "all-x placeholder must stay exempt"
    assert any(rx.search("8fda2...07") for rx in compiled), "redaction stub must stay exempt"
    # values merely CONTAINING the markers are findings (proven miss class)
    xxx_bearing = "q8Kw2" + "x" * 3 + "Xp7Qv5Nt8Lb3"
    assert not any(rx.search(xxx_bearing) for rx in compiled), (
        "xxx-bearing value must not be suppressed"
    )
    assert not any(rx.search("notredacted_at_all") for rx in compiled)


@pytest.mark.skipif(_gitleaks_bin() is None, reason="no gitleaks binary on PATH")
def test_integration_planted_token_in_fixture_named_test_file_detected(tmp_path: Path) -> None:
    """A planted ghp_-shaped token in tests/unit/test_fixture_loader.py IS
    detected — the exact escape the retired path allowlist created."""
    bin_path = _gitleaks_bin()
    repo = tmp_path / "escape-repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "sentinel-selftest@example.invalid")
    _git(repo, "config", "user.name", "sentinel-selftest")
    token = "ghp_" + "Zr4k9Wm2" + "Xp7Qv5Nt" + "8Lb39cQw" + "1Er4Ty6Ui8OpAsDfGh"
    (repo / "tests" / "unit").mkdir(parents=True)
    (repo / "tests" / "unit" / "test_fixture_loader.py").write_text(
        'TOKEN = "%s"  # fixture loader auth\n' % token
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "fixture: planted token in fixture-named test file")

    report = tmp_path / "report.json"
    rc = _run_gitleaks(bin_path, repo, report)
    assert rc == 1, (
        "planted token inside a fixture-NAMED test file went undetected — "
        "path-allowlist escape regression (rm-037)"
    )
    import json

    findings = json.loads(report.read_text())
    assert findings, "rc=1 but empty report"


@pytest.mark.skipif(_gitleaks_bin() is None, reason="no gitleaks binary on PATH")
def test_integration_fixture_directory_still_exempt(tmp_path: Path) -> None:
    """The same token inside a real fixture DIRECTORY stays exempt."""
    bin_path = _gitleaks_bin()
    repo = tmp_path / "fixture-dir-repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "sentinel-selftest@example.invalid")
    _git(repo, "config", "user.name", "sentinel-selftest")
    token = "ghp_" + "Zr4k9Wm2" + "Xp7Qv5Nt" + "8Lb39cQw" + "1Er4Ty6Ui8OpAsDfGh"
    (repo / "tests" / "fixtures").mkdir(parents=True)
    (repo / "tests" / "fixtures" / "dummy_home.py").write_text(
        'TOKEN = "%s"  # dummy secret home\n' % token
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "fixture: dummy secret home")

    report = tmp_path / "report.json"
    rc = _run_gitleaks(bin_path, repo, report)
    assert rc == 0, "fixture-directory convention regressed to findings"


@pytest.mark.skipif(_gitleaks_bin() is None, reason="no gitleaks binary on PATH")
def test_integration_xxx_bearing_secret_value_detected(tmp_path: Path) -> None:
    """A high-entropy secret whose VALUE contains xxx is a finding — the
    retired `xxx+` entry suppressed exactly this shape (cycle-5 assess)."""
    bin_path = _gitleaks_bin()
    repo = tmp_path / "xxx-value-repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "sentinel-selftest@example.invalid")
    _git(repo, "config", "user.name", "sentinel-selftest")
    secret = "q8Kw2" + "x" * 3 + "Xp7Qv5Nt8Lb3"
    (repo / "cfg.yml").write_text('api_key: "%s"\n' % secret)
    # placeholder control in the same repo: all-x value must stay clean
    (repo / "template.env").write_text('API_KEY="xxxxxxxxxxxxxxxx"\n')
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "fixture: xxx-bearing value + placeholder")

    report = tmp_path / "report.json"
    rc = _run_gitleaks(bin_path, repo, report)
    assert rc == 1, "xxx-bearing secret value went undetected — value suppression escape"
    import json

    findings = json.loads(report.read_text())
    assert findings, "rc=1 but empty report"


# --------------------------------------------------------------------------
# Cycle-6 batch F2 (rm-037 reopen): full-path anchoring of every paths[]
# exemption — no directory-name-suffix escapes
# --------------------------------------------------------------------------


def test_every_allowlist_path_is_fully_anchored() -> None:
    """gitleaks matches paths[] against the FULL path with an unanchored
    regex, so a bare `dist/` exempted any directory whose name merely ends
    in dist (cycle-6 live A/B on 8.30.1: identical api_key file flagged in
    src/, silent in xdist/). Every entry must pin a path BOUNDARY at its
    start — (^|/) directly or behind a leading (?i) flag — so exemptions
    scope to real directory/filename components only."""
    paths = _allowlist_paths(load_config())
    assert paths, "allowlist.paths vanished"
    for entry in paths:
        assert re.match(r"^(?:\(\?i\))?\(\^\|/\)", entry), (
            f"unanchored allowlist path {entry!r}: full-path matching would "
            "also exempt name-suffixed paths (xdist/, mynode_modules/)"
        )


@pytest.mark.skipif(_gitleaks_bin() is None, reason="no gitleaks binary on PATH")
def test_integration_dist_named_directory_is_scanned(tmp_path: Path) -> None:
    """The cycle-6 A/B as a permanent regression lock: the identical secret
    file is detected in src/ (control) AND in xdist/ (name merely ENDING in
    dist — the pre-F2 escape), while the genuine vendored web/dist/ build
    output stays exempt."""
    bin_path = _gitleaks_bin()
    repo = tmp_path / "ab-repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "sentinel-selftest@example.invalid")
    _git(repo, "config", "user.name", "sentinel-selftest")
    secret = assembled_secret()
    for rel in ("src/keep.py", "xdist/keep.py", "web/dist/keep.py"):
        target = repo / rel
        target.parent.mkdir(parents=True)
        target.write_text('api_key = "%s"\n' % secret)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "fixture: identical secret in src/, xdist/, web/dist/")

    report = tmp_path / "ab-report.json"
    rc = _run_gitleaks(bin_path, repo, report)
    assert rc == 1, f"expected findings (rc={rc})"

    import json

    findings = json.loads(report.read_text())
    hit = {f.get("File", "") for f in findings}
    assert any("xdist/" in f for f in hit), (
        f"xdist/ escape regressed (unanchored dist/ allowlist?): {sorted(hit)}"
    )
    assert any("src/" in f for f in hit), "control location not flagged"
    assert not any("web/dist/" in f for f in hit), (
        "vendored web/dist/ must stay exempt — anchoring over-tightened"
    )
