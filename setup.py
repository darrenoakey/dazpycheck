"""
Setup configuration for dazpycheck package.

This setup script configures the package for distribution. The version number
is read from dazpycheck/__init__.py to maintain a single source of truth.
"""

import os
import re
from setuptools import setup


def get_version():
    """Get version from src/dazpycheck/__init__.py"""
    version_file = os.path.join(
        os.path.dirname(__file__), "src", "dazpycheck", "__init__.py"
    )
    with open(version_file, "r", encoding="utf-8") as f:
        version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", f.read(), re.M)
        if version_match:
            return version_match.group(1)
    raise RuntimeError("Unable to find version string")


if __name__ == "__main__":
    setup()
