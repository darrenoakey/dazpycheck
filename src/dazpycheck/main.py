import os
import subprocess
import sys
from multiprocessing import Pool, cpu_count
import coverage
import argparse
import unittest

# dazpycheck: ignore-banned-words
BANNED_WORDS = ["mock", "fallback", "simulate", "pretend", "fake"]
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
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            if "dazpycheck: ignore-banned-words" in content:
                return True, ""
            lines = content.splitlines()
            for line_num, line in enumerate(lines, 1):
                for word in BANNED_WORDS:
                    if word in line:
                        return False, f"{file_path}:{line_num}: Banned word '{word}' found.\n{BANNED_WORDS_SPIEL}"
    except Exception:
        pass  # Ignore files that can't be read
    return True, ""


def compile_file(file_path):
    return run_command(['python', '-m', 'py_compile', file_path])


def run_test_on_file(file_path):
    source_file = file_path.replace("_test.py", ".py")
    if not os.path.exists(source_file):
        return False, f"Test file {file_path} exists but corresponding source file {source_file} does not."

    # Add the directory of the test file to the python path
    sys.path.insert(0, os.path.dirname(file_path))

    cov = coverage.Coverage(source=[source_file])
    cov.start()

    # Try pytest first, then fall back to unittest
    pytest_success, pytest_message = run_command(['python', '-m', 'pytest', file_path, '-q', '--tb=no'])

    if not pytest_success:
        # Try unittest as fallback
        suite = unittest.TestLoader().discover(
            start_dir=os.path.dirname(file_path), pattern=os.path.basename(file_path)
        )
        result = unittest.TextTestRunner(failfast=True, stream=open(os.devnull, 'w')).run(suite)
        if not result.wasSuccessful():
            cov.stop()
            sys.path.pop(0)
            return False, f"Tests failed in {file_path} (tried both pytest and unittest)"

    cov.stop()
    cov.save()

    try:
        filename, statements, excluded, missing, formatted = cov.analysis2(source_file)
        total_statements = len(statements)
        executed_statements = total_statements - len(missing)
        coverage_percentage = (executed_statements / total_statements) * 100 if total_statements > 0 else 100
    except coverage.misc.NoSource:
        sys.path.pop(0)
        return False, f"Coverage data not available for {source_file}. Module may not have been imported."

    if coverage_percentage < 50:
        sys.path.pop(0)
        return False, f"Coverage for {source_file} is {coverage_percentage:.2f}%, which is less than 50%."

    # Remove the directory from the python path
    sys.path.pop(0)

    return True, ""


def main(directory, fix, single_thread, full):
    if fix:
        run_command(["python3", "-m", "black", directory])

    py_files = []
    test_files = []
    for root, dirs, files in os.walk(directory):
        # Skip build, dist, and cache directories
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "build", "dist", ".git", ".pytest_cache")]
        for file in files:
            if file.endswith('.py'):
                py_files.append(os.path.join(root, file))
            if file.endswith('_test.py'):
                test_files.append(os.path.join(root, file))

    # Initial scan for missing tests and banned words
    has_errors = False
    for py_file in py_files:
        if not py_file.endswith("_test.py"):
            # Skip setup.py and build directory
            if py_file.endswith("/setup.py") or py_file == "setup.py" or "/build/" in py_file:
                continue
            test_file = py_file.replace(".py", "_test.py")
            if not os.path.exists(test_file):
                has_errors = True
                print(f"Missing test file for {py_file}", file=sys.stderr)
                if not full:
                    return 1

        success, message = check_banned_words_in_file(py_file)
        if not success:
            has_errors = True
            print(message, file=sys.stderr)
            if not full:
                return 1

    # Parallelizable jobs
    jobs = []
    jobs.append((run_command, ["python3", "-m", "flake8", "--max-line-length=120", directory]))
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
            results = pool.starmap(lambda f, *a: f(*a), jobs)
            for success, message in results:
                if not success:
                    has_errors = True
                    print(message, file=sys.stderr)
                    if not full:
                        return 1

    return 1 if has_errors else 0


def cli():
    parser = argparse.ArgumentParser(description="A tool to check and validate a Python code repository.")
    parser.add_argument("--full", action="store_true", help="Run all checks regardless of failures.")
    parser.add_argument("--readonly", action="store_true", help="Only check for issues, don't modify files.")
    parser.add_argument("--single-thread", action="store_true", help="Run checks sequentially.")
    parser.add_argument(
        "directory", nargs="?", default=".", help="The directory to check (default: current directory)."
    )

    args = parser.parse_args()

    sys.exit(main(args.directory, not args.readonly, args.single_thread, args.full))
