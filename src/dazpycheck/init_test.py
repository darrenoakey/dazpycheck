import unittest
from dazpycheck import __version__, main, cli


class TestDazpycheckInit(unittest.TestCase):

    def test_version_defined(self):
        """Test that version is properly defined"""
        self.assertIsInstance(__version__, str)
        self.assertGreater(len(__version__), 0)
        # Test semantic versioning format
        parts = __version__.split(".")
        self.assertEqual(len(parts), 3)
        for part in parts:
            self.assertTrue(part.isdigit())

    def test_imports_available(self):
        """Test that all public imports are available"""
        self.assertTrue(callable(main))
        self.assertTrue(callable(cli))

    def test_main_function_exists(self):
        """Test that main function is callable"""
        self.assertTrue(callable(main))

    def test_cli_function_exists(self):
        """Test that cli function is callable"""
        self.assertTrue(callable(cli))


if __name__ == '__main__':
    unittest.main()