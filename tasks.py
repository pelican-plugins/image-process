import os
from pathlib import Path
from shutil import which
import sys

from invoke import task

PKG_NAME = "image_process"
PKG_PATH = Path(f"pelican/plugins/{PKG_NAME}")
TOOLS = ["poetry", "pre-commit"]

ACTIVE_VENV = os.environ.get("VIRTUAL_ENV", None)
VENV_HOME = Path(
    os.environ.get("WORKON_HOME", "~/.local/share/virtualenvs")
).expanduser()
VENV_PATH = Path(ACTIVE_VENV) if ACTIVE_VENV else (VENV_HOME / PKG_NAME)
VENV = str(VENV_PATH.expanduser())
BIN_DIR = "bin" if os.name != "nt" else "Scripts"
VENV_BIN = Path(VENV) / Path(BIN_DIR)
POETRY = which("poetry") if which("poetry") else (VENV_BIN / "poetry")
CMD_PREFIX = f"{VENV_BIN}/" if ACTIVE_VENV else f"{POETRY} run "
PRECOMMIT = which("pre-commit") if which("pre-commit") else f"{CMD_PREFIX}pre-commit"
PTY = True if os.name != "nt" else False


@task
def tests(c):
    """Run the test suite."""
    c.run(f"{CMD_PREFIX}pytest", pty=PTY)


@task
def black(c, check=False, diff=False):
    """Run Black auto-formatter, optionally with `--check` or `--diff`."""
    check_flag, diff_flag = "", ""
    if check:
        check_flag = "--check"
    if diff:
        diff_flag = "--diff"

    c.run(f"{CMD_PREFIX}black {check_flag} {diff_flag} {PKG_PATH} tasks.py")


@task
def isort(c, check=False, diff=False):
    """Run isort against the codebase."""
    check_flag, diff_flag = "", ""
    if check:
        check_flag = "-c"
    if diff:
        diff_flag = "--diff"
    c.run(f"{CMD_PREFIX}isort {check_flag} {diff_flag} .")


@task
def flake8(c):
    """Run flake8 against the codebase."""
    c.run(f"{CMD_PREFIX}flake8 {PKG_PATH} tasks.py")


@task
def lint(c, diff=False):
    isort(c, check=True, diff=diff)
    black(c, check=True, diff=diff)
    flake8(c)


@task
def tools(c):
    """Install development tools in the virtual environment if not already on PATH."""
    for tool in TOOLS:
        if not which(tool):
            print(f"** Installing {tool}.")
            c.run(f"{CMD_PREFIX}pip install {tool}")


@task
def precommit(c):
    """Install pre-commit hooks to `.git/hooks/pre-commit`."""
    print("** Installing pre-commit hooks.")
    c.run(f"{PRECOMMIT} install")


@task
def setup(c):
    """Run this to get your development environment set up."""
    if which("poetry") or ACTIVE_VENV:
        tools(c)
        print("** Upgrade pip.")
        c.run(f"{CMD_PREFIX}python -m pip install pip --upgrade")
        print(f"** Install {PKG_NAME} for development using poetry.")
        c.run(f"{POETRY} install")
        precommit(c)
    else:
        sys.exit(
            """Poetry is not installed, and there is no active virtual environment
            available. You can either manually create and activate a virtual
            environment, or you can install Poetry via:

            curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -

            Once you have taken one of the above two steps, run `invoke setup` again.
            """  # noqa: E501
        )
