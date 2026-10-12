"""Writing tags from the main window (MainWin.writeTags, which the Tag Panel,
Extended Tags and the tag sources go through) when a file can't be written.
Synthetic files.
"""
import os

import mutagen
import pytest
from PyQt6.QtWidgets import QMessageBox

from puddlestuff import audioinfo

pytestmark = pytest.mark.ui


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot):
    music = tmp_path / 'music'
    paths = [make_audio('01.flac', music, title='One'), make_audio('02.flac', music, title='Two')]
    mainwin.openDir(str(music), False)
    model = mainwin._table.model()
    qtbot.waitUntil(lambda: model.rowCount() == 2)
    return model, paths


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
