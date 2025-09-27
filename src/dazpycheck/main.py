
import os
import subprocess
import sys
from colorama import Fore, Style, init
from multiprocessing import Pool, cpu_count
import unittest

init(autoreset=True)

BANNED_WORDS = ["mock", "fallback", "simulate", "pretend", "fake"]

def print_error(message):
    print(f"{Fore.RED}{message}{Style.RESET_ALL}", file=sys.stderr)

def print_success(message):
    print(f"{Fore.GREEN}{message}{Style.RESET_ALL}")

def print_info(message):
    print(f"{Fore.CYAN}{message}{Style.RESET_ALL}")

def run_command(command, description):
    print_info(f"Running {description}...")
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print_error(result.stderr)
        print_success(f"{description} passed!")
        return True, ""
    except subprocess.CalledProcessError as e:
        error_message = f"{description} failed.\n{e.stdout}\n{e.stderr}"
        print_error(error_message)
        return False, error_message

def find_banned_words(directory):
    banned_words_found = []
    for root, _, files in os.walk(directory):
        for file in files:
            if ".git" in root.split(os.path.sep):
                continue
            file_path = os.path.join(root, file)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        for word in BANNED_WORDS:
                            if word in line:
                                banned_words_found.append(f"{file_path}:{line_num}: Banned word '{word}' found.")
            except Exception as e:
                print_error(f"Error reading file {file_path}: {e}")
    return banned_words_found

def run_check(check_function, *args):
    result = check_function(*args)
    if isinstance(result, list):
        if result:
            for item in result:
                print_error(item)
            return False
        return True
    return result[0]

def main(directory, fix, single_thread):
    print_info(f"Running dazpycheck in {'fix' if fix else 'readonly'} mode on directory: {directory}")

    if fix:
        run_command(["python3", "-m", "black", directory], "Black formatting")

    checks = [
        (find_banned_words, directory),
        (run_command, ["python3", "-m", "flake8", directory], "Flake8 linting"),
        (run_command, ["python3", "-m", "pyright", directory], "Pyright type check"),
        (py_compile_check, directory),
    ]

    results = []
    if single_thread:
        for check, *args in checks:
            results.append(run_check(check, *args))
    else:
        with Pool(processes=cpu_count()) as pool:
            results = pool.starmap(run_check, checks)

    if all(results):
        print_success("\nAll checks passed!")
        return 0
    else:
        print_error("\nSome checks failed.")
        return 1

def py_compile_check(directory):
    print_info("Running py_compile check...")
    compiled_successfully = True
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    subprocess.run(['python', '-m', 'py_compile', file_path], check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as e:
                    print_error(f"Failed to compile {file_path}")
                    print_error(e.stdout)
                    print_error(e.stderr)
                    compiled_successfully = False
    if compiled_successfully:
        print_success("All python files compiled successfully.")
        return True, ""
    else:
        return False, "Failed to compile some python files."

def run_tests(directory):
    print_info(f"Running tests in {directory}...")
    test_files = []
    for root, _, files in os.walk("src"):
        for file in files:
            if file.endswith("_test.py") or file.startswith("test_"):
                test_files.append(os.path.join(root, file))

    if not test_files:
        print_info("No tests found.")
        return 0

    all_tests_passed = True
    for test_file in test_files:
        print_info(f"Running test: {test_file}")
        with open(test_file, "r") as f:
            content = f.read()
            if "import pytest" in content:
                result = subprocess.run(["python3", "-m", "pytest", test_file], capture_output=True, text=True)
                if result.returncode != 0:
                    print_error(f"Pytest failed for {test_file}")
                    print_error(result.stdout)
                    print_error(result.stderr)
                    all_tests_passed = False
            elif "import unittest" in content:
                result = subprocess.run(["python3", "-m", "unittest", test_file], capture_output=True, text=True)
                if result.returncode != 0:
                    print_error(f"Unittest failed for {test_file}")
                    print_error(result.stdout)
                    print_error(result.stderr)
                    all_tests_passed = False
            else:
                print_info(f"Skipping {test_file} as it does not seem to be a pytest or unittest file.")

    if all_tests_passed:
        print_success("\nAll tests passed!")
        return 0
    else:
        print_error("\nSome tests failed.")
        return 1
