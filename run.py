"""Cross-platform pipeline runner (works on Windows without ``make``).

Usage::

    python run.py all          # db-up, download, clean, load, analyze, export, export-web, check, test
    python run.py clean        # one step
    python run.py load export  # several steps, in order
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from collections.abc import Callable

from src.settings import PROJECT_ROOT, setup_logging

logger = logging.getLogger("run")


def db_up() -> None:
    """Start the PostgreSQL container if Docker is available."""
    if shutil.which("docker") is None:
        logger.warning("Docker not found: make sure PostgreSQL is reachable (see config.yaml)")
        return
    subprocess.run(["docker", "compose", "up", "-d", "--wait"], cwd=PROJECT_ROOT, check=True)


def download() -> None:
    from src import download as step
    step.run()


def clean() -> None:
    from src import clean as step
    step.run()


def load() -> None:
    from src import load_postgres as step
    step.run()


def analyze() -> None:
    from src import analyze as step
    step.run()


def export() -> None:
    from src import export_gold as step
    step.run()


def export_web() -> None:
    from src import export_web as step
    step.run()


def check() -> None:
    from src import crosscheck as step
    step.run()


def validate_pbi() -> None:
    from src import validate_powerbi as step
    step.run()


def test() -> None:
    subprocess.run([sys.executable, "-m", "pytest"], cwd=PROJECT_ROOT, check=True)


def notebook() -> None:
    """Re-execute the exploration notebook in place (outputs saved in the file)."""
    subprocess.run(
        [
            sys.executable, "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute",
            "--inplace", "--ExecutePreprocessor.timeout=900", "notebooks/01_exploration.ipynb",
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )


STEPS: dict[str, Callable[[], None]] = {
    "db-up": db_up,
    "download": download,
    "clean": clean,
    "load": load,
    "analyze": analyze,
    "export": export,
    "export-web": export_web,
    "check": check,
    "test": test,
    "notebook": notebook,
    "validate-pbi": validate_pbi,
}
PIPELINE = ["db-up", "download", "clean", "load", "analyze", "export", "export-web", "check", "test"]


def main() -> None:
    parser = argparse.ArgumentParser(description="DVF pipeline runner")
    parser.add_argument("steps", nargs="+", choices=[*STEPS, "all"], help="steps to run, in order")
    args = parser.parse_args()
    setup_logging()
    steps = [s for name in args.steps for s in (PIPELINE if name == "all" else [name])]
    for name in steps:
        logger.info("=== %s ===", name)
        STEPS[name]()
    logger.info("Done: %s", ", ".join(steps))


if __name__ == "__main__":
    main()
