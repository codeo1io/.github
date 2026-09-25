"""Behavioral lock for solutions-lint.py (review P3: no automated coverage).

The historical bug: relpath for the category self-heal was anchored to the
caller's CWD ('./docs/solutions'), so running the lint from any directory
other than the repo root produced a '/-laden derived category, the heal
refused to fire, and the file went to JUDGMENT. These tests run the script
as a subprocess from a foreign CWD — the old code fails them, the
root-threaded code passes. (rm-032 acceptance: 'bash solutions-lint from a
different CWD'.)
"""
import os
import subprocess
import sys
import textwrap

SCRIPT = os.path.join(os.path.dirname(__file__), os.pardir,
                      "scripts", "solutions-lint.py")

VALID_FM = """\
---
module: demo
date: 2026-09-21
problem_type: incident
symptoms: thing broke
root_cause: widget misaligned
---
Body text.
"""


def _run_lint(repo, cwd):
    return subprocess.run(
        [sys.executable, os.path.abspath(SCRIPT), str(repo)],
        capture_output=True, text=True, cwd=str(cwd),
    )


def test_category_selfheal_fires_from_foreign_cwd(tmp_path):
    # All required keys except category — derivable from the directory.
    repo = tmp_path / "fleetrepo"
    sol = repo / "docs" / "solutions" / "netcat"
    sol.mkdir(parents=True)
    entry = sol / "relay-probe.md"
    entry.write_text(VALID_FM, encoding="utf-8")

    elsewhere = tmp_path / "elsewhere"  # NOT the repo root, not a parent of it
    elsewhere.mkdir()

    r = _run_lint(repo, elsewhere)

    assert r.returncode == 0, f"rc={r.returncode} stdout={r.stdout} stderr={r.stderr}"
    assert "healed:" in r.stdout and "category: solutions/netcat" in r.stdout
    assert "JUDGMENT" not in r.stdout
    # the file itself gained the derived key
    assert "category: solutions/netcat" in entry.read_text(encoding="utf-8")


def test_judgment_findings_exit_nonzero(tmp_path):
    # root_cause cannot be invented by the linter — must go to JUDGMENT, rc=1.
    repo = tmp_path / "fleetrepo2"
    sol = repo / "docs" / "solutions" / "netcat"
    sol.mkdir(parents=True)
    (sol / "needs-human.md").write_text(
        VALID_FM.replace("root_cause: widget misaligned\n", ""),
        encoding="utf-8")

    r = _run_lint(repo, tmp_path)

    assert r.returncode == 1
    assert "JUDGMENT" in r.stdout and "root_cause" in r.stdout


def test_judgment_scoped_per_repo_no_cross_contamination(tmp_path):
    """cycle-8 rm-022: JUDGMENT used to be module-level — a multi-repo run
    re-printed every earlier repo's findings during each later pass."""
    repos = []
    for name in ("fleetrepo-a", "fleetrepo-b"):
        repo = tmp_path / name
        sol = repo / "docs" / "solutions" / "netcat"
        sol.mkdir(parents=True)
        (sol / "needs-human.md").write_text(
            VALID_FM.replace("root_cause: widget misaligned\n", ""),
            encoding="utf-8")
        repos.append(repo)

    # ONE process, BOTH repos — the shape the engine's cron loop uses
    r = subprocess.run(
        [sys.executable, os.path.abspath(SCRIPT), *[str(p) for p in repos]],
        capture_output=True, text=True, cwd=str(tmp_path),
    )

    assert r.returncode == 1
    judgments = [ln for ln in r.stdout.splitlines() if ln.startswith("JUDGMENT:")]
    # exactly one finding line per repo — the module-level accumulator
    # re-printed fleetrepo-a's finding during fleetrepo-b's pass
    assert len(judgments) == 2, (
        f"expected exactly one JUDGMENT per repo, got {len(judgments)}:\n{r.stdout}"
    )
    assert sum("fleetrepo-a" in ln for ln in judgments) == 1
    assert sum("fleetrepo-b" in ln for ln in judgments) == 1
