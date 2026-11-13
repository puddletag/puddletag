"""Writing tags from the main window (MainWin.writeTags, which the Tag Panel,
Extended Tags and the tag sources go through) when a file can't be written.
Synthetic files.
"""
import errno
import os

import mutagen
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QCheckBox, QMessageBox, QStyle, QStyleOptionButton

from puddlestuff import audioinfo

pytestmark = pytest.mark.ui

Key = Qt.Key
Shift = Qt.KeyboardModifier.ShiftModifier


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot):
    music = tmp_path / 'music'
    paths = [make_audio('01.flac', music, title='One'), make_audio('02.flac', music, title='Two')]
    mainwin.openDir(str(music), False)
    model = mainwin._table.model()
    qtbot.waitUntil(lambda: model.rowCount() == 2)
    return model, paths


@pytest.fixture
def three(mainwin, make_audio, tmp_path, qtbot, user):
    music = tmp_path / 'music'
    paths = [make_audio(name, music, title=title)
             for name, title in [('01.flac', 'One'), ('02.flac', 'Two'), ('03.flac', 'Three')]]
    mainwin.openDir(str(music), False)
    model = mainwin._table.model()
    qtbot.waitUntil(lambda: model.rowCount() == 3)
    user.activate()
    mainwin._table.setFocus()
    return model, paths


def title_all(user):
    """Types New into the three files' Title cells at once (F2 on the
    selection, tut3.txt)."""
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(2, 'title'), Shift)
    user.press(Key.Key_F2)
    user.type('New')
    user.press(Key.Key_Return)


def titles_in_files(paths):
    return [mutagen.File(str(path))['title'] for path in paths]


def questions(dialogs):
    return [args[0].text() for name, args, kwargs in dialogs.calls if name == 'QMessageBox.exec']


def unchanged(model, paths):
    in_table = [audioinfo.usertags(audio) for audio in model.taginfo]
    in_files = [[(key.upper(), value) for key, value in mutagen.File(str(path)).tags] for path in paths]
    return in_table == [{'title': ['One']}, {'title': ['Two']}] and \
        in_files == [[('TITLE', 'One')], [('TITLE', 'Two')]]


# A field the files' format can't store: in a VorbisComment, título isn't a
# valid name. tags.txt: such a field "isn't saved: puddletag reports it as it
# does a file it can't write, and the file keeps its tags". Before, it
# aborted the app when written to several files (an exception nothing
# caught, in the write thread).

def test_one_file(mainwin, loaded, dialogs):
    model, paths = loaded
    dialogs.answer('QMessageBox.warning', QMessageBox.StandardButton.Ok)
    mainwin.writeTags(iter([{'título': ['x']}]), [0])
    [(name, (parent, title, message), kwargs)] = dialogs.calls
    assert 'título' in message and 'VorbisComment' in message
    assert unchanged(model, paths)


def test_several_files(mainwin, loaded, dialogs, qtbot):
    model, paths = loaded
    # The error asks whether to go on with the other files: no.
    dialogs.answer('QMessageBox.exec', QMessageBox.StandardButton.No)
    mainwin.writeTags(iter([{'título': ['x']}] * 2), [0, 1])
    qtbot.waitUntil(lambda: len(dialogs.calls) == 1)
    [(name, (box,), kwargs)] = dialogs.calls
    assert 'título' in box.text() and 'VorbisComment' in box.text()
    assert unchanged(model, paths)


@pytest.mark.skipif(os.geteuid() == 0, reason='root can write a read-only file')
def test_continue_after_an_error_writes_the_rest(mainwin, loaded, dialogs, qtbot):
    # The error asks "Do you want to continue?": yes writes the files after
    # the one that failed. Before, when the next-to-last file failed, the
    # last one wasn't written: the progress window counts from 1, so it
    # closed itself, which cancels, one file early.
    model, paths = loaded
    os.chmod(paths[0], 0o444)
    dialogs.answer('QMessageBox.exec', QMessageBox.StandardButton.Yes)
    mainwin.writeTags(iter([{'title': ['New']}] * 2), [0, 1])
    qtbot.waitUntil(lambda: mutagen.File(str(paths[1]))['title'] == ['New'])
    assert mutagen.File(str(paths[0]))['title'] == ['One']
    assert [audio['title'] for audio in model.taginfo] == [['One'], ['New']]


# An error other than an EnvironmentError while saving, here from a file
# another program damaged after puddletag loaded it (synthetic): mutagen
# raises its own error. It's reported like any write error, the table
# keeps the file's value and puddletag goes on. Before, it closed
# puddletag (#989, #937, #1060, #1066 and #1086 report such errors).

def damage(path):
    path.write_bytes(b'not a FLAC file any more')


def test_unexpected_error_one_file(user, loaded, dialogs, qtbot):
    model, paths = loaded
    damage(paths[0])
    user.activate()
    dialogs.answer('QMessageBox.warning', QMessageBox.StandardButton.Ok)
    user.double_click_cell(user.cell(0, 'title'))
    user.type('New')
    user.press(Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: len(dialogs.calls) == 1)
    [(name, (parent, title, message), kwargs)] = dialogs.calls
    assert '01.flac' in message
    assert model.taginfo[0]['title'] == ['One']
    assert not user.action('&Undo').isEnabled()
    assert QApplication.overrideCursor() is None


def test_unexpected_error_several_files(user, loaded, dialogs, qtbot):
    # "Do you want to continue?": yes writes the other file.
    model, paths = loaded
    damage(paths[0])
    user.activate()
    dialogs.answer('QMessageBox.exec', QMessageBox.StandardButton.Yes)
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(1, 'title'), Qt.KeyboardModifier.ShiftModifier)
    user.press(Qt.Key.Key_F2)
    user.type('New')
    user.press(Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: mutagen.File(str(paths[1]))['title'] == ['New'])
    [(name, (box,), kwargs)] = dialogs.calls
    assert '01.flac' in box.text()
    assert [audio['title'] for audio in model.taginfo] == [['One'], ['New']]


@pytest.mark.skipif(os.geteuid() == 0, reason='root can write a read-only file')
def test_no_stops_at_the_file_that_failed(three, user, qtbot, dialogs):
    # The question's own words: "Do you want to continue?". No stops. The
    # docs are silent on it.
    model, paths = three
    os.chmod(paths[1], 0o444)
    dialogs.answer('QMessageBox.exec', QMessageBox.StandardButton.No)
    title_all(user)
    qtbot.waitUntil(lambda: len(dialogs.calls) == 1)
    user.activate()
    [question] = questions(dialogs)
    assert str(paths[1]) in question and 'Do you want to continue?' in question
    assert titles_in_files(paths) == [['New'], ['Two'], ['Three']]
    assert [audio['title'] for audio in model.taginfo] == [['New'], ['Two'], ['Three']]


@pytest.mark.skipif(os.geteuid() == 0, reason='root can write a read-only file')
def test_yes_to_all_asks_once(three, user, qtbot, dialogs):
    # Yes to All carries on and asks no more, though two files fail. The
    # docs are silent on it.
    model, paths = three
    os.chmod(paths[0], 0o444)
    os.chmod(paths[1], 0o444)
    dialogs.answer('QMessageBox.exec', QMessageBox.StandardButton.YesToAll)
    title_all(user)
    qtbot.waitUntil(lambda: titles_in_files(paths)[2] == ['New'])
    user.activate()
    [question] = questions(dialogs)
    assert str(paths[0]) in question
    assert titles_in_files(paths) == [['One'], ['Two'], ['New']]
    assert [audio['title'] for audio in model.taginfo] == [['One'], ['Two'], ['New']]


@pytest.mark.skipif(os.geteuid() == 0, reason='root can write a read-only file')
@pytest.mark.xfail(strict=True, reason='the progress window asks whether to continue '
                   'at the last failing file too, ignoring the count the command yields')
def test_the_last_file_gets_a_plain_warning(three, user, qtbot, dialogs):
    # Undo: "If a file can't be written, puddletag says so as it does for
    # any write and goes on with the other files"; nothing is left to go on
    # with after the last file, so it gets a plain warning, as Undo's does.
    model, paths = three
    os.chmod(paths[2], 0o444)
    dialogs.answer('QMessageBox.warning', QMessageBox.StandardButton.Ok)
    dialogs.answer('QMessageBox.exec', QMessageBox.StandardButton.Yes)
    title_all(user)
    qtbot.waitUntil(lambda: len(dialogs.calls) == 1)
    user.activate()
    assert questions(dialogs) == []
    [(name, args, kwargs)] = dialogs.calls
    assert name == 'QMessageBox.warning' and str(paths[2]) in args[2]
    assert titles_in_files(paths) == [['New'], ['New'], ['Three']]


@pytest.mark.skipif(os.geteuid() == 0, reason='root can write a read-only file')
def test_one_read_only_file(user, loaded, dialogs, qtbot):
    # menus.txt: "If a file can't be written, puddletag says so as it does
    # for any write". Report: #448 (saving hung on files without write
    # rights).
    model, paths = loaded
    os.chmod(paths[0], 0o444)
    user.activate()
    dialogs.answer('QMessageBox.warning', QMessageBox.StandardButton.Ok)
    user.double_click_cell(user.cell(0, 'title'))
    user.type('New')
    user.press(Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: len(dialogs.calls) == 1)
    [(name, (parent, title, message), kwargs)] = dialogs.calls
    assert 'Permission denied' in message and str(paths[0]) in message
    assert unchanged(model, paths)
    assert not user.action('&Undo').isEnabled()
    assert QApplication.overrideCursor() is None


def tick_preserve(user):
    """Preferences > General: Preserve file modification times (off on a new
    profile)."""
    window = user.open_preferences('General')
    [box] = [b for b in window.findChildren(QCheckBox)
             if b.text().replace('&', '').startswith('Preserve file modification times')]
    option = QStyleOptionButton()
    box.initStyleOption(option)
    user.click(box, box.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, box).center())
    assert box.isChecked()
    user.close_preferences(window, 'OK')


def edit_title(user):
    user.activate()
    user.double_click_cell(user.cell(0, 'title'))
    user.type('New')
    user.press(Qt.Key.Key_Return)


def test_preserve_modification_times_keeps_the_time(mainwin, make_audio, tmp_path, qtbot, user, dialogs):
    # preferences.txt: "If checked, a file keeps the modification time it
    # had before puddletag wrote its tags, where the file system allows it."
    # The time is a whole second in September 2001 (synthetic), far from a
    # DST change.
    music = tmp_path / 'music'
    path = make_audio('01.flac', music, title='One')
    os.utime(path, (1_000_000_000, 1_000_000_000))
    mainwin.openDir(str(music), False)
    model = mainwin._table.model()
    qtbot.waitUntil(lambda: model.rowCount() == 1)
    tick_preserve(user)
    edit_title(user)
    qtbot.waitUntil(lambda: mutagen.File(str(path))['title'] == ['New'])
    assert path.stat().st_mtime == 1_000_000_000
    assert model.taginfo[0]['title'] == ['New']
    assert dialogs.calls == []


def test_modification_time_that_cannot_be_set(mainwin, make_audio, tmp_path, qtbot, user, dialogs, monkeypatch):
    # preferences.txt: "If checked, a file keeps the modification time it
    # had before puddletag wrote its tags, where the file system allows it."
    # Where it doesn't, the tags are written and nothing is reported.
    music = tmp_path / 'music'
    path = make_audio('01.flac', music, title='One')
    mainwin.openDir(str(music), False)
    model = mainwin._table.model()
    qtbot.waitUntil(lambda: model.rowCount() == 1)
    tick_preserve(user)

    def refuse(*args):
        raise PermissionError(errno.EPERM, os.strerror(errno.EPERM))

    monkeypatch.setattr('puddlestuff.util.setmodtime', refuse)
    edit_title(user)
    qtbot.waitUntil(lambda: mutagen.File(str(path))['title'] == ['New'])
    assert dialogs.calls == []
    assert model.taginfo[0]['title'] == ['New']
