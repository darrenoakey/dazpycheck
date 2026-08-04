import argparse
import os
import subprocess
import sys
import unittest
from multiprocessing import Pool, cpu_count

import coverage

ALWAYS_EXCLUDE = {
    "__pycache__",
    "build",
    "dist",
    ".git",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
    ".env",
    "node_modules",
    ".tox",
    ".nox",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
    ".coverage",
    "eggs",
    ".eggs",
    "site-packages",
}

# dazpycheck: ignore-banned-words
BANNED_WORDS = ["mock", "fallback", "simulate", "pretend", "fake", "skip", "sleep", "dummy"]
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


def should_require_test(file_path):
    if file_path.endswith("/setup.py") or file_path == "setup.py":
        return False
    if file_path.endswith("/__init__.py"):
        return False
    if "/build/" in file_path:
        return False
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i >= 20:
                    break
                if "dazpycheck: no-test-required" in line:
                    return False
    except Exception:
        pass
    return True


def compile_file(file_path):
    return run_command(["python", "-m", "py_compile", file_path])


def run_test_on_file(file_path, check_coverage=True):
    import tempfile

    source_file = file_path.replace("_test.py", ".py")
    if not os.path.exists(source_file):
        return (
            False,
            f"Test file {file_path} exists but corresponding source file {source_file} does not.",
        )

    # Add the appropriate directory to python path
    # If there's an __init__.py, this is a package - add parent directory instead
    test_dir = os.path.dirname(file_path)
    init_file = os.path.join(test_dir, "__init__.py")

    if os.path.exists(init_file):
        # This is a package - add parent directory so imports work as "package.module"
        path_to_add = os.path.dirname(test_dir)
    else:
        # Not a package - add the directory itself
        path_to_add = test_dir

    # Use a thread-safe approach: check if already in path before adding
    path_needs_cleanup = path_to_add not in sys.path
    if path_needs_cleanup:
        sys.path.insert(0, path_to_add)

    cov = None
    coverage_temp_dir = None

    if check_coverage:
        # Use absolute path for coverage tracking to ensure correct file matching
        source_module = os.path.abspath(source_file)

        # Suppress coverage warnings by creating coverage with warnings disabled
        # Create a unique temporary coverage data file for this test run to avoid conflicts
        # Using a unique temp directory ensures SQLite databases don't conflict
        import warnings

        warnings.filterwarnings("ignore")
        coverage_temp_dir = tempfile.mkdtemp(prefix="dazpycheck_cov_")
        coverage_data_file = os.path.join(coverage_temp_dir, ".coverage")

        cov = coverage.Coverage(source=[test_dir], config_file=False, data_file=coverage_data_file)
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
            # Set timeout to 30 seconds per test
            exit_code = pytest.main([file_path, "-q", "--tb=short", "--disable-warnings", "--timeout=30"])

        pytest_success = exit_code == 0
        if not pytest_success:
            test_failed = True
            captured_output = stdout_capture.getvalue() + stderr_capture.getvalue()
            # Check if it's a timeout error and provide clear message
            if "Timeout" in captured_output or "timeout" in captured_output:
                test_output = f"Test timeout in {file_path} (maximum 30s exceeded)\n{captured_output}"
            else:
                test_output = captured_output
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
            if cov:
                cov.stop()
            if coverage_temp_dir:
                try:
                    import shutil

                    shutil.rmtree(coverage_temp_dir, ignore_errors=True)
                except Exception:
                    pass
            if path_needs_cleanup:
                sys.path.remove(path_to_add)
            return (
                False,
                f"Tests failed in {file_path} (tried both pytest and unittest)",
            )

    if test_failed:
        if cov:
            cov.stop()
        if coverage_temp_dir:
            try:
                import shutil

                shutil.rmtree(coverage_temp_dir, ignore_errors=True)
            except Exception:
                pass
        if path_needs_cleanup:
            sys.path.remove(path_to_add)
        return (
            False,
            f"Tests failed in {file_path}:\n{test_output}",
        )

    if not check_coverage:
        if path_needs_cleanup:
            sys.path.remove(path_to_add)
        return True, ""

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
        if coverage_temp_dir:
            try:
                import shutil

                shutil.rmtree(coverage_temp_dir, ignore_errors=True)
            except Exception:
                pass
        if path_needs_cleanup:
            sys.path.remove(path_to_add)
        return (
            False,
            f"Coverage data not available for {source_file}. Module may not have been imported.",
        )
    finally:
        if coverage_temp_dir:
            try:
                import shutil

                shutil.rmtree(coverage_temp_dir, ignore_errors=True)
            except Exception:
                pass

    if coverage_percentage < 50:
        if path_needs_cleanup:
            sys.path.remove(path_to_add)
        test_name = os.path.basename(file_path)
        source_name = os.path.basename(source_file)
        return (
            False,
            f"Coverage failure: {file_path} only achieved {coverage_percentage:.2f}% coverage of {source_file}.\n"
            f"Each test file must achieve at least 50% coverage of its corresponding source file.\n"
            f"Coverage from other test files does not count - {test_name} must directly cover {source_name}.",
        )

    # Remove the directory from the python path only if we added it
    if path_needs_cleanup:
        sys.path.remove(path_to_add)

    return True, ""


def check_venv_keyring_safety(directory):
    """Check that every venv in the repository has the safe keyring backend .pth.

    The securitykeyring backend lives in ~/src/securitykeyring/src and is made
    importable inside each venv via a zz_keyring_safe.pth file in the venv's
    site-packages. This check fails if any venv under the directory is missing
    that file, so keyring cannot silently fall back to a prompt-generating
    backend on macOS.
    """
    if sys.platform != "darwin":
        return True, ""

    errors = []
    venv_names = {".venv", "venv", "env"}

    for root, dirs, _files in os.walk(directory):
        # Enter venv directories but skip other common non-repo trees.
        dirs[:] = [d for d in dirs if d not in ALWAYS_EXCLUDE or d in venv_names]

        if not os.path.exists(os.path.join(root, "pyvenv.cfg")):
            continue

        site_packages_paths = []
        for lib_dir in ("lib", "Lib"):
            lib_path = os.path.join(root, lib_dir)
            if not os.path.isdir(lib_path):
                continue
            try:
                entries = os.listdir(lib_path)
            except OSError:
                continue
            for entry in entries:
                if entry.startswith("python"):
                    sp = os.path.join(lib_path, entry, "site-packages")
                    if os.path.isdir(sp):
                        site_packages_paths.append(sp)

        if not site_packages_paths:
            errors.append(f"{root}: venv has no site-packages directory")
        elif not any(os.path.exists(os.path.join(sp, "zz_keyring_safe.pth")) for sp in site_packages_paths):
            errors.append(f"{root}: venv missing zz_keyring_safe.pth (safe keyring backend not available)")

        # Do not recurse into the venv itself.
        dirs[:] = []

    if errors:
        return False, "\n".join(errors)
    return True, ""


def main(directory, fix, single_thread, full, pattern=None, check_coverage=True, extra_excludes=None):
    if fix:
        # Run ruff format to fix formatting issues with line length 120
        run_command(["python3", "-m", "ruff", "format", "--line-length=120", directory])
        # Run ruff check with --fix to fix linting issues
        run_command(["python3", "-m", "ruff", "check", "--fix", "--line-length=120", directory])

    exclude_dirs = ALWAYS_EXCLUDE | set(extra_excludes or [])

    py_files = []
    test_files = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
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
            if not should_require_test(py_file):
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

    success, message = check_venv_keyring_safety(directory)
    if not success:
        has_errors = True
        print(message, file=sys.stderr)
        if not full:
            return 1

    # Parallelizable jobs
    jobs = []
    jobs.append((run_command, ["python3", "-m", "ruff", "check", "--line-length=120", directory]))
    for py_file in py_files:
        jobs.append((compile_file, py_file))
    for test_file in test_files:
        jobs.append((run_test_on_file, test_file, check_coverage))

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
        "--no-coverage",
        action="store_true",
        help="Skip per-file coverage checks.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Additional directory names to exclude (repeatable).",
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="The directory to check (default: current directory).",
    )

    args = parser.parse_args()

    sys.exit(
        main(
            args.directory,
            not args.readonly,
            args.single_thread,
            args.full,
            args.pattern,
            check_coverage=not args.no_coverage,
            extra_excludes=args.exclude,
        )
    )
