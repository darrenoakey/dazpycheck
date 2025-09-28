# dazpycheck: ignore-banned-words
"""
dazpycheck - A tool to check and validate Python code repositories

This tool enforces code quality standards, test coverage, and anti-mocking practices.
"""

from .main import main, cli

__version__ = "0.7.0"
__all__ = ["main", "cli"]
