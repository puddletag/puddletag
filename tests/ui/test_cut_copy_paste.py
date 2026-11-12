"""Cut, Copy and Paste (menus.txt), run as a user runs them: the Edit menu,
their shortcuts and the File-View's right-click menu. Each paste is checked
in the files and in the table. Synthetic files.
"""
import base64
import json
import pickle
from pathlib import Path

import pytest
from PyQt6.QtCore import QMimeData, Qt, QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox

from puddlestuff import audioinfo

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier

JPEG = b'\xff\xd8' + b'\0' * 64 + b'\xff\xd9'

# Read before the dialog guard replaces it, so the 5 MiB question can run
# for real.
REAL_EXEC = QMessageBox.exec

# Synthetic: a JPEG's start and end around 4 MiB of zeros; its base64 alone
# is over 5 MiB.
BIG_JPEG = b'\xff\xd8' + b'\0' * (4 * 1024 * 1024) + b'\xff\xd9'
LARGE = ("That's a large amount of data to copy.\nIt may cause your system to lock up.\n\n"
         "Do you want to go ahead?")


@pytest.fixture(autouse=True)
def empty_clipboard():
    """The clipboard is the whole app's: a test would otherwise paste what
    the one before it copied."""
    QApplication.clipboard().clear()


def load(mainwin, qtbot, user, paths):
    mainwin.openDir(str(paths[0].parent), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == len(paths))
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]
    user.activate()
    table.setFocus()
    return table


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    """Four MP3s: the first two to copy from, the last two to paste onto."""
    music = tmp_path / 'music'
    paths = [make_audio(f'0{i}.mp3', music, artist=f'Artist {i}', title=f'Title {i}', album=f'Album {i}')
             for i in (1, 2, 3, 4)]
    return load(mainwin, qtbot, user, paths), paths


def in_file(path, *fields):
    tag = audioinfo.Tag(str(path))
    return [tag.get(field) for field in fields]


def shown(table, row, *fields):
    audio = table.model().taginfo[row]
    return [audio.get(field) for field in fields]


def select(user, first, last):
    """Clicks the first cell and Shift+clicks the last: (row, field)."""
    user.click_cell(user.cell(*first))
    user.click_cell(user.cell(*last), Shift)


def written(user, qtbot, check):
    """Several files are written in a thread, behind a progress window."""
    qtbot.waitUntil(check)
    user.activate()


def by_menu(name):
    return lambda user, index: user.click_menu(name)


def by_key(key, modifier=Ctrl):
    return lambda user, index: user.press(key, modifier)


def by_right_click(name):
    return lambda user, index: user.right_click_cell(index, name)


def ways(name, *keys):
    """A command from the Edit menu, each of its shortcuts and the
    File-View's right-click menu."""
    return {'Edit menu': by_menu(name), **{label: by_key(*key) for label, key in keys},
            'right-click menu': by_right_click(name)}


COPY = ways('&Copy Selection', ('Ctrl+C', (Key.Key_C,)))
CUT = ways('&Cut', ('Ctrl+X', (Key.Key_X,)))
COPY_ALL = ways('Copy All &Fields', ('Ctrl+Shift+C', (Key.Key_C, Ctrl | Shift)))
PASTE = ways('&Paste', ('Ctrl+V', (Key.Key_V,)), ('Shift+Ins', (Key.Key_Insert, Shift)))
PASTE_ONTO = ways('Paste &Onto Selection')


@pytest.mark.parametrize('copy', COPY.values(), ids=COPY.keys())
def test_copy_selection(user, loaded, qtbot, copy):
    # "Copies the selected cells to the clipboard", then Paste "Pastes the
    # copied/cut fields onto the selected files".
    table, paths = loaded
    select(user, (0, 'artist'), (1, 'title'))
    copy(user, user.cell(1, 'title'))
    select(user, (2, 'artist'), (3, 'artist'))
    user.press(Key.Key_V, Ctrl)
    written(user, qtbot, lambda: in_file(paths[3], 'artist') == [['Artist 2']])
    assert [in_file(p, 'artist', 'title', 'album') for p in paths[2:]] == [
        [['Artist 1'], ['Title 1'], ['Album 3']], [['Artist 2'], ['Title 2'], ['Album 4']]]
    assert shown(table, 2, 'artist', 'title') == [['Artist 1'], ['Title 1']]


@pytest.mark.parametrize('cut', CUT.values(), ids=CUT.keys())
def test_cut(user, loaded, qtbot, cut):
    # "Works like Copy Selection, but removes the selected fields."
    table, paths = loaded
    select(user, (0, 'artist'), (1, 'artist'))
    cut(user, user.cell(1, 'artist'))
    written(user, qtbot, lambda: in_file(paths[1], 'artist') == [None])
    assert in_file(paths[0], 'artist', 'title') == [None, ['Title 1']]
    assert shown(table, 0, 'artist') == [None]
    select(user, (2, 'artist'), (3, 'artist'))
    user.press(Key.Key_V, Ctrl)
    written(user, qtbot, lambda: in_file(paths[3], 'artist') == [['Artist 2']])
    assert in_file(paths[2], 'artist', 'title') == [['Artist 1'], ['Title 3']]


@pytest.mark.parametrize('paste', PASTE.values(), ids=PASTE.keys())
def test_paste(user, loaded, qtbot, paste):
    table, paths = loaded
    select(user, (0, 'artist'), (1, 'title'))
    user.press(Key.Key_C, Ctrl)
    select(user, (2, 'artist'), (3, 'artist'))
    paste(user, user.cell(3, 'artist'))
    written(user, qtbot, lambda: in_file(paths[3], 'artist', 'title') == [['Artist 2'], ['Title 2']])
    assert in_file(paths[2], 'artist', 'title') == [['Artist 1'], ['Title 1']]


@pytest.mark.parametrize('targets', [1, 5, 15])
def test_paste_restarts_from_the_first_tag(mainwin, make_audio, tmp_path, qtbot, user, targets):
    # "If you have more files selected than the number of tags copied, then
    # the pasting restarts from the first tag copied. E.g say you copied
    # the artist and title fields of ten files before.
    # * Pasting the copied tags onto 1 file will result in the first copied
    #   tag being written to that one file.
    # * Having five files selected will result in the first five copied
    #   tags being written to the selected files.
    # * If you have 15 files selected. All ten tags in the clipboard will
    #   get written the first selection. Following which, the first five
    #   copied tags will get written to the rest of the selected files."
    music = tmp_path / 'music'
    paths = [make_audio(f'{i:02}.mp3', music, artist=f'Artist {i}', title=f'Title {i}') for i in range(25)]
    load(mainwin, qtbot, user, paths)
    select(user, (0, 'artist'), (9, 'title'))
    user.press(Key.Key_C, Ctrl)
    select(user, (10, 'artist'), (9 + targets, 'artist'))
    user.press(Key.Key_V, Ctrl)
    last = paths[9 + targets]
    written(user, qtbot, lambda: in_file(last, 'artist') == [[f'Artist {(targets - 1) % 10}']])
    pasted = [in_file(p, 'artist', 'title') for p in paths[10:]]
    copied = [[[f'Artist {i % 10}'], [f'Title {i % 10}']] for i in range(targets)]
    untouched = [[[f'Artist {i}'], [f'Title {i}']] for i in range(10 + targets, 25)]
    assert pasted == copied + untouched


@pytest.mark.parametrize('copy_all', COPY_ALL.values(), ids=COPY_ALL.keys())
def test_copy_all_fields(user, loaded, qtbot, copy_all):
    # "Copies the complete tag of the selected files": its cover too.
    table, paths = loaded
    tag = audioinfo.Tag(str(paths[0]))
    tag.update({'genre': ['Genre 1'], '__image': [{'data': JPEG, 'mime': 'image/jpeg'}]})
    tag.save()
    user.press(Key.Key_F5)  # Refresh, to read the cover
    qtbot.waitUntil(lambda: bool(table.model().taginfo[0].images))
    user.activate()  # the loading window took the activation
    user.click_cell(user.cell(0, 'title'))
    copy_all(user, user.cell(0, 'title'))
    user.click_cell(user.cell(2, 'title'))
    user.press(Key.Key_V, Ctrl)
    qtbot.waitUntil(lambda: in_file(paths[2], 'genre') == [['Genre 1']])
    assert in_file(paths[2], 'artist', 'title', 'album') == [['Artist 1'], ['Title 1'], ['Album 1']]
    assert [image['data'] for image in audioinfo.Tag(str(paths[2])).images] == [JPEG]


def with_originalartist(table):
    """Adds an Original Artist column, as Select Columns does."""
    table.setHeaderTags(table.model().headerdata + [('Original Artist', 'originalartist')])


@pytest.mark.parametrize('paste_onto', PASTE_ONTO.values(), ids=PASTE_ONTO.keys())
def test_paste_onto_selection(user, loaded, qtbot, paste_onto):
    # "If, for example, you'd copied the artist and album fields of a
    # single file before, but now have the title and originalartist fields
    # selected. The copied value in artist field will get to written to
    # the title field and the copied album value will get written to the
    # originalartist field."
    table, paths = loaded
    with_originalartist(table)
    user.click_cell(user.cell(0, 'artist'))
    user.click_cell(user.cell(0, 'album'), Ctrl)
    user.press(Key.Key_C, Ctrl)
    user.click_cell(user.cell(1, 'title'))
    user.click_cell(user.cell(1, 'originalartist'), Ctrl)
    paste_onto(user, user.cell(1, 'title'))
    qtbot.waitUntil(lambda: in_file(paths[1], 'title') == [['Artist 1']])
    assert in_file(paths[1], 'artist', 'title', 'album', 'originalartist') == [
        ['Artist 2'], ['Artist 1'], ['Album 2'], ['Album 1']]
    assert shown(table, 1, 'title', 'originalartist') == [['Artist 1'], ['Album 1']]


def test_paste_onto_selection_is_not_restarted(user, loaded, qtbot):
    # "the pasting isn't restarted for individual files. ie. If you've
    # copied two fields before, but have four cells selected. The values
    # will only get written to the first two selected cells."
    table, paths = loaded
    user.click_cell(user.cell(0, 'artist'))
    user.click_cell(user.cell(0, 'album'), Ctrl)
    user.press(Key.Key_C, Ctrl)
    for i, field in enumerate(('title', 'album', 'genre', 'comment')):
        user.click_cell(user.cell(1, field), Ctrl if i else Qt.KeyboardModifier.NoModifier)
    user.click_menu('Paste &Onto Selection')
    qtbot.waitUntil(lambda: in_file(paths[1], 'title') == [['Artist 1']])
    assert in_file(paths[1], 'title', 'album', 'genre', 'comment') == [['Artist 1'], ['Album 1'], None, None]


def test_copy_all_fields_as_text(user, loaded, qtbot):
    # "Copies the complete tag of the selected files": the clipboard's text
    # holds it as JSON, only to support pasting outside of puddletag (code
    # comment).
    table, paths = loaded
    tag = audioinfo.Tag(str(paths[0]))
    tag.update({'genre': ['Genre 1'], '__image': [{'data': JPEG, 'mime': 'image/jpeg'}]})
    tag.save()
    user.press(Key.Key_F5)  # Refresh, to read the cover
    qtbot.waitUntil(lambda: bool(table.model().taginfo[0].images))
    user.activate()  # the loading window took the activation
    user.click_cell(user.cell(0, 'title'))
    user.press(Key.Key_C, Ctrl | Shift)
    [copied] = json.loads(QApplication.clipboard().text())
    assert copied['artist'] == ['Artist 1']
    assert copied['genre'] == ['Genre 1']
    assert [base64.b64decode(image['data']) for image in copied['__image']] == [JPEG]


OLD_TAGS_TYPE = 'application/x.puddletag.tags'
TAGS_TYPE = 'application/x.puddletag.tags+json'


def with_big_cover(user, qtbot, table, path):
    tag = audioinfo.Tag(str(path))
    tag.update({'__image': [{'data': BIG_JPEG, 'mime': 'image/jpeg'}]})
    tag.save()
    user.press(Key.Key_F5)  # Refresh, to read the cover
    qtbot.waitUntil(lambda: bool(table.model().taginfo[0].images))
    user.activate()  # the loading window took the activation


def answer_large_copy(monkeypatch, qtbot, button):
    """Runs the 5 MiB question for real and, from inside its event loop,
    clicks the button with this text, or presses Esc for 'Esc'. Returns
    the list the question's text is put in."""
    monkeypatch.setattr(QMessageBox, 'exec', lambda self: REAL_EXEC(self))
    shown = []

    def pick(tries=200):
        box = QApplication.activeModalWidget()
        if not isinstance(box, QMessageBox):
            if tries:
                QTimer.singleShot(10, lambda: pick(tries - 1))
            return
        shown.append(box.text())
        if button == 'Esc':
            qtbot.keyClick(box, Key.Key_Escape)
        else:
            [found] = [b for b in box.buttons() if b.text() == button]
            qtbot.mouseClick(found, Qt.MouseButton.LeftButton)

    QTimer.singleShot(0, pick)
    return shown


@pytest.mark.parametrize('clipboard', ['empty', 'text from another program'])
def test_paste_with_nothing_copied_writes_nothing(user, loaded, qtbot, dialogs, clipboard):
    # "Pastes the copied/cut fields onto the selected files": with nothing
    # copied by puddletag there is nothing to paste.
    table, paths = loaded
    if clipboard != 'empty':
        QApplication.clipboard().setText('Synthetic text')
    user.click_cell(user.cell(3, 'title'))
    for paste in (by_key(Key.Key_V), by_key(Key.Key_Insert, Shift), by_menu('Paste &Onto Selection')):
        paste(user, None)
        qtbot.wait(200)
    assert in_file(paths[3], 'artist', 'title', 'album') == [['Artist 4'], ['Title 4'], ['Album 4']]
    assert dialogs.calls == []
    assert not user.action('&Undo').isEnabled()


@pytest.mark.parametrize('button', ['&Yes', 'No', 'Copy without images.', 'Esc'])
def test_copy_all_fields_over_5_mib(user, loaded, qtbot, monkeypatch, button):
    # "Copies the complete tag of the selected files": over 5 MiB of data
    # puddletag asks first (synthetic cover); Yes copies everything, No
    # nothing, and "Copy without images." the fields only.
    table, paths = loaded
    with_big_cover(user, qtbot, table, paths[0])
    user.click_cell(user.cell(0, 'title'))
    shown = answer_large_copy(monkeypatch, qtbot, button)
    user.press(Key.Key_C, Ctrl | Shift)
    qtbot.waitUntil(lambda: bool(shown))
    assert shown == [LARGE]
    user.activate()  # the question took the activation
    clipboard = QApplication.clipboard()
    if button in ('No', 'Esc'):
        assert clipboard.text() == ''
        # An empty clipboard has no mime data at all.
        assert clipboard.mimeData() is None or not clipboard.mimeData().hasFormat(TAGS_TYPE)
        return
    [copied] = json.loads(clipboard.text())
    assert copied['artist'] == ['Artist 1']
    if button == '&Yes':
        assert [base64.b64decode(image['data']) for image in copied['__image']] == [BIG_JPEG]
    else:
        assert '__image' not in copied
    user.click_cell(user.cell(2, 'title'))
    user.press(Key.Key_V, Ctrl)
    qtbot.waitUntil(lambda: in_file(paths[2], 'artist') == [['Artist 1']], timeout=10000)
    covers = [image['data'] for image in audioinfo.Tag(str(paths[2])).images]
    assert covers == ([BIG_JPEG] if button == '&Yes' else [])


def test_copy_all_fields_over_5_mib_with_no_button_clicked(user, loaded, qtbot, dialogs):
    # Synthetic: the dialog guard's stand-in for the question returns
    # without a click. The same as No: nothing is copied.
    table, paths = loaded
    with_big_cover(user, qtbot, table, paths[0])
    user.click_cell(user.cell(0, 'title'))
    dialogs.answer('QMessageBox.exec', None)
    user.press(Key.Key_C, Ctrl | Shift)
    assert QApplication.clipboard().text() == ''


def test_paste_runs_no_code_from_the_clipboard(user, loaded, qtbot, tmp_path):
    # Synthetic payload. Data on the clipboard is read, not run: any
    # program can put data under puddletag's type.
    table, paths = loaded
    marker = tmp_path / 'ran'

    class Payload:
        def __reduce__(self):
            return (Path.touch, (marker,))

    mime = QMimeData()
    for name in (OLD_TAGS_TYPE, TAGS_TYPE):
        mime.setData(name, pickle.dumps([Payload()]))
    QApplication.clipboard().setMimeData(mime)
    user.click_cell(user.cell(3, 'title'))
    user.press(Key.Key_V, Ctrl)
    qtbot.wait(200)
    assert not marker.exists()
    assert in_file(paths[3], 'artist', 'title') == [['Artist 4'], ['Title 4']]


def test_paste_between_two_puddletags(user, loaded, qtbot):
    # "Pastes the copied/cut fields onto the selected files": what another
    # puddletag put on the clipboard is whatever formats it set, so they are
    # carried over as they are.
    table, paths = loaded
    select(user, (0, 'artist'), (0, 'title'))
    user.press(Key.Key_C, Ctrl)
    mime = QApplication.clipboard().mimeData()
    other = QMimeData()
    for name in mime.formats():
        other.setData(name, mime.data(name))
    QApplication.clipboard().clear()
    QApplication.clipboard().setMimeData(other)
    select(user, (3, 'artist'), (3, 'title'))
    user.press(Key.Key_V, Ctrl)
    written(user, qtbot, lambda: in_file(paths[3], 'artist', 'title') == [['Artist 1'], ['Title 1']])
