import os
import sys
from unittest.mock import patch

import pytest
from PyQt6.QtCore import QDir

from puddlestuff.mainwin import dirview
from puddlestuff.mainwin.dirview import (
    DirModel,
    get_network_mounts,
    is_network_path,
)


def test_is_network_path_empty_or_none():
    assert is_network_path('') is False
    assert is_network_path(None) is False


def test_is_network_path_mount_table(tmp_path):
    net_mount = str(tmp_path / 'mnt' / 'nas')
    local_path = str(tmp_path / 'home' / 'user' / 'music')

    with patch('puddlestuff.mainwin.dirview.get_network_mounts', return_value=[net_mount]):
        assert is_network_path(net_mount + '/Albums/Rock') is True
        assert is_network_path(local_path) is False


def test_is_network_path_follows_the_mount_table(monkeypatch):
    # A folder checked before its share was mounted, as an automounted
    # share is on first access.
    table = [[]]
    monkeypatch.setattr(dirview, 'get_network_mounts', lambda: table[0])
    assert is_network_path('/mnt/nas/Artist') is False
    table[0] = ['/mnt/nas']
    assert is_network_path('/mnt/nas/Artist') is True


# Lines of a real /proc/mounts: a local disk, an NFS share and GNOME's GVFS.
REAL_MOUNTS = (
    '/dev/mapper/system-root / xfs rw,noatime,attr2,inode64,logbufs=8,logbsize=32k,noquota 0 0\n'
    'nas:/music /nas/music nfs4 rw,nosuid,nodev,noatime,vers=4.1,rsize=1048576,wsize=1048576,namlen=255,soft,'
    'proto=tcp,timeo=100,retrans=2,sec=sys,clientaddr=192.168.0.218,local_lock=none,addr=192.168.0.70 0 0\n'
    'gvfsd-fuse /run/user/1000/gvfs fuse.gvfsd-fuse rw,nosuid,nodev,relatime,user_id=1000,group_id=1000 0 0\n'
)


@pytest.fixture
def mounts(tmp_path, monkeypatch):
    """Writes the mount table's file for dirview to read, with its cache
    empty, and returns the file.

    The test calls it, not the fixture: pytest-qt processes Qt events after
    the fixtures, and a DirModel an earlier test left alive then reads the
    table, caching it before the test has written it.
    """
    path = tmp_path / 'mounts'

    def write(text):
        path.write_text(text, encoding='utf-8')
        monkeypatch.setattr(dirview, 'MOUNTS', str(path))
        monkeypatch.setattr(dirview, '_network_mounts_cache', None)
        return path
    return write


def test_network_mounts(mounts):
    # Synthetic: SMB shares mounted on folders named with a space, which
    # the table escapes, and with a non-ASCII letter.
    mounts(REAL_MOUNTS + '//nas/a /mnt/My\\040Music cifs rw 0 0\n'
                         '//nas/b /mnt/Música cifs rw 0 0\n')
    assert sorted(get_network_mounts()) == ['/mnt/My Music', '/mnt/Música', '/nas/music', '/run/user/1000/gvfs']


def test_mount_table_read_again_after_10_seconds(mounts, monkeypatch):
    # Also when it lists no network mount.
    clock = [1000.0]
    monkeypatch.setattr(dirview.time, 'monotonic', lambda: clock[0])
    table = mounts(REAL_MOUNTS.splitlines(keepends=True)[0])
    assert get_network_mounts() == []
    table.write_text(REAL_MOUNTS)
    clock[0] += 9
    assert get_network_mounts() == []
    clock[0] += 2
    assert sorted(get_network_mounts()) == ['/nas/music', '/run/user/1000/gvfs']


def test_dirmodel_local_empty_and_nonempty(qapp, tmp_path):
    empty_dir = tmp_path / 'empty'
    empty_dir.mkdir()

    nonempty_dir = tmp_path / 'with_sub'
    nonempty_dir.mkdir()
    (nonempty_dir / 'child').mkdir()

    model = DirModel()
    idx_empty = model.index(str(empty_dir))
    idx_nonempty = model.index(str(nonempty_dir))

    # Empty folder hides arrow immediately without needing to expand
    assert model.hasChildren(idx_empty) is False
    # Non-empty folder shows arrow immediately
    assert model.hasChildren(idx_nonempty) is True


def test_dirmodel_network_share_unpopulated_shows_arrow_then_hides_if_empty(qtbot, qapp, tmp_path):
    empty_dir = str(tmp_path / 'net_empty')
    os.mkdir(empty_dir)

    model = DirModel()
    idx_empty = model.index(empty_dir)

    with patch('puddlestuff.mainwin.dirview.is_network_path', return_value=True):
        # Unpopulated network folder shows arrow without synchronous QDirIterator
        assert model.hasChildren(idx_empty) is True

        # When Qt's background engine fetches the folder:
        with qtbot.waitSignal(
            model.directoryLoaded,
            check_params_cb=lambda path: path == empty_dir,
            timeout=5000,
        ):
            model.fetchMore(idx_empty)

        # Once loaded, Qt detects 0 subfolders and hides the arrow
        assert model.hasChildren(idx_empty) is False


def test_dirmodel_network_share_populated_nonempty_shows_arrow(qtbot, qapp, tmp_path):
    nonempty_dir = str(tmp_path / 'net_nonempty')
    os.mkdir(nonempty_dir)
    os.mkdir(os.path.join(nonempty_dir, 'sub'))

    model = DirModel()
    idx = model.index(nonempty_dir)

    with patch('puddlestuff.mainwin.dirview.is_network_path', return_value=True):
        assert model.hasChildren(idx) is True

        with qtbot.waitSignal(
            model.directoryLoaded,
            check_params_cb=lambda path: path == nonempty_dir,
            timeout=5000,
        ):
            model.fetchMore(idx)

        assert model.hasChildren(idx) is True
