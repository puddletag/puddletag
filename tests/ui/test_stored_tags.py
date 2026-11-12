"""The Stored Tags window (menus.txt: "The Stored Tags dialog displays the
Tags of the currently selected files as stored on disk"), shown from the
Windows menu as a user shows it. Synthetic files.
"""
import os

import mutagen.apev2
import mutagen.id3
import pytest
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QApplication, QLabel

from puddlestuff.mainwin.storedtags import StoredTags

pytestmark = pytest.mark.ui

Key = Qt.Key


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    """Two MP3s titled One and Two, listed, with Stored Tags shown and the
    first file selected."""
    music = tmp_path / 'music'
    paths = [make_audio('01.mp3', music, title='One'), make_audio('02.mp3', music, title='Two')]
    mainwin.openDir(str(music), False)
    qtbot.waitUntil(lambda: mainwin._table.model().rowCount() == 2)
    user.activate()
    user.click_menu('Stored Tags')
    [dock] = mainwin.findChildren(StoredTags)
    qtbot.waitUntil(dock.isVisible)
    user.click_cell(user.cell(0, 'title'))
    qtbot.waitUntil(lambda: labels(dock) == ['ID3v2.4', 'title:', 'One'])
    return dock, paths


def labels(dock):
    """The dock's text, in the order it's laid out: each tag's name, then its
    fields and values."""
    return [label.text() for label in dock.findChildren(QLabel)]


def bold(dock):
    return [label.text() for label in dock.findChildren(QLabel) if label.font().bold()]


def test_every_tag_in_the_file_is_listed(mainwin, make_audio, tmp_path, qtbot, user):
    # menus.txt: "displays the Tags of the currently selected files as stored
    # on disk". The order is the docs' silence: the tag puddletag reads first,
    # then the others as the file holds them. Synthetic file.
    music = tmp_path / 'music'
    path = make_audio('01.mp3', music, artist='V2 artist', title='V2 title')
    # APEv2 first: saved the other way round, mutagen leaves the ID3v1 tag
    # where it can no longer be found.
    ape = mutagen.apev2.APEv2()
    ape['Artist'] = 'Ape artist'
    ape['Title'] = 'Ape title'
    ape.save(str(path))
    mutagen.id3.ID3(str(path)).save(v1=2, v2_version=3)
    mainwin.openDir(str(music), False)
    qtbot.waitUntil(lambda: mainwin._table.model().rowCount() == 1)
    user.activate()
    user.click_menu('Stored Tags')
    [dock] = mainwin.findChildren(StoredTags)
    qtbot.waitUntil(dock.isVisible)
    user.click_cell(user.cell(0, 'title'))
    expected = ['ID3v2.3', 'artist:', 'V2 artist', 'title:', 'V2 title',
                'ID3v1.1', 'artist:', 'V2 artist', 'title:', 'V2 title',
                'APEv2', 'artist:', 'Ape artist', 'title:', 'Ape title']
    qtbot.waitUntil(lambda: labels(dock) == expected)
    assert bold(dock) == ['ID3v2.3', 'ID3v1.1', 'APEv2']


@pytest.mark.skipif(os.geteuid() == 0, reason='root can read a file without permissions')
@pytest.mark.xfail(strict=True, reason='Stored Tags raises KeyError for a file it can\'t read')
def test_file_that_cant_be_read(loaded, qtbot, user):
    # The docs are silent about a file puddletag can't read; this is what the
    # dock should show instead of failing: the error, in bold.
    dock, paths = loaded
    os.chmod(paths[1], 0)
    try:
        user.click_cell(user.cell(1, 'title'))
        qtbot.waitUntil(lambda: labels(dock) == ['Error', 'Permission denied'])
    finally:
        os.chmod(paths[1], 0o644)
    assert bold(dock) == ['Error']


@pytest.mark.xfail(strict=True, reason='Stored Tags raises the format\'s error for a file it can\'t read')
def test_file_that_isnt_audio_any_more(loaded, qtbot, user):
    # The docs are silent about a listed file that was overwritten; the dock
    # should show the error, in bold. Synthetic: 4096 zero bytes.
    dock, paths = loaded
    paths[1].write_bytes(b'\0' * 4096)
    user.click_cell(user.cell(1, 'title'))
    qtbot.waitUntil(lambda: labels(dock) == ['Error', "can't sync to MPEG frame"])
    assert bold(dock) == ['Error']


def test_file_removed_after_it_was_listed(loaded, qtbot, user):
    # The docs are silent about a listed file deleted behind puddletag's
    # back; the dock empties, with no dialog (the guard fails the test on one).
    dock, paths = loaded
    paths[1].unlink()
    user.click_cell(user.cell(1, 'title'))
    qtbot.waitUntil(lambda: labels(dock) == [])


def test_wheel_scrolls_sideways_without_a_vertical_bar(mainwin, make_audio, tmp_path, qtbot, user):
    # The docs don't say; this is what puddletag does: with the contents wider
    # than the dock and no vertical bar, a wheel notch scrolls sideways,
    # 120 // 5 pixels. Synthetic: a 2000-character album.
    music = tmp_path / 'music'
    make_audio('01.mp3', music, title='One', album='x' * 2000)
    mainwin.openDir(str(music), False)
    qtbot.waitUntil(lambda: mainwin._table.model().rowCount() == 1)
    user.activate()
    user.click_menu('Stored Tags')
    [dock] = mainwin.findChildren(StoredTags)
    qtbot.waitUntil(dock.isVisible)
    dock.resize(150, 600)
    user.click_cell(user.cell(0, 'title'))
    h, v = dock.horizontalScrollBar(), dock.verticalScrollBar()
    qtbot.waitUntil(lambda: h.isVisible() and not v.isVisible())
    before = h.value()
    # qtbot can't make a QWheelEvent, so it goes straight to the viewport.
    pos = QPointF(dock.viewport().rect().center())
    QApplication.sendEvent(dock.viewport(), QWheelEvent(
        pos, QPointF(dock.viewport().mapToGlobal(pos.toPoint())), QPoint(0, 0), QPoint(0, -120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False))
    assert h.value() == before + 24
