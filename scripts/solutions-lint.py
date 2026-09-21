#!/usr/bin/env python3
"""solutions-lint — self-healing frontmatter/index lint for docs/solutions/.

fro-bot/.github knowledge-wiki pattern: scheduled lint fixes purely mechanical
findings (missing frontmatter keys, index drift) in place; judgment calls are
reported for an issue. Exit 0 = clean or self-healed; exit 1 = findings needing
judgment. Run from a repo root that has docs/solutions/.
"""
import os
import re
import sys
from datetime import datetime, timezone

REQUIRED_KEYS = ['module', 'date', 'category', 'problem_type', 'symptoms', 'root_cause']
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
JUDGMENT = []  # findings that need a human/agent issue


def lint_file(path: str) -> list[str]:
    """Return list of self-healed actions taken (mutates the file)."""
    with open(path) as fh:
        text = fh.read()

    # split frontmatter
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    if not m:
        JUDGMENT.append(f'{path}: no frontmatter block (needs authoring, cannot self-heal)')
        return []
    fm, body = m.group(1), text[m.end():]
    healed = []

    keys = {ln.split(':', 1)[0].strip() for ln in fm.splitlines() if ':' in ln and not ln.startswith((' ', '-', '\t'))}
    missing = [k for k in REQUIRED_KEYS if k not in keys]
    # category is derivable from the file's directory (mechanical self-heal)
    if 'category' in missing:
        rel = os.path.relpath(path, os.path.join(repo_root_unused := '.', 'docs', 'solutions'))
        cat = os.path.dirname(rel).replace(os.sep, '/')
        if cat and '/' not in cat:
            fm += f'\ncategory: solutions/{cat}'
            missing.remove('category')
            healed.append(f'{path}: added category: solutions/{cat} (derived from directory)')
    if missing:
        JUDGMENT.append(f'{path}: missing frontmatter keys {missing} (content needed — cannot invent)')

    for ln in fm.splitlines():
        dm = re.match(r'^(date):\s*(\S+)$', ln)
        if dm and not DATE_RE.match(dm.group(2)):
            JUDGMENT.append(f'{path}: date "{dm.group(2)}" not YYYY-MM-DD')

    new_text = f'---\n{fm}\n---\n{body}'
    if new_text != text:
        with open(path, 'w') as fh:
            fh.write(new_text)
        healed.append(f'{path}: normalized frontmatter delimiters')
    return healed


def lint_repo(repo: str) -> int:
    root = os.path.join(repo, 'docs', 'solutions')
    if not os.path.isdir(root):
        print(f'{repo}: no docs/solutions/ — skip')
        return 0
    healed: list[str] = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if name.endswith('.md'):
                healed += lint_file(os.path.join(dirpath, name))

    # index drift: every .md should appear in the nearest README/index if one exists
    index_path = os.path.join(root, 'README.md')
    if os.path.isfile(index_path):
        with open(index_path) as fh:
            index = fh.read()
        for dirpath, _dirs, files in os.walk(root):
            for name in files:
                if name.endswith('.md') and name != 'README.md':
                    rel = os.path.relpath(os.path.join(dirpath, name), root)
                    if rel not in index and name not in index:
                        JUDGMENT.append(f'{repo}: {rel} not referenced in docs/solutions/README.md')

    for h in healed:
        print(f'healed: {h}')
    for j in JUDGMENT:
        print(f'JUDGMENT: {j}')
    return 1 if JUDGMENT else 0


if __name__ == '__main__':
    repos = sys.argv[1:] or ['/work/projects/hermes-conductor', '/work/projects/hermes-gpt']
    rc = 0
    for repo in repos:
        rc |= lint_repo(repo)
    sys.exit(rc)
