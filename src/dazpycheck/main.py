import argparse
import os
import subprocess
import sys
from multiprocessing import Pool, cpu_count

from .secret_scan import check_legacy_secret_access
from .test_runner import run_test_on_file

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

    success, message = check_legacy_secret_access(directory)
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
