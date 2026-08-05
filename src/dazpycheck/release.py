# dazpycheck: ignore-banned-words
# dazpycheck: no-test-required
from __future__ import annotations

import glob
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from twine.commands.upload import upload
from twine.settings import Settings

from . import __version__
from .publishing import pypi_token


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    for directory in (root / "dist", root / "build"):
        if directory.exists():
            shutil.rmtree(directory)
    subprocess.run([sys.executable, "-m", "build"], cwd=root, check=True)
    distributions = glob.glob(str(root / "dist" / "*"))
    if not distributions:
        raise RuntimeError("build produced no distribution files")

    upload(
        Settings(username="__token__", password=pypi_token(), non_interactive=True, skip_existing=True),
        distributions,
    )

    with tempfile.TemporaryDirectory(prefix="dazpycheck-pypi-") as download_dir:
        for attempt in range(12):
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "download",
                    "--no-deps",
                    "--dest",
                    download_dir,
                    f"dazpycheck=={__version__}",
                ],
                check=False,
            )
            if result.returncode == 0:
                break
            if attempt == 11:
                raise RuntimeError(f"published {__version__}, but PyPI indexing verification failed")
            time.sleep(5)

    for directory in (root / "dist", root / "build"):
        if directory.exists():
            shutil.rmtree(directory)
    print(f"Published and verified dazpycheck {__version__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
