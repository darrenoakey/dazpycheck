# dazpycheck: The Ultimate Python Code Guardian

![dazpycheck logo](output/logo.png)

**dazpycheck** is a powerful and comprehensive tool for ensuring your Python code is clean, correct, and consistent. It combines multiple code quality tools into a single, easy-to-use command-line interface, and even helps you enforce your own coding standards.

## Features

*   **All-in-One Checking:** dazpycheck integrates `black` for formatting, `flake8` for linting, `pyright` for type checking, and `py_compile` for compilation, giving you a complete picture of your code's health.
*   **Automated Fixing:** By default, `dazpycheck` will automatically fix formatting issues. Use the `--readonly` flag to see what would be changed without modifying any files.
*   **Banned Words Enforcement:** Define a list of "banned words" to enforce your own coding standards. `dazpycheck` will scan your entire repository and flag any occurrences of these words.
*   **Parallel Execution:** `dazpycheck` runs all readonly checks in parallel, making it fast and efficient, even on large codebases.
*   **Integrated Test Runner:** Run all your `unittest` and `pytest` tests with a single command: `./run test`.

## How it Works

`dazpycheck` is designed to be simple and intuitive. The main entry point is the `run` script, which provides two main commands: `check` and `test`.

### Checking Your Code

To check your code, simply run:

```bash
./run check
```

This will run all the checks in parallel and automatically fix any formatting issues. If you want to see what would be changed without modifying any files, use the `--readonly` flag:

```bash
./run check --readonly
```

![Parallel Checks](output/parallel_checks.png)

### Banned Words

`dazpycheck` can help you enforce your own coding standards by searching for a list of "banned words". You can configure this list in the `main.py` file. If any of these words are found, `dazpycheck` will report them and fail the check.

![Banned Words](output/banned_words.png)

### Running Tests

To run all your tests, use the `test` command:

```bash
./run test
```

`dazpycheck` will automatically discover and run all your `unittest` and `pytest` tests.

## Installation

To get started with `dazpycheck`, simply clone the repository and install the dependencies:

```bash
pip install -r requirements.txt
```

Then, you can run the tool using the `run` script:

```bash
./run check
```

We hope you find `dazpycheck` to be a valuable addition to your development workflow!