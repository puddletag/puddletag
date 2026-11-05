"""Helpers in puddleobjects that load files."""
import os

import pytest

from puddlestuff import puddleobjects
from puddlestuff.puddleobjects import getfiles


@pytest.fixture
def unsorted_walk(monkeypatch):
    """os.walk listing the folders of one top folder in a fixed unsorted order.

    Like the real one, it honours in-place edits of the folder list.
    """
    def walk(top):
        dirnames = ['cd2', 'cd10', 'cd1']
        yield top, dirnames, ['top.mp3']
        for name in dirnames:
            yield os.path.join(top, name), [], ['01.mp3']

    monkeypatch.setattr(puddleobjects.os, 'walk', walk)


def test_subfolders_are_read_in_name_order(tmp_path, unsorted_walk):
    # The docs don't say; users shouldn't see an order that varies by machine.
    # Synthetic folders and files: files named alike in two folders stay in
    # this order in the table.
    assert list(getfiles(str(tmp_path), True)) == [
        str(tmp_path / 'top.mp3'), str(tmp_path / 'cd1' / '01.mp3'),
        str(tmp_path / 'cd2' / '01.mp3'), str(tmp_path / 'cd10' / '01.mp3')]


def test_subfolders_are_skipped_when_not_asked_for(tmp_path, unsorted_walk):
    # Synthetic folders and files.
    assert list(getfiles(str(tmp_path), False)) == [str(tmp_path / 'top.mp3')]
