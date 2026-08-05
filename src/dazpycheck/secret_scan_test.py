# dazpycheck: ignore-banned-words
from pathlib import Path

from dazpycheck.secret_scan import check_legacy_secret_access


def test_accepts_daz_secrets_and_ignores_non_python_files(tmp_path: Path) -> None:
    (tmp_path / "credential.py").write_text("from daz_secrets import Client\n")
    (tmp_path / "notes.txt").write_text("import keyring\n")
    assert check_legacy_secret_access(str(tmp_path)) == (True, "")


def test_rejects_retired_module_imports(tmp_path: Path) -> None:
    (tmp_path / "credential.py").write_text("from securitykeyring.backend import Backend\nimport keyring\n")
    success, message = check_legacy_secret_access(str(tmp_path))
    assert not success
    assert message.count("retired credential module import") == 2


def test_rejects_macos_security_subprocess_calls(tmp_path: Path) -> None:
    (tmp_path / "credential.py").write_text(
        "import subprocess\nsubprocess.Popen(['/usr/bin/security', 'find-generic-password'])\n"
    )
    success, message = check_legacy_secret_access(str(tmp_path))
    assert not success
    assert "retired macOS security command invocation" in message


def test_ignores_unparseable_python_while_compilation_gate_reports_it(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def broken(:\n")
    assert check_legacy_secret_access(str(tmp_path)) == (True, "")
