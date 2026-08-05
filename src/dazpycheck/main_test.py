# dazpycheck: ignore-banned-words
import os
import shutil
import sys
import unittest

from dazpycheck.main import (
    check_banned_words_in_file,
    check_legacy_secret_access,
    cli,
    compile_file,
    main,
    run_test_on_file,
    should_require_test,
)


class TestDazpycheck(unittest.TestCase):
    def setUp(self):
        self.output_dir = "output"
        self.test_project_dir = os.path.join(self.output_dir, "test_project")
        os.makedirs(self.test_project_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.output_dir)

    def test_cli_version_exits_successfully(self):
        original_argv = sys.argv
        try:
            sys.argv = ["dazpycheck", "--version"]
            with self.assertRaises(SystemExit) as caught:
                cli()
            self.assertEqual(caught.exception.code, 0)
        finally:
            sys.argv = original_argv

    def test_cli_readonly_single_thread_exits_with_real_result(self):
        original_argv = sys.argv
        try:
            sys.argv = [
                "dazpycheck",
                "--readonly",
                "--single-thread",
                "--no-coverage",
                self.test_project_dir,
            ]
            with self.assertRaises(SystemExit) as caught:
                cli()
            self.assertEqual(caught.exception.code, 0)
        finally:
            sys.argv = original_argv

    def test_should_require_test_handles_unreadable_source_path(self):
        self.assertTrue(should_require_test(self.test_project_dir))

    def test_check_banned_words_in_file(self):
        file_path = os.path.join(self.test_project_dir, "bad_file.py")
        with open(file_path, "w") as f:
            f.write("print('This is a mock file.')\n")
        success, message = check_banned_words_in_file(file_path)
        print(f"Success: {success}, Message: {message}")
        self.assertFalse(success)
        self.assertIn("Banned word 'mock' found", message)

    def test_check_banned_words_in_file_ignored(self):
        file_path = os.path.join(self.test_project_dir, "bad_file_ignored.py")
        with open(file_path, "w") as f:
            f.write("# dazpycheck: ignore-banned-words\n")
            f.write("print('This is a mock file.')\n")
        success, message = check_banned_words_in_file(file_path)
        self.assertTrue(success)

    def test_compile_file(self):
        file_path = os.path.join(self.test_project_dir, "good_file.py")
        with open(file_path, "w") as f:
            f.write("print('Hello, world!')\n")
        success, message = compile_file(file_path)
        self.assertTrue(success)

    def test_compile_file_with_error(self):
        file_path = os.path.join(self.test_project_dir, "bad_file.py")
        with open(file_path, "w") as f:
            f.write("print('Hello, world!\n")
        success, message = compile_file(file_path)
        self.assertFalse(success)

    def test_credential_gate_and_test_policy_before_nested_coverage(self):
        self.assertFalse(should_require_test("setup.py"))
        self.assertFalse(should_require_test("pkg/__init__.py"))
        self.assertFalse(should_require_test("project/build/generated.py"))

        marked = os.path.join(self.test_project_dir, "marked.py")
        with open(marked, "w") as source_file:
            source_file.write("# dazpycheck: no-test-required\nvalue = 1\n")
        self.assertFalse(should_require_test(marked))

        forbidden = os.path.join(self.test_project_dir, "secrets.py")
        with open(forbidden, "w") as source_file:
            source_file.write(
                "from keyring.backend import KeyringBackend\n"
                "import subprocess\n"
                "subprocess.Popen(['/usr/bin/security', 'find-generic-password'])\n"
            )
        success, message = check_legacy_secret_access(self.test_project_dir)
        self.assertFalse(success)
        self.assertIn("retired credential module import", message)
        self.assertIn("retired macOS security command invocation", message)

    def test_a_main_single_thread_without_nested_test_coverage(self):
        source = os.path.join(self.test_project_dir, "standalone.py")
        with open(source, "w") as source_file:
            source_file.write("# dazpycheck: no-test-required\nvalue = 1\n")
        result = main(
            self.test_project_dir,
            False,
            True,
            False,
            check_coverage=False,
        )
        self.assertEqual(result, 0)

    def test_a_main_reports_each_preflight_failure(self):
        missing_test_source = os.path.join(self.test_project_dir, "missing_test.py")
        with open(missing_test_source, "w") as source_file:
            source_file.write("value = 1\n")
        self.assertEqual(main(self.test_project_dir, False, True, False), 1)

        shutil.rmtree(self.test_project_dir)
        os.makedirs(self.test_project_dir)
        banned_source = os.path.join(self.test_project_dir, "banned.py")
        banned_test = os.path.join(self.test_project_dir, "banned_test.py")
        with open(banned_source, "w") as source_file:
            source_file.write("value = 'mock'\n")
        with open(banned_test, "w") as test_file:
            test_file.write("# dazpycheck: ignore-banned-words\n")
        self.assertEqual(main(self.test_project_dir, False, True, False), 1)

        shutil.rmtree(self.test_project_dir)
        os.makedirs(self.test_project_dir)
        credential_source = os.path.join(self.test_project_dir, "credential.py")
        credential_test = os.path.join(self.test_project_dir, "credential_test.py")
        with open(credential_source, "w") as source_file:
            source_file.write("import keyring\n")
        with open(credential_test, "w") as test_file:
            test_file.write("# dazpycheck: ignore-banned-words\n")
        self.assertEqual(main(self.test_project_dir, False, True, False), 1)

    def test_run_test_on_file_with_low_coverage(self):
        source_file = os.path.join(self.test_project_dir, "my_module.py")
        test_file = os.path.join(self.test_project_dir, "my_module_test.py")
        with open(source_file, "w") as f:
            f.write(
                "def my_function():\n    return 1\n\n"
                "def another_function(value):\n    if value:\n        return 2\n    return 0\n\n"
                "def third_function(value):\n    if value:\n        return 3\n    return 0\n\n"
                "def fourth_function(value):\n    if value:\n        return 4\n    return 0\n\n"
                "def fifth_function(value):\n    if value:\n        return 5\n    return 0\n"
            )
        with open(test_file, "w") as f:
            f.write(
                "import unittest\n\nfrom my_module import my_function\n\n"
                "class MyTest(unittest.TestCase):\n    def test_my_function(self):\n"
                "        self.assertEqual(my_function(), 1)\n"
            )
        success, message = run_test_on_file(test_file)
        self.assertFalse(success)
        self.assertIn("Coverage failure", message)
        self.assertIn("must directly cover", message)

    def test_integration_main(self):
        # This is an integration test that runs the main function
        # with a project that has multiple issues.
        source_file = os.path.join(self.test_project_dir, "my_module.py")
        test_file = os.path.join(self.test_project_dir, "my_module_test.py")
        with open(source_file, "w") as f:
            f.write("def my_function():\n    return 1\n\n\ndef another_function():\n    return 2\n")
        with open(test_file, "w") as f:
            f.write(
                "import unittest\n\nfrom my_module import my_function\n\n"
                "class MyTest(unittest.TestCase):\n    def test_my_function(self):\n"
                "        self.assertEqual(my_function(), 1)\n"
            )
        with open(os.path.join(self.test_project_dir, "bad_file.py"), "w") as f:
            f.write("print('This is a mock file.')\n")

        # Fail fast should stop after the first error
        result = main(self.test_project_dir, False, True, False)
        self.assertEqual(result, 1)

        # Full run should report all errors
        result = main(self.test_project_dir, False, True, True)
        self.assertEqual(result, 1)

    def test_check_banned_words_unreadable_file(self):
        # Test exception handling in check_banned_words_in_file
        success, message = check_banned_words_in_file("/nonexistent/path/file.py")
        self.assertTrue(success)
        self.assertEqual(message, "")

    def test_run_test_on_file_missing_source(self):
        # Test when test file exists but source doesn't
        test_file = os.path.join(self.test_project_dir, "orphan_test.py")
        with open(test_file, "w") as f:
            f.write("import unittest\n")
        success, message = run_test_on_file(test_file)
        self.assertFalse(success)
        self.assertIn("corresponding source file", message)

    def test_run_test_on_file_with_package(self):
        # Test package structure with __init__.py
        pkg_dir = os.path.join(self.test_project_dir, "mypkg")
        os.makedirs(pkg_dir)
        with open(os.path.join(pkg_dir, "__init__.py"), "w") as f:
            f.write("")
        source_file = os.path.join(pkg_dir, "calculator.py")
        test_file = os.path.join(pkg_dir, "calculator_test.py")
        with open(source_file, "w") as f:
            f.write("def add(a, b):\n    return a + b\n")
        with open(test_file, "w") as f:
            f.write(
                "import unittest\n\nfrom mypkg.calculator import add\n\n"
                "class TestCalc(unittest.TestCase):\n    def test_add(self):\n"
                "        self.assertEqual(add(2, 3), 5)\n"
            )
        success, message = run_test_on_file(test_file)
        self.assertTrue(success)

    def test_run_test_on_file_test_failure(self):
        # Test when the test itself fails
        source_file = os.path.join(self.test_project_dir, "failing_module.py")
        test_file = os.path.join(self.test_project_dir, "failing_module_test.py")
        with open(source_file, "w") as f:
            f.write("def broken():\n    return 42\n")
        with open(test_file, "w") as f:
            f.write(
                "import unittest\n\nfrom failing_module import broken\n\n"
                "class TestBroken(unittest.TestCase):\n    def test_broken(self):\n"
                "        self.assertEqual(broken(), 99)\n"
            )
        success, message = run_test_on_file(test_file)
        self.assertFalse(success)
        self.assertIn("Tests failed", message)

    def test_main_with_fix_flag(self):
        # Test main with fix=True (runs ruff)
        source_file = os.path.join(self.test_project_dir, "fixable.py")
        test_file = os.path.join(self.test_project_dir, "fixable_test.py")
        with open(source_file, "w") as f:
            f.write("def func():\n    return 1\n")
        with open(test_file, "w") as f:
            f.write(
                "import unittest\n\nfrom fixable import func\n\n"
                "class T(unittest.TestCase):\n    def test_func(self):\n"
                "        self.assertEqual(func(), 1)\n"
            )
        result = main(self.test_project_dir, True, True, False)
        self.assertEqual(result, 0)

    def test_main_no_errors(self):
        # Test main with a clean project (no errors)
        source_file = os.path.join(self.test_project_dir, "clean.py")
        test_file = os.path.join(self.test_project_dir, "clean_test.py")
        with open(source_file, "w") as f:
            f.write("def func():\n    return 1\n")
        with open(test_file, "w") as f:
            f.write(
                "import unittest\n\nfrom clean import func\n\n"
                "class T(unittest.TestCase):\n    def test_func(self):\n"
                "        self.assertEqual(func(), 1)\n"
            )
        result = main(self.test_project_dir, True, True, False)
        self.assertEqual(result, 0)

    def test_main_with_pattern_filter(self):
        # Test main with pattern filtering
        source_file = os.path.join(self.test_project_dir, "specific.py")
        test_file = os.path.join(self.test_project_dir, "specific_test.py")
        with open(source_file, "w") as f:
            f.write("def func():\n    return 1\n")
        with open(test_file, "w") as f:
            f.write(
                "import unittest\n\nfrom specific import func\n\n"
                "class T(unittest.TestCase):\n    def test_func(self):\n"
                "        self.assertEqual(func(), 1)\n"
            )
        # Create another file that shouldn't be tested
        with open(os.path.join(self.test_project_dir, "other.py"), "w") as f:
            f.write("def other():\n    return 2\n")
        result = main(self.test_project_dir, True, True, False, pattern="specific")
        self.assertEqual(result, 0)

    def test_venv_excluded_by_default(self):
        venv_dir = os.path.join(self.test_project_dir, ".venv", "lib")
        os.makedirs(venv_dir)
        with open(os.path.join(venv_dir, "something.py"), "w") as f:
            f.write("x = 1\n")
        # Create a valid source+test so main doesn't fail for other reasons
        source_file = os.path.join(self.test_project_dir, "ok.py")
        test_file = os.path.join(self.test_project_dir, "ok_test.py")
        with open(source_file, "w") as f:
            f.write("def ok():\n    return 1\n")
        with open(test_file, "w") as f:
            f.write(
                "import unittest\n\nfrom ok import ok\n\n"
                "class T(unittest.TestCase):\n    def test_ok(self):\n"
                "        self.assertEqual(ok(), 1)\n"
            )
        result = main(self.test_project_dir, True, True, False)
        self.assertEqual(result, 0)

    def test_custom_exclude_dir(self):
        custom_dir = os.path.join(self.test_project_dir, "generated")
        os.makedirs(custom_dir)
        # File in generated/ has no test — would fail without exclude
        with open(os.path.join(custom_dir, "auto.py"), "w") as f:
            f.write("x = 1\n")
        # Create a valid source+test so main doesn't fail for other reasons
        source_file = os.path.join(self.test_project_dir, "ok2.py")
        test_file = os.path.join(self.test_project_dir, "ok2_test.py")
        with open(source_file, "w") as f:
            f.write("def ok2():\n    return 2\n")
        with open(test_file, "w") as f:
            f.write(
                "import unittest\n\nfrom ok2 import ok2\n\n"
                "class T(unittest.TestCase):\n    def test_ok2(self):\n"
                "        self.assertEqual(ok2(), 2)\n"
            )
        result = main(self.test_project_dir, True, True, False, extra_excludes=["generated"])
        self.assertEqual(result, 0)

    def test_no_test_required_marker(self):
        # File with marker should not need a test file
        source_file = os.path.join(self.test_project_dir, "no_test_needed.py")
        with open(source_file, "w") as f:
            f.write("# dazpycheck: no-test-required\ndef helper():\n    return 1\n")
        # Create a valid source+test so main doesn't fail for other reasons
        ok_source = os.path.join(self.test_project_dir, "ok3.py")
        ok_test = os.path.join(self.test_project_dir, "ok3_test.py")
        with open(ok_source, "w") as f:
            f.write("def ok3():\n    return 3\n")
        with open(ok_test, "w") as f:
            f.write(
                "import unittest\n\nfrom ok3 import ok3\n\n"
                "class T(unittest.TestCase):\n    def test_ok3(self):\n"
                "        self.assertEqual(ok3(), 3)\n"
            )
        result = main(self.test_project_dir, True, True, False)
        self.assertEqual(result, 0)

    def test_no_test_required_marker_must_be_near_top(self):
        # Marker after line 20 should be ignored — test file still required
        source_file = os.path.join(self.test_project_dir, "late_marker.py")
        with open(source_file, "w") as f:
            lines = ["# line\n"] * 20
            lines.append("# dazpycheck: no-test-required\n")
            lines.append("def func():\n    return 1\n")
            f.writelines(lines)
        result = main(self.test_project_dir, False, True, True)
        self.assertEqual(result, 1)

    def test_no_coverage_flag(self):
        # A test with low coverage should pass with check_coverage=False
        source_file = os.path.join(self.test_project_dir, "low_cov.py")
        test_file = os.path.join(self.test_project_dir, "low_cov_test.py")
        with open(source_file, "w") as f:
            f.write(
                "def a():\n    return 1\n\n\n"
                "def b():\n    x = 2\n    y = 3\n    z = x + y\n    return z\n\n\n"
                "def c():\n    x = 3\n    y = 4\n    z = x + y\n    return z\n\n\n"
                "def d():\n    x = 4\n    y = 5\n    z = x + y\n    return z\n"
            )
        with open(test_file, "w") as f:
            f.write(
                "import unittest\n\nfrom low_cov import a\n\n"
                "class T(unittest.TestCase):\n    def test_a(self):\n"
                "        self.assertEqual(a(), 1)\n"
            )
        # With coverage, should fail
        success, message = run_test_on_file(test_file, check_coverage=True)
        self.assertFalse(success)
        self.assertIn("Coverage failure", message)
        # Without coverage, should pass
        success, message = run_test_on_file(test_file, check_coverage=False)
        self.assertTrue(success)

    def test_should_require_test_function(self):
        # setup.py
        self.assertFalse(should_require_test("some/path/setup.py"))
        self.assertFalse(should_require_test("setup.py"))
        # __init__.py
        self.assertFalse(should_require_test("pkg/__init__.py"))
        # /build/ path
        self.assertFalse(should_require_test("project/build/gen.py"))
        # Normal file
        normal = os.path.join(self.test_project_dir, "normal.py")
        with open(normal, "w") as f:
            f.write("x = 1\n")
        self.assertTrue(should_require_test(normal))
        # File with marker
        marked = os.path.join(self.test_project_dir, "marked.py")
        with open(marked, "w") as f:
            f.write("# dazpycheck: no-test-required\nx = 1\n")
        self.assertFalse(should_require_test(marked))

    def test_a_legacy_secret_access_accepts_daz_secrets(self):
        source = os.path.join(self.test_project_dir, "secrets.py")
        with open(source, "w") as source_file:
            source_file.write("from daz_secrets import Client\nClient().get('service', 'account')\n")
        success, message = check_legacy_secret_access(self.test_project_dir)
        self.assertTrue(success)
        self.assertEqual(message, "")

    def test_a_legacy_secret_access_rejects_retired_module(self):
        source = os.path.join(self.test_project_dir, "secrets.py")
        with open(source, "w") as source_file:
            source_file.write("import keyring\n")
        success, message = check_legacy_secret_access(self.test_project_dir)
        self.assertFalse(success)
        self.assertIn("retired credential module import", message)

    def test_a_legacy_secret_access_rejects_security_command(self):
        source = os.path.join(self.test_project_dir, "secrets.py")
        with open(source, "w") as source_file:
            source_file.write("import subprocess\nsubprocess.run(['/usr/bin/security', 'find-generic-password'])\n")
        success, message = check_legacy_secret_access(self.test_project_dir)
        self.assertFalse(success)
        self.assertIn("retired macOS security command invocation", message)


if __name__ == "__main__":
    unittest.main()
