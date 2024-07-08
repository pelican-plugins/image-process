from inspect import cleandoc
import logging
import os
from pathlib import Path
from shutil import which

from invoke import task

logger = logging.getLogger(__name__)

PKG_NAME = "image_process"
PKG_PATH = Path(f"pelican/plugins/{PKG_NAME}")

ACTIVE_VENV = os.environ.get("VIRTUAL_ENV", None)
VENV_HOME = Path(os.environ.get("WORKON_HOME", "~/.local/share/virtualenvs"))
VENV_PATH = Path(ACTIVE_VENV) if ACTIVE_VENV else (VENV_HOME.expanduser() / PKG_NAME)
VENV = str(VENV_PATH.expanduser())
BIN_DIR = "bin" if os.name != "nt" else "Scripts"
VENV_BIN = Path(VENV) / Path(BIN_DIR)

TOOLS = ("cruft", "pdm", "pre-commit")
PDM = which("pdm") if which("pdm") else (VENV_BIN / "pdm")
CMD_PREFIX = f"{VENV_BIN}/" if ACTIVE_VENV else f"{PDM} run "
CRUFT = which("cruft") if which("cruft") else f"{CMD_PREFIX}cruft"
PRECOMMIT = which("pre-commit") if which("pre-commit") else f"{CMD_PREFIX}pre-commit"
PTY = os.name != "nt"


@task
def tests(c, deprecations=False):
    """Run the test suite, optionally with `--deprecations`."""
    deprecations_flag = "" if deprecations else "-W ignore::DeprecationWarning"
    c.run(f"{CMD_PREFIX}pytest {deprecations_flag}", pty=PTY)


@task
def format(c, check=False, diff=False):
    """Run Ruff's auto-formatter, optionally with `--check` or `--diff`."""
    check_flag, diff_flag = "", ""
    if check:
        check_flag = "--check"
    if diff:
        diff_flag = "--diff"
    c.run(
        f"{CMD_PREFIX}ruff format {check_flag} {diff_flag} {PKG_PATH} tasks.py", pty=PTY
    )


@task
def ruff(c, fix=False, diff=False):
    """Run Ruff to ensure code meets project standards."""
    diff_flag, fix_flag = "", ""
    if fix:
        fix_flag = "--fix"
    if diff:
        diff_flag = "--diff"
    c.run(f"{CMD_PREFIX}ruff check {diff_flag} {fix_flag} .", pty=PTY)


@task
def lint(c, fix=False, diff=False):
    """Check code style via linting tools."""
    ruff(c, fix=fix, diff=diff)
    format(c, check=(not fix), diff=diff)


@task
def tools(c):
    """Install development tools in the virtual environment if not already on PATH."""
    for tool in TOOLS:
        if not which(tool):
            logger.info(f"** Installing {tool} **")
            c.run(f"{CMD_PREFIX}pip install {tool}")


@task
def precommit(c):
    """Install pre-commit hooks to .git/hooks/pre-commit."""
    logger.info("** Installing pre-commit hooks **")
    c.run(f"{PRECOMMIT} install")


@task
def update(c, check=False):
    """Apply upstream plugin template changes to this project."""
    if check:
        logger.info("** Checking for upstream template changes **")
        c.run(f"{CRUFT} check", pty=PTY)
    else:
        logger.info("** Updating project from upstream template **")
        c.run(f"{CRUFT} update", pty=PTY)


@task
def setup(c):
    """Set up the development environment."""
    if which("pdm") or ACTIVE_VENV:
        tools(c)
        c.run(f"{CMD_PREFIX}python -m pip install --upgrade pip", pty=PTY)
        c.run(f"{PDM} update --dev", pty=PTY)
        precommit(c)
        logger.info("\nDevelopment environment should now be set up and ready!\n")
    else:
        error_message = """
            PDM is not installed, and there is no active virtual environment available.
            You can either manually create and activate a virtual environment, or you can
            install PDM via:

            curl -sSL https://raw.githubusercontent.com/pdm-project/pdm/main/install-pdm.py | python3 -

            Once you have taken one of the above two steps, run `invoke setup` again.
            """  # noqa: E501
        raise SystemExit(cleandoc(error_message))
