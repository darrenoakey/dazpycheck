# dazpycheck: ignore-banned-words
import os
import shutil
import unittest

from dazpycheck.main import (
    check_banned_words_in_file,
    compile_file,
    main,
    run_test_on_file,
)


class TestDazpycheck(unittest.TestCase):
    def setUp(self):
        self.output_dir = "output"
        self.test_project_dir = os.path.join(self.output_dir, "test_project")
        os.makedirs(self.test_project_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.output_dir)

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

    def test_run_test_on_file_with_low_coverage(self):
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
        success, message = run_test_on_file(test_file)
        self.assertFalse(success)
        self.assertIn("less than 50%", message)

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


if __name__ == "__main__":
    unittest.main()
