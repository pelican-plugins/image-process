
import os
from pathlib import Path
import re
import shutil
import subprocess

import colorama
from minchin import text
from invoke import run, task
import semantic_version
from semantic_version import Version
# also requires `twine`

# TODO: provide for alternative shell on something other than Windows
INVOKE_SHELL = 'C:\Windows\system32\cmd.EXE'

p = Path(__file__).parent  # directory holding this file


#@task
def build(ctx):
    pass


@task
def test(ctx):
    run('python {}/test_image_process.py'.format(test_directory()),
        shell=INVOKE_SHELL)


version_re = re.compile(r"__version__ = [\"\']{1,3}(?P<major>\d+)\.(?P<minor>\d+).(?P<patch>\d+)(?:-(?P<prerelease>[0-9A-Za-z\.]+))?(?:\+[0-9A-Za-z-\.]+)?[\"\']{1,3}")
bare_version_re = re.compile(r"__version__ = [\"\']{1,3}([\.\dA-Za-z+-]*)[\"\']{1,3}")
list_match_re = re.compile(r"(?P<leading>[ \t]*)(?P<mark>[-\*+]) +:\w+:")


def here_directory():
    return(Path.cwd())


def module_name():
    return("minchin.pelican.plugins.image_process")


def source_directory():
    return(here_directory() / 'minchin')


def test_directory():
    return(here_directory() / 'tests')


def doc_directory():
    #return(here_directory() / 'docs')
    pass


def dist_directory():
    return(here_directory() / 'dist')


def version_file():
    return(source_directory() / 'pelican' / 'plugins' / 'image_process.py')


def changelog_file():
    return(here_directory() / "changelog.rst")


def server_url(server_name):
    server_name = server_name.lower()
    if server_name in ["testpypi", "pypitest"]:
        return(r"https://testpypi.python.org/pypi")
    elif server_name in ["pypi", ]:
        return(r"https://pypi.python.org/pypi")


def update_version_number(update_level='patch'):
    """Update version number

    Returns a semantic_version object"""

    """Find current version"""
    temp_file = version_file().parent / ("~" + version_file().name)
    with open(str(temp_file), 'w') as g:
        with open(str(version_file()), 'r') as f:
            for line in f:
                version_matches = bare_version_re.match(line)
                if version_matches:
                    bare_version_str = version_matches.groups(0)[0]
                    if semantic_version.validate(bare_version_str):
                        current_version = Version(bare_version_str)
                        print("{}Current version is {}".format(" "*4, current_version))
                    else:
                        current_version = Version.coerce(bare_version_str)
                        if not text.query_yes_quit("{}I think the version is {}. Use it?".format(" "*4, current_version), default="yes"):
                            exit(colorama.Fore.RED + 'Please set an initial version number to continue')

                    """Determine new version number"""
                    if update_level is 'major':
                        current_version = current_version.next_major()
                    elif update_level is 'minor':
                        current_version = current_version.next_minor()
                    elif update_level is 'patch':
                        current_version = current_version.next_patch()
                    elif update_level is 'prerelease':
                        if not current_version.prerelease:
                            current_version = current_version.next_patch()
                            current_version.prerelease = ('dev', )
                    elif update_level is None:
                        # don't update version
                        pass
                    else:
                        exit(colorama.Fore.RED + 'Cannot update version in {} mode'.format(update_level))

                    print("{}New version is     {}".format(" "*4, current_version))

                    """Update version number"""
                    line = '__version__ = "{}"\n'.format(current_version)
                print(line, file=g, end="")
        #print('', file=g)  # add a blank line at the end of the file
    shutil.copyfile(str(temp_file), str(version_file()))
    os.remove(str(temp_file))
    return(current_version)


def build_distribution():
    build_status = subprocess.check_call(['python', 'setup.py', 'sdist', 'bdist_egg', 'bdist_wheel'])
    if build_status is not 0:
        exit(colorama.Fore.RED + 'Something broke tyring to package your code...')


def other_dependancies(server, environment):
    """
    Installs things that need to be in place before installing the main package
    """
    print('  ** Other Dependancides, based on server', server, '**')
    server = server.lower()
    # Pillow is not on TestPyPI
    if server is "local":
        pass
    elif server in ["testpypi", "pypitest"]:
        # these are packages not available on the test server, so install them
        # off the regular pypi server
        print("  **Install Pillow, six, pelican**")
        subprocess.call([environment + '\\Scripts\\pip.exe', 'install', 'Pillow', 'six', 'pelican'], shell=True)
    elif server in ["pypi"]:
        # Pillow is wierd to install. Counting on a cached version of it here
        print("  **Install Pillow**")
        subprocess.call([environment + '\\Scripts\\pip.exe', 'install', 'Pillow', 'python-dateutil'], shell=True)
        print("  **Install dateutil**")
        subprocess.call([environment + '\\Scripts\\pip.exe', 'install', 'python-dateutil'], shell=True)
    else:
        print("  **Nothing more to install**")


def check_local_install(version, ext, server="local"):
    all_files = list(dist_directory().glob('*.{}'.format(ext)))
    the_file = all_files[0]
    for f in all_files[1:]:
        if f.stat().st_mtime > the_file.stat().st_mtime:
            the_file = f

    environment = 'env-{}-{}-{}'.format(version, ext, server)
    if server == "local":
        pass
    else:
        # upload to server
        print("  **Uploading**")
        subprocess.call(['twine', 'upload', str(the_file), '-r', server])

    if (here_directory() / environment).exists():
        shutil.rmtree(environment)  # remove directory if it exists
    subprocess.call(['python', '-m', 'venv', environment])
    if server == "local":
        subprocess.call([environment + '\\Scripts\\pip.exe', 'install', str(the_file)], shell=True)
    else:
        other_dependancies(server, environment)
        print("  **Install from server**")
        subprocess.call([environment + '\\Scripts\\pip.exe', 'install', '-i', server_url(server), module_name() + "==" + str(version)], shell=True)
    print("  **Test version of install package**")
    test_version = subprocess.check_output([environment + '\\Scripts\\python.exe', '-c', "exec(\"\"\"import {0}\\nprint({0}.__version__)\\n\"\"\")".format(module_name())], shell=True)
    test_version = test_version.decode('ascii').strip()
    # print(test_version, type(test_version), type(expected_version))
    if (Version(test_version) == version):
        print('{}{} install {} works!{}'.format(colorama.Fore.GREEN, server, ext, colorama.Style.RESET_ALL))
    else:
        exit('{}{} install {} broken{}'.format(colorama.Fore.RED, server, ext, colorama.Style.RESET_ALL))


@task
def make_release(cts):
    make_release_version = '0.2.0'
    colorama.init()
    text.title("Minchin 'Make Release' for Python v{}".format(make_release_version))
    print()
    text.subtitle("Configuration")
    print("base dir     -> {}".format(here_directory()))
    print("source       -> .\{}\\".format(source_directory().relative_to(here_directory())))
    print("test dir     -> .\{}\\".format(test_directory().relative_to(here_directory())))
    #print("doc dir      -> .\{}\\".format(doc_directory().relative_to(here_directory())))
    print("version file -> .\{}".format(version_file().relative_to(here_directory())))
    print()
    text.subtitle("Git -- Clean directory?")
    print()
    text.subtitle("Sort Import Statements")
    print()
    text.subtitle("Run Tests")
    print()
    text.subtitle("Update Version Number")
    new_version = update_version_number(None)
    print()
    text.subtitle("Add Release to Changelog")
    print()
    text.subtitle("Build Documentation")
    print()
    text.query_yes_quit('All good and ready to go?')

    text.subtitle("Build Distributions")
    build_distribution()

    for server in [
                    "local",
                    "testpypi",
                    "pypi",
                  ]:
        for file_format in ["tar.gz", "whl"]:
            print()
            text.subtitle("Test {} Build {}".format(file_format, server))
            check_local_install(new_version, file_format, server)

    # new_version = update_version_number('prerelease')
