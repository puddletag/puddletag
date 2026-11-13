"""What a pip install gets: the wheel built from this tree, as the
publishing workflow builds it (python -m build --wheel)."""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).parents[2]
# What setup.py reads, or installs besides the package.
SETUP_FILES = ['README.md', 'puddletag', 'puddletag.1', 'puddletag.desktop', 'puddletag.png',
               'pyproject.toml', 'requirements.txt', 'setup.py']


def wheel_files(tmp_path):
    """The files in a wheel built from a copy of the tree, so that the
    build's output stays out of the tree."""
    src = tmp_path / 'src'
    shutil.copytree(ROOT / 'puddlestuff', src / 'puddlestuff', ignore=shutil.ignore_patterns('__pycache__'))
    for name in SETUP_FILES:
        shutil.copy(ROOT / name, src / name)
    subprocess.run([sys.executable, '-m', 'build', '--wheel', '--no-isolation',
                    '--outdir', str(tmp_path / 'dist'), str(src)], check=True, capture_output=True)
    [wheel] = (tmp_path / 'dist').glob('*.whl')
    return set(zipfile.ZipFile(wheel).namelist())


def test_wheel_holds_every_bundled_plugin(tmp_path):
    # README: "There are several tools to install puddletag via PyPI"; plugins.txt: a
    # plugin is a folder holding __init__.py and info.
    bundled = sorted(info.parent.name for info in (ROOT / 'puddlestuff' / 'plugins').glob('*/info'))
    assert len(bundled) == 6
    expected = {f'puddlestuff/plugins/{name}/{file}' for name in bundled for file in ('__init__.py', 'info')}
    assert sorted(expected - wheel_files(tmp_path)) == []
