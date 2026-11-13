"""Helpers in puddleobjects."""
import json
import os

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QStandardItemModel
from PyQt6.QtWidgets import QLineEdit, QTreeView, QVBoxLayout

from puddlestuff import puddleobjects
from puddlestuff.puddleobjects import (PuddleConfig, PuddleHeader, PuddleThread, create_buddy,
                                      fnmatch, get_icon, get_languages, getfiles, issubfolder,
                                      natural_sort_key, ratio, removeslash, unique)


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


def test_config_value_saved_as_null_reads_as_the_default(tmp_path):
    # Synthetic config: a value saved as null.
    path = tmp_path / 'puddletag.conf'
    path.write_text(json.dumps({'section': {'key': None}}))
    assert PuddleConfig(str(path)).get('section', 'key', 'fallback') == 'fallback'


def test_config_write_failure_keeps_the_file(tmp_path, monkeypatch):
    # #987, "Puddletag trashes its configuration file": a write that fails
    # leaves the old file as it was. Synthetic config.
    path = tmp_path / 'puddletag.conf'
    path.write_text(json.dumps({'section': {'key': 'old'}}))
    config = PuddleConfig(str(path))
    before = path.read_bytes()

    def replace(*args):
        raise OSError('disk full')

    monkeypatch.setattr(puddleobjects.os, 'replace', replace)
    with pytest.raises(OSError):
        config.set('section', 'key', 'new')
    assert path.read_bytes() == before
    assert not (tmp_path / 'puddletag.conf.tmp').exists()


def test_ratio_moves_a_trailing_article():
    # The docs don't say; Mass Tagging matches an album named "X, The" to
    # "The X".
    assert ratio('Beatles, The', 'The Beatles') == 1.0
    assert ratio('The Beatles', 'Beatles, The') == 1.0


def test_ratio_of_two_empty_strings():
    # The docs don't say. Synthetic input.
    assert ratio('', '') == 1.0


def test_removeslash():
    # The docs don't say. Synthetic path.
    assert removeslash('/a/b//') == '/a/b'


def test_create_buddy_in_a_column(qapp):
    # The docs don't say. Synthetic label and field.
    box = create_buddy('Name', edit := QLineEdit(), True)
    assert isinstance(box, QVBoxLayout)
    assert box.itemAt(0).widget().buddy() is edit
    assert box.itemAt(1).widget() is edit


@pytest.mark.parametrize('parent, child, level, expected', [
    ('/a', '/a/b', 1, True),
    ('/a', '/a/b/c', 1, False),
    ('/a', '/a/b/c', None, True),
    ('/a', '/ab', None, False),
    ('/a/', '/a/b', 1, True),
])
def test_issubfolder(parent, child, level, expected):
    # The docs don't say. Synthetic paths.
    assert issubfolder(parent, child, level) is expected


def test_get_icon_without_a_name(qapp):
    # The docs don't say.
    assert get_icon().isNull()


def test_get_languages_reads_any_qm_file(tmp_path):
    # translate.txt: "Copy the .qm to ~/.local/share/puddletag/translations
    # ... you'll have the option to switch to the language in
    # Edit->Preferences", the file being "puddletag_your_locale.qm". The docs
    # say nothing about a file without the prefix. Synthetic empty files.
    (tmp_path / 'puddletag_xx.qm').write_bytes(b'')
    (tmp_path / 'yy.qm').write_bytes(b'')
    languages = get_languages([str(tmp_path)])
    assert languages['xx'] == str(tmp_path / 'puddletag_xx.qm')
    assert languages['yy'] == str(tmp_path / 'yy.qm')


def test_natural_sort_key_against_another_type():
    # The docs don't say. Synthetic text.
    assert (natural_sort_key('a') == 'a') is False
    with pytest.raises(TypeError):
        natural_sort_key('a') < 'a'


def test_getfiles_skips_a_missing_path_and_yields_a_file(tmp_path):
    # The docs don't say. Synthetic file.
    song = tmp_path / 'song.mp3'
    song.write_bytes(b'')
    assert list(getfiles([str(tmp_path / 'missing'), str(song)])) == [str(song)]


NAMES = ['[x', ']x', '^x', 'ax', 'bx', 'cover1.jpg', 'cover12.jpg']


@pytest.mark.parametrize('pattern, expected', [
    ('cover?.jpg', ['cover1.jpg']),
    ('[ab]x', ['ax', 'bx']),
    ('[!a]x', ['[x', ']x', '^x', 'bx']),
    ('[]a]x', [']x', 'ax']),
    ('[^a]x', ['^x', 'ax']),
    ('[x', ['[x']),
])
def test_fnmatch_shell_wildcards(pattern, expected):
    # function.txt (Load artwork): "Filenames are a semicolon-separated list
    # of shell-style wildcards, eg. *.jpg;*.png". Synthetic names.
    assert fnmatch(pattern, NAMES) == expected


def test_thread_command_raising_stop_iteration(qtbot):
    # The docs don't say. Synthetic command.
    thread = PuddleThread(lambda: next(iter([])))
    with qtbot.waitSignal(thread.threadfinished) as blocker:
        thread.start()
    assert blocker.args == ['STOP']
    thread.wait()


@pytest.mark.xfail(strict=True, raises=TypeError,
                   reason='PuddleHeader() without a parent raises TypeError')
def test_header_without_a_parent(qapp):
    # Synthetic: no window builds the header this way (the Filesystem dock
    # passes a parent and no actions).
    header = PuddleHeader()
    assert header.orientation() == Qt.Orientation.Horizontal
    assert header.sectionsMovable()


@pytest.mark.xfail(strict=True, raises=AttributeError,
                   reason='getMenu with actions calls addSeperator, which QMenu lacks')
def test_header_menu_with_extra_actions(qapp):
    # Synthetic: no window builds the header this way (the Filesystem dock
    # passes a parent and no actions).
    model = QStandardItemModel(0, 2)
    model.setHorizontalHeaderLabels(['Name', 'Size'])
    view = QTreeView()
    view.setModel(model)
    header = PuddleHeader(Qt.Orientation.Horizontal, view)
    view.setHeader(header)
    extra = QAction('Extra')
    menu = header.getMenu([extra])
    assert [a.text() for a in menu.actions()] == ['Extra', '', 'Name', 'Size']
    assert menu.actions()[1].isSeparator()


@pytest.mark.parametrize('seq, stable, expected', [
    ([], False, []),
    ([1, 1], False, [1]),
    ([[1], [1]], False, [[1]]),
    ([{1: 2}, {1: 2}], False, [{1: 2}]),
    ([3, 1, 3], True, [3, 1]),
    ([[2], [1], [2]], True, [[2], [1]]),
    ([{1: 2}, {1: 2}], True, [{1: 2}]),
])
def test_unique(seq, stable, expected):
    # The docs don't say. Synthetic lists.
    assert unique(seq, stable) == expected


def test_unique_of_a_set():
    # The docs don't say. Synthetic set.
    assert sorted(unique({2, 1})) == [1, 2]
