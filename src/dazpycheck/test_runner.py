# dazpycheck: ignore-banned-words
# dazpycheck: no-test-required
from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

import coverage


def _python_for(test_path: Path) -> str:
    for parent in (test_path.parent, *test_path.parents):
        candidate = parent / ".venv" / "bin" / "python"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return sys.executable


# Per-test hangs are caught by the inner pytest timeout. Both budgets must
# be generous enough for slow real integration tests (xcodebuild, simctl,
# device tools) on a loaded machine, or they manufacture false failures
# unrelated to the code under test. The inner budget stays well under the
# outer file budget so a hung file still dies file-locally first.
TEST_TIMEOUT_SECONDS = 180
FILE_TIMEOUT_SECONDS = 600


def run_test_on_file(file_path: str, check_coverage: bool = True) -> tuple[bool, str]:
    """Run one real test file in an isolated process and enforce direct coverage."""
    test_path = Path(file_path).resolve()
    source_path = Path(str(test_path).replace("_test.py", ".py"))
    if not source_path.exists():
        return False, f"Test file {file_path} exists but corresponding source file {source_path} does not."

    package_root = test_path.parent.parent if (test_path.parent / "__init__.py").exists() else test_path.parent
    python = _python_for(test_path)
    with tempfile.TemporaryDirectory(prefix="dazpycheck-cov-") as temporary_directory:
        data_file = str(Path(temporary_directory) / ".coverage")
        command = [
            python,
            "-m",
            "pytest",
            str(test_path),
            "-q",
            "--tb=short",
            "--disable-warnings",
            "--timeout=" + str(TEST_TIMEOUT_SECONDS),
        ]
        if check_coverage:
            command = [
                python,
                "-m",
                "coverage",
                "run",
                f"--data-file={data_file}",
                f"--include={source_path}",
                "-m",
                "pytest",
                str(test_path),
                "-q",
                "--tb=short",
                "--disable-warnings",
                "--timeout=" + str(TEST_TIMEOUT_SECONDS),
            ]
        process = subprocess.Popen(
            command,
            cwd=package_root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        try:
            output, _ = process.communicate(timeout=FILE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            return False, f"Test timeout in {file_path} (maximum {FILE_TIMEOUT_SECONDS}s exceeded)"
        if process.returncode != 0:
            return False, f"Tests failed in {file_path}:\n{output}"
        if not check_coverage:
            return True, ""

        cov = coverage.Coverage(data_file=data_file, config_file=False)
        cov.load()
        try:
            _, statements, _, missing, _ = cov.analysis2(str(source_path))
        except coverage.misc.NoSource:
            return False, f"Coverage data not available for {source_path}. Module may not have been imported."
        percentage = ((len(statements) - len(missing)) / len(statements) * 100) if statements else 100
        if percentage < 50:
            return (
                False,
                f"Coverage failure: {file_path} only achieved {percentage:.2f}% coverage of {source_path}.\n"
                f"Each test file must achieve at least 50% coverage of its corresponding source file.\n"
                "Coverage from other test files does not count - "
                f"{test_path.name} must directly cover {source_path.name}.",
            )
        return True, ""
