"""The changeset puddletag shows in About puddletag and in Report a
problem when it runs from a git checkout: the hash of the commit
checked out. Synthetic checkouts.
"""
from pathlib import Path

import pytest

import puddlestuff

SHA = '0123456789abcdef0123456789abcdef01234567'
ROOT = Path(__file__).resolve().parents[2]
OTHER = 'fedcba9876543210fedcba9876543210fedcba98'


def init_namespace(checkout, source=None):
    """puddlestuff/__init__.py run as if its source sat in this checkout:
    the namespace it leaves. Compiled under the real file's name so
    coverage counts its lines."""
    package = checkout / 'puddlestuff'
    package.mkdir(exist_ok=True)
    # Not named __init__.py: coverage takes a frame's __file__ over the
    # compiled name when their basenames match, and files the lines under
    # the temp path.
    namespace = {'__file__': str(package / 'checkout.py')}
    if source is None:
        source = Path(puddlestuff.__file__).read_text()
    exec(compile(source, puddlestuff.__file__, 'exec'), namespace)
    return namespace


def changeset(checkout):
    """The changeset the package reports when its source sits in this
    checkout, read as puddletag reads it when it starts."""
    return init_namespace(checkout)['changeset']


# The docs are silent on the changeset; each case is a synthetic .git directory.
@pytest.mark.parametrize('files, dirs, expected', [
    pytest.param({'HEAD': SHA + '\n'}, [], SHA, id='detached'),
    pytest.param({'HEAD': 'ref: refs/heads/main\n', 'refs/heads/main': SHA + '\n'}, [], SHA, id='loose'),
    pytest.param(None, [], None, id='no_git'),
    pytest.param({'HEAD': 'ref: refs/heads/main\n',
                  'packed-refs': f'# pack-refs with: peeled fully-peeled sorted \n{SHA} refs/heads/main\n'},
                 [], SHA, id='packed'),
    pytest.param({'HEAD': 'ref: refs/heads/.invalid\n'}, ['reftable'], None, id='reftable'),
    pytest.param({'HEAD': 'ref: refs/heads/main\n',
                  'packed-refs': f'# pack-refs with: peeled fully-peeled sorted \n{SHA} refs/heads/other\n^{OTHER}\n'},
                 [], None, id='in_neither'),
])
def test_changeset_from_a_git_checkout(tmp_path, files, dirs, expected):
    if files is not None:
        git = tmp_path / '.git'
        for name, text in files.items():
            (git / name).parent.mkdir(parents=True, exist_ok=True)
            (git / name).write_text(text)
        for name in dirs:
            (git / name).mkdir()
    assert changeset(tmp_path) == expected


# CONTRIBUTING.md, "CI and publishing": "It appends `.post<run number>` to the
# version (via `_buildid` in `puddlestuff/__init__.py`) and publishes to
# TestPyPI." The workflow does it with the sed line asserted below; the run
# number 42 is synthetic.
def test_build_number_is_appended_to_the_version(tmp_path):
    workflow = (ROOT / '.github/workflows/publish-to-pypi.yml').read_text()
    assert 'sed -i "/_buildid/s/None/$GITHUB_RUN_NUMBER/" puddlestuff/__init__.py' in workflow
    source = Path(puddlestuff.__file__).read_text()
    edited = ''.join(line.replace('None', '42', 1) if '_buildid' in line else line
                     for line in source.splitlines(keepends=True))
    namespace = init_namespace(tmp_path, edited)
    assert namespace['version_string'] == puddlestuff.version_string + '.post42'
    assert namespace['__version__'] == namespace['version_string']
