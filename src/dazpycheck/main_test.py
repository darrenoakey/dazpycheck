# dazpycheck: ignore-banned-words
import os
import shutil
import unittest
from dazpycheck.main import (
    check_banned_words_in_file,
    compile_file,
    run_test_on_file,
    main,
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
            f.write(
                "def my_function():\n    return 1\n\n\ndef another_function():\n    return 2\n"
            )
        with open(test_file, "w") as f:
            f.write(
                "import unittest\nfrom my_module import my_function\n\n\n"
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
            f.write(
                "def my_function():\n    return 1\n\ndef another_function():\n    return 2\n"
            )
        with open(test_file, "w") as f:
            f.write(
                "import unittest\nfrom my_module import my_function\n\n"
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


if __name__ == "__main__":
    unittest.main()
