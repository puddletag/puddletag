import os
import sys
from unittest.mock import patch

import pytest
from PyQt6.QtCore import QDir

from puddlestuff.mainwin.dirview import (
    DirModel,
    get_network_mounts,
    is_network_path,
)


def test_is_network_path_unc():
    is_network_path.cache_clear()
    assert is_network_path('//nas/music/rock') is True
    assert is_network_path(r'\\nas\music\rock') is True


def test_is_network_path_gvfs():
    is_network_path.cache_clear()
    assert is_network_path('/run/user/1000/gvfs/smb-share:server=nas/music') is True


def test_is_network_path_empty_or_none():
    is_network_path.cache_clear()
    assert is_network_path('') is False
    assert is_network_path(None) is False


def test_is_network_path_mount_table(tmp_path):
    is_network_path.cache_clear()
    net_mount = str(tmp_path / 'mnt' / 'nas')
    local_path = str(tmp_path / 'home' / 'user' / 'music')

    with patch('puddlestuff.mainwin.dirview.get_network_mounts', return_value=[net_mount]):
        is_network_path.cache_clear()
        assert is_network_path(net_mount + '/Albums/Rock') is True
        assert is_network_path(local_path) is False


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
