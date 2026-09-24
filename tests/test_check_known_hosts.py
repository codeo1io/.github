"""Unit tests for scripts/check_known_hosts.py (rm-003 / rm-001).

Hermetic: real throwaway ssh keys (ed25519/rsa/ecdsa) generated once per
session, known_hosts written to tmp files, meta_fingerprints monkeypatched —
no network, no ~/.ssh reads.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_known_hosts as ckh  # noqa: E402


@pytest.fixture(scope="module")
def keys(tmp_path_factory) -> dict[str, dict]:
    """One throwaway keypair per algorithm; returns type -> {pub_line, fp}."""
    out: dict[str, dict] = {}
    d = tmp_path_factory.mktemp("keys")
    for algo, t in (("ED25519", "ed25519"), ("RSA", "rsa"), ("ECDSA", "ecdsa")):
        kf = d / f"k_{t}"
        subprocess.run(
            ["ssh-keygen", "-q", "-t", t, "-N", "", "-C", f"test-{t}", "-f", str(kf)],
            check=True, capture_output=True,
        )
        pub_line = kf.with_suffix(".pub").read_text().strip()
        lf = subprocess.run(["ssh-keygen", "-lf", str(kf.with_suffix(".pub"))],
                            check=True, capture_output=True, text=True).stdout.split()
        out[algo] = {"pub": pub_line, "fp": lf[1]}  # "SHA256:..."
    return out


def kh_line(host: str, key: dict) -> str:
    ktype, b64 = key["pub"].split()[:2]
    return f"{host} {ktype} {b64}"


def pin(tmp_path, monkeypatch, hosts_lines: list[str]) -> Path:
    f = tmp_path / "known_hosts"
    f.write_text("\n".join(hosts_lines) + "\n")
    monkeypatch.setattr(ckh, "KNOWN_HOSTS", str(f))
    return f


def fake_meta(keys: dict, monkeypatch, algos=("ED25519", "RSA", "ECDSA"), strip_prefix=False):
    meta = {f"SHA256_{a}": keys[a]["fp"] for a in algos}
    if strip_prefix:
        meta = {k: v.removeprefix("SHA256:") for k, v in meta.items()}
    monkeypatch.setattr(ckh, "meta_fingerprints", lambda: meta)


def test_exact_set_ok(tmp_path, monkeypatch, capsys, keys):
    pin(tmp_path, monkeypatch, [kh_line("github.com", keys[a]) for a in keys])
    monkeypatch.setattr(ckh, "HOSTS", ["github.com"])
    fake_meta(keys, monkeypatch, strip_prefix=True)  # meta omits SHA256: prefix
    assert ckh.main() == 0
    out = capsys.readouterr().out
    assert "RESULT: OK" in out
    assert out.count(": OK ") == 3


def test_stale_extra_key_fails(tmp_path, monkeypatch, capsys, keys):
    # THE rm-003 regression: stale duplicate alongside the valid key.
    # Old last-key-wins code printed OK here while ssh accepted the stale pin.
    stale = subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "stale", "-f", str(tmp_path / "stale")],
        check=True, capture_output=True)
    assert stale.returncode == 0
    stale_pub = (tmp_path / "stale.pub").read_text().strip()
    lines = [kh_line("github.com", keys[a]) for a in keys]
    lines.insert(0, "github.com " + " ".join(stale_pub.split()[:2]))
    pin(tmp_path, monkeypatch, lines)
    monkeypatch.setattr(ckh, "HOSTS", ["github.com"])
    fake_meta(keys, monkeypatch)
    assert ckh.main() == 1
    out = capsys.readouterr().out
    assert "STALE/EXTRA" in out and "RESULT: FAIL" in out


def test_mismatch_fails(tmp_path, monkeypatch, capsys, keys):
    # valid ED25519 + wrong (fresh) RSA -> MISMATCH, not OK
    wrong = subprocess.run(
        ["ssh-keygen", "-q", "-t", "rsa", "-N", "", "-C", "mitm", "-f", str(tmp_path / "mitm")],
        check=True, capture_output=True)
    assert wrong.returncode == 0
    wrong_pub = (tmp_path / "mitm.pub").read_text().strip()
    pin(tmp_path, monkeypatch, [
        kh_line("github.com", keys["ED25519"]),
        "github.com " + " ".join(wrong_pub.split()[:2]),
    ])
    monkeypatch.setattr(ckh, "HOSTS", ["github.com"])
    fake_meta(keys, monkeypatch)
    assert ckh.main() == 1
    assert "MISMATCH" in capsys.readouterr().out


def test_missing_algo_fails(tmp_path, monkeypatch, capsys, keys):
    pin(tmp_path, monkeypatch, [kh_line("github.com", keys["ED25519"])])
    monkeypatch.setattr(ckh, "HOSTS", ["github.com"])
    fake_meta(keys, monkeypatch)
    assert ckh.main() == 1
    out = capsys.readouterr().out
    assert "MISSING RSA" in out and "MISSING ECDSA" in out


def test_unpinned_host_fails(tmp_path, monkeypatch, capsys, keys):
    pin(tmp_path, monkeypatch, [kh_line("github.com", keys[a]) for a in keys])
    monkeypatch.setattr(ckh, "HOSTS", ["github.com", "[ssh.github.com]:443"])
    fake_meta(keys, monkeypatch)
    assert ckh.main() == 1
    out = capsys.readouterr().out
    assert "[ssh.github.com]:443: FAIL no pinned keys" in out


def test_port443_host_checked_ok(tmp_path, monkeypatch, capsys, keys):
    lines = [kh_line("github.com", keys[a]) for a in keys]
    lines += [kh_line("[ssh.github.com]:443", keys[a]) for a in keys]
    pin(tmp_path, monkeypatch, lines)
    monkeypatch.setattr(ckh, "HOSTS", ["github.com", "[ssh.github.com]:443"])
    fake_meta(keys, monkeypatch)
    assert ckh.main() == 0
    assert capsys.readouterr().out.count(": OK ") == 6


def test_stale_algorithm_fails(tmp_path, monkeypatch, capsys, keys):
    # pinned ED25519 but meta no longer publishes it (e.g. GitHub drops it)
    pin(tmp_path, monkeypatch, [kh_line("github.com", keys["ED25519"])])
    monkeypatch.setattr(ckh, "HOSTS", ["github.com"])
    fake_meta(keys, monkeypatch, algos=("RSA",))
    assert ckh.main() == 1
    out = capsys.readouterr().out
    assert "STALE ALGORITHM" in out and "MISSING RSA" in out


def test_empty_known_hosts_fails(tmp_path, monkeypatch, capsys, keys):
    pin(tmp_path, monkeypatch, [])
    monkeypatch.setattr(ckh, "HOSTS", ["github.com"])
    fake_meta(keys, monkeypatch)
    assert ckh.main() == 1
    assert "no pinned keys" in capsys.readouterr().out


def test_no_temp_file_leak(tmp_path, monkeypatch, keys):
    # rm-003: old code leaked one /tmp/*.kh per run (delete=False)
    leak_dir = tmp_path / "leak"
    leak_dir.mkdir()
    monkeypatch.setenv("TMPDIR", str(leak_dir))
    pin(tmp_path, monkeypatch, [kh_line("github.com", keys[a]) for a in keys])
    ckh.known_fingerprints("github.com")
    ckh.known_fingerprints("github.com")
    assert list(leak_dir.iterdir()) == []


def test_known_hosts_path_env_override(tmp_path, monkeypatch):
    # Cycle-7 F1f: CHECK_KNOWN_HOSTS must retarget the checker without code
    # edits (parity with CONTROL_PLANE_*/VERIFY_* siblings).
    import importlib

    alt = tmp_path / "kh-env"
    alt.write_text("")
    monkeypatch.setenv("CHECK_KNOWN_HOSTS", str(alt))
    module = importlib.reload(ckh)
    try:
        assert module.KNOWN_HOSTS == str(alt)
    finally:
        monkeypatch.delenv("CHECK_KNOWN_HOSTS")
        importlib.reload(ckh)  # restore the default for later tests
    assert ckh.KNOWN_HOSTS == "/home/agent/.ssh/known_hosts"
