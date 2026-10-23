"""The changeset puddletag shows in About puddletag and in Report a
problem when it runs from a git checkout: the hash of the commit
checked out. Synthetic checkouts.
"""
from pathlib import Path

import pytest

import puddlestuff

SHA = '0123456789abcdef0123456789abcdef01234567'


def changeset(checkout):
    """The changeset the package reports when its source sits in this
    checkout, read as puddletag reads it when it starts."""
    package = checkout / 'puddlestuff'
    package.mkdir()
    namespace = {'__file__': str(package / '__init__.py')}
    exec(compile(Path(puddlestuff.__file__).read_text(), str(package / '__init__.py'), 'exec'), namespace)
    return namespace['changeset']


# The docs are silent on the changeset; each case is a synthetic .git directory.
@pytest.mark.parametrize('files, dirs, expected', [
    pytest.param({'HEAD': SHA + '\n'}, [], SHA, id='detached'),
    pytest.param({'HEAD': 'ref: refs/heads/main\n', 'refs/heads/main': SHA + '\n'}, [], SHA, id='loose'),
    pytest.param(None, [], None, id='no_git'),
    pytest.param({'HEAD': 'ref: refs/heads/main\n',
                  'packed-refs': f'# pack-refs with: peeled fully-peeled sorted \n{SHA} refs/heads/main\n'},
                 [], SHA, id='packed'),
    pytest.param({'HEAD': 'ref: refs/heads/.invalid\n'}, ['reftable'], None, id='reftable'),
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
