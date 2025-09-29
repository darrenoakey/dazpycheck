import argparse
import os
import subprocess
import sys
import unittest
from multiprocessing import Pool, cpu_count

import coverage

# dazpycheck: ignore-banned-words
BANNED_WORDS = ["mock", "fallback", "simulate", "pretend", "fake", "skip"]
BANNED_WORDS_SPIEL = """
Banned word found. This isn't about specific words - it's about practices. Mocking is always bad.
Fallbacks are bad - if something fails, we want it to fail, not pretend to work. If you need or
want a mock in a test, it suggests the structure of your actual code needs improvement. Look at
your code and see if it can be restructured to separate dependencies so tests can run fast
without mocks. Focus on creating small, testable functions with clear interfaces.
"""


def run_command(command):
    try:
        subprocess.run(command, capture_output=True, text=True, check=True)
        return True, ""
    except subprocess.CalledProcessError as e:
        return False, f"{e.stdout}\n{e.stderr}"


def check_banned_words_in_file(file_path):
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()
            if "dazpycheck: ignore-banned-words" in content:
                return True, ""
            lines = content.splitlines()
            for line_num, line in enumerate(lines, 1):
                for word in BANNED_WORDS:
                    if word in line:
                        return (
                            False,
                            f"{file_path}:{line_num}: Banned word '{word}' found.\n{BANNED_WORDS_SPIEL}",
                        )
    except Exception:
        pass  # Ignore files that can't be read
    return True, ""


def compile_file(file_path):
    return run_command(["python", "-m", "py_compile", file_path])


def run_test_on_file(file_path):
    source_file = file_path.replace("_test.py", ".py")
    if not os.path.exists(source_file):
        return (
            False,
            f"Test file {file_path} exists but corresponding source file {source_file} does not.",
        )

    # Add the directory of the test file to the python path
    test_dir = os.path.dirname(file_path)
    sys.path.insert(0, test_dir)

    # Use relative path for coverage tracking to match how modules are imported
    source_module = os.path.basename(source_file)

    # Suppress coverage warnings by creating coverage with warnings disabled
    import warnings

    warnings.filterwarnings("ignore")
    cov = coverage.Coverage(source=[test_dir], config_file=False)
    cov.start()

    test_failed = False
    test_output = ""

    # Try pytest first - but run it in-process, not as subprocess
    try:
        import io
        from contextlib import redirect_stderr, redirect_stdout

        import pytest

        # Capture all output during test run
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            # Suppress pytest warnings and output for passing tests
            exit_code = pytest.main([file_path, "-q", "--tb=short", "--disable-warnings"])

        pytest_success = exit_code == 0
        if not pytest_success:
            test_failed = True
            test_output = stdout_capture.getvalue() + stderr_capture.getvalue()
    except ImportError:
        pytest_success = False

    if not pytest_success:
        # Try unittest as fallback
        import io
        from contextlib import redirect_stderr, redirect_stdout

        suite = unittest.TestLoader().discover(
            start_dir=os.path.dirname(file_path), pattern=os.path.basename(file_path)
        )

        if not test_failed:  # Only capture if we haven't already captured from pytest
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()

            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                result = unittest.TextTestRunner(failfast=True, stream=io.StringIO()).run(suite)

            if not result.wasSuccessful():
                test_failed = True
                test_output = stdout_capture.getvalue() + stderr_capture.getvalue()
        else:
            # We already have output from pytest failure
            result = unittest.TextTestRunner(failfast=True, stream=io.StringIO()).run(suite)

        if not test_failed and not result.wasSuccessful():
            cov.stop()
            sys.path.pop(0)
            return (
                False,
                f"Tests failed in {file_path} (tried both pytest and unittest)",
            )

    if test_failed:
        cov.stop()
        sys.path.pop(0)
        return (
            False,
            f"Tests failed in {file_path}:\n{test_output}",
        )

    cov.stop()
    cov.save()

    try:
        # Suppress coverage warnings during analysis
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            filename, statements, excluded, missing, formatted = cov.analysis2(source_module)
            total_statements = len(statements)
            executed_statements = total_statements - len(missing)
            coverage_percentage = (executed_statements / total_statements) * 100 if total_statements > 0 else 100
    except coverage.misc.NoSource:
        sys.path.pop(0)
        return (
            False,
            f"Coverage data not available for {source_file}. Module may not have been imported.",
        )

    if coverage_percentage < 50:
        sys.path.pop(0)
        return (
            False,
            f"Coverage for {source_file} is {coverage_percentage:.2f}%, which is less than 50%.",
        )

    # Remove the directory from the python path
    sys.path.pop(0)

    return True, ""


def main(directory, fix, single_thread, full, pattern=None):
    if fix:
        # Run ruff format to fix formatting issues with line length 120
        run_command(["python3", "-m", "ruff", "format", "--line-length=120", directory])
        # Run ruff check with --fix to fix linting issues
        run_command(["python3", "-m", "ruff", "check", "--fix", "--line-length=120", directory])

    py_files = []
    test_files = []
    for root, dirs, files in os.walk(directory):
        # Skip build, dist, and cache directories
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "build", "dist", ".git", ".pytest_cache")]
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                # Apply pattern filter if specified
                if pattern is None or pattern in file:
                    py_files.append(full_path)
            if file.endswith("_test.py"):
                full_path = os.path.join(root, file)
                # Apply pattern filter if specified
                if pattern is None or pattern in file:
                    test_files.append(full_path)

    # Collect all errors by type before reporting
    missing_test_errors = []
    banned_word_errors = []

    for py_file in py_files:
        if not py_file.endswith("_test.py"):
            # Skip setup.py, __init__.py, and build directory
            if (
                py_file.endswith("/setup.py")
                or py_file == "setup.py"
                or py_file.endswith("/__init__.py")
                or "/build/" in py_file
            ):
                continue
            test_file = py_file.replace(".py", "_test.py")
            if not os.path.exists(test_file):
                missing_test_errors.append(f"Missing test file for {py_file}")

        success, message = check_banned_words_in_file(py_file)
        if not success:
            banned_word_errors.append(message)

    # Report all errors by type
    has_errors = False
    if missing_test_errors:
        has_errors = True
        for error in missing_test_errors:
            print(error, file=sys.stderr)
        if not full:
            return 1

    if banned_word_errors:
        has_errors = True
        for error in banned_word_errors:
            print(error, file=sys.stderr)
        if not full:
            return 1

    # Parallelizable jobs
    jobs = []
    jobs.append((run_command, ["python3", "-m", "ruff", "check", "--line-length=120", directory]))
    for py_file in py_files:
        jobs.append((compile_file, py_file))
    for test_file in test_files:
        jobs.append((run_test_on_file, test_file))

    if single_thread:
        for job, *args in jobs:
            success, message = job(*args)
            if not success:
                has_errors = True
                print(message, file=sys.stderr)
                if not full:
                    return 1
    else:
        with Pool(processes=cpu_count()) as pool:
            results = []
            for job_func, *args in jobs:
                result = pool.apply_async(job_func, args)
                results.append(result)
            for result in results:
                success, message = result.get()
                if not success:
                    has_errors = True
                    print(message, file=sys.stderr)
                    if not full:
                        return 1

    return 1 if has_errors else 0


def cli():
    # Import version here to avoid circular import
    from . import __version__

    parser = argparse.ArgumentParser(description="A tool to check and validate a Python code repository.")
    parser.add_argument("--version", action="version", version=f"dazpycheck {__version__}")
    parser.add_argument("--full", action="store_true", help="Run all checks regardless of failures.")
    parser.add_argument(
        "--readonly",
        action="store_true",
        help="Only check for issues, don't modify files.",
    )
    parser.add_argument("--single-thread", action="store_true", help="Run checks sequentially.")
    parser.add_argument(
        "--pattern",
        type=str,
        help="Only check files matching this pattern (e.g., 'llm_codex_cli').",
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="The directory to check (default: current directory).",
    )

    args = parser.parse_args()

    sys.exit(main(args.directory, not args.readonly, args.single_thread, args.full, args.pattern))
