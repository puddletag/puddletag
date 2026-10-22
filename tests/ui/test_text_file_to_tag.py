"""Text File→Tag and Clipboard→Tag (the Convert menu and the Tools toolbar,
menus.txt, tut2.txt), run as a user runs them. Text File→Tag "Asks you to
open a Text File with which you can then use patterns to extract tags";
Clipboard→Tag "Uses the same dialog as Text File->Tag, but preloaded with
text from the clipboard". Each result is checked in the files and in the
table. Synthetic files and text.
"""
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox, QPushButton

from puddlestuff import audioinfo
from puddlestuff.helperwin import ImportTextFile

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier

LINES = 'Artist 1 - Song 1\nArtist 2 - Song 2\nArtist 3 - Song 3\n'
IMPORTED = [[['Artist 1'], ['Song 1']], [['Artist 2'], ['Song 2']], [['Artist 3'], ['Song 3']]]
UNCHANGED = [[None, ['Title 1']], [None, ['Title 2']], [None, ['Title 3']]]

TEXT_FILE_TO_TAG = {
    'Convert menu': lambda user: user.click_menu('&Text File->Tag'),
    'toolbar': lambda user: user.click_toolbar('&Text File->Tag'),
}


@pytest.fixture(autouse=True)
def empty_clipboard():
    """The clipboard is the whole app's: a test would otherwise read what
    the one before it copied."""
    QApplication.clipboard().clear()


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    """Three MP3s with only a title."""
    music = tmp_path / 'music'
    paths = [make_audio(f'0{i}.mp3', music, title=f'Title {i}') for i in (1, 2, 3)]
    mainwin.openDir(str(music), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == 3)
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]
    user.activate()
    table.setFocus()
    return table, paths


def text_file(tmp_path, text, name='tracks.txt'):
    """A synthetic text file, next to the music folder."""
    path = tmp_path / name
    path.write_text(text, encoding='utf-8')
    return path


def import_window(qtbot):
    """The open Text File->Tag window. Its parent isn't the main window, so
    it's looked for among the top-level windows."""
    def shown():
        return [w for w in QApplication.topLevelWidgets() if isinstance(w, ImportTextFile) and w.isVisible()]
    qtbot.waitUntil(lambda: len(shown()) == 1)
    [window] = shown()
    return window


def open_text_file(user, qtbot, dialogs, path, text_file_to_tag=TEXT_FILE_TO_TAG['Convert menu']):
    """Runs Text File->Tag and picks the file in the file dialog it opens
    first."""
    dialogs.answer('QFileDialog.getOpenFileName', (str(path), ''))
    text_file_to_tag(user)
    window = import_window(qtbot)
    user.activate(window)
    return window


def set_pattern(user, window, pattern):
    """Types the pattern over the window's. Delete drops the rest of a saved
    pattern that the box completes the typed text to."""
    user.click(window.patterncombo.lineEdit())
    user.press(Key.Key_A, Ctrl)
    user.type(pattern)
    user.press(Key.Key_Delete)
    assert window.patterncombo.currentText() == pattern


def in_files(paths):
    return [[audioinfo.Tag(str(p)).get(field) for field in ('artist', 'title')] for p in paths]


def in_table(table):
    return [[audio.get(field) for field in ('artist', 'title')] for audio in table.model().taginfo]


def written(user, qtbot, paths, expected):
    """Several files are written in a thread, behind a progress window."""
    qtbot.waitUntil(lambda: in_files(paths) == expected)
    user.activate()


@pytest.mark.parametrize('text_file_to_tag', TEXT_FILE_TO_TAG.values(), ids=TEXT_FILE_TO_TAG.keys())
def test_text_file_to_tag(user, loaded, qtbot, dialogs, tmp_path, text_file_to_tag):
    # menus.txt: "Asks you to open a Text File with which you can then use
    # patterns to extract tags." tut2.txt: "obtaining the tags from each
    # line in the file in exactly the same way as extracting tags from
    # filenames" and "Clicking OK will write the tags to the selected
    # files." Synthetic files and text.
    table, paths = loaded
    user.press(Key.Key_A, Ctrl)
    window = open_text_file(user, qtbot, dialogs, text_file(tmp_path, LINES), text_file_to_tag)
    assert [name for name, args, kwargs in dialogs.calls] == ['QFileDialog.getOpenFileName']
    assert window.file.toPlainText() == LINES
    set_pattern(user, window, '%artist% - %title%')
    user.click(window.ok)
    written(user, qtbot, paths, IMPORTED)
    assert not window.isVisible()
    assert in_table(table) == IMPORTED


def test_edit_the_text(user, loaded, qtbot, dialogs, tmp_path):
    # tut2.txt: "Editing the text on the left will change the tags, but
    # editing the tags themselves will not." Synthetic files and text.
    table, paths = loaded
    user.press(Key.Key_A, Ctrl)
    window = open_text_file(user, qtbot, dialogs, text_file(tmp_path, 'Artist 1 - Song 1\nArtist 2 - Song 2'))
    set_pattern(user, window, '%artist% - %title%')
    user.click(window.file)
    user.press(Key.Key_End, Ctrl)
    user.press(Key.Key_Return)
    user.type('Artist 3 - Song 3')
    user.click(window.tags)
    user.press(Key.Key_End, Ctrl)
    user.type(' extra')
    user.click(window.ok)
    written(user, qtbot, paths, IMPORTED)
    assert in_table(table) == IMPORTED


def test_selected_files_only(user, loaded, qtbot, dialogs, tmp_path):
    # tut2.txt: "Clicking OK will write the tags to the selected files."
    # Synthetic files and text.
    table, paths = loaded
    user.click_cell(user.cell(1, 'title'))
    user.click_cell(user.cell(2, 'title'), Shift)
    window = open_text_file(user, qtbot, dialogs, text_file(tmp_path, 'Artist 1 - Song 1\nArtist 2 - Song 2\n'))
    set_pattern(user, window, '%artist% - %title%')
    user.click(window.ok)
    expected = [[None, ['Title 1']], [['Artist 1'], ['Song 1']], [['Artist 2'], ['Song 2']]]
    written(user, qtbot, paths, expected)
    assert in_table(table) == expected


def test_open_a_different_file(user, loaded, qtbot, dialogs, tmp_path):
    # tut2.txt: "You have the option of opening a different file and
    # obtaining the tags from each line in the file in exactly the same way
    # as extracting tags from filenames." Synthetic files and text.
    table, paths = loaded
    first = text_file(tmp_path, 'Wrong - Wrong\n' * 3, 'first.txt')
    second = text_file(tmp_path, LINES, 'second.txt')
    user.press(Key.Key_A, Ctrl)
    window = open_text_file(user, qtbot, dialogs, first)
    assert window.openfile.text() == '&Select File'
    dialogs.answer('QFileDialog.getOpenFileName', (str(second), ''))
    user.click(window.openfile)
    assert window.file.toPlainText() == LINES
    set_pattern(user, window, '%artist% - %title%')
    user.click(window.ok)
    written(user, qtbot, paths, IMPORTED)
    assert in_table(table) == IMPORTED


def test_clipboard_to_tag(user, loaded, qtbot, dialogs):
    # menus.txt: "Uses the same dialog as Text File->Tag, but preloaded with
    # text from the clipboard." Synthetic files and text.
    table, paths = loaded
    QApplication.clipboard().setText(LINES)  # as if copied in another program
    user.press(Key.Key_A, Ctrl)
    user.click_menu('&Clipboard->Tag')
    window = import_window(qtbot)
    user.activate(window)
    assert dialogs.calls == []
    assert window.file.toPlainText() == LINES
    set_pattern(user, window, '%artist% - %title%')
    user.click(window.ok)
    written(user, qtbot, paths, IMPORTED)
    assert in_table(table) == IMPORTED


def test_preview_mode(user, loaded, qtbot, dialogs, tmp_path):
    # menus.txt: "When enabled any changes you make will not get written.
    # Instead any values you change that differ from the original will be
    # shown as emboldened text in the File-View". Synthetic files and text.
    table, paths = loaded
    user.press(Key.Key_A, Ctrl)
    user.press(Key.Key_P, Ctrl | Shift)
    assert table.model().previewMode
    window = open_text_file(user, qtbot, dialogs, text_file(tmp_path, LINES))
    set_pattern(user, window, '%artist% - %title%')
    user.click(window.ok)
    qtbot.waitUntil(lambda: table.model().data(user.cell(0, 'artist')) == 'Artist 1')
    assert table.model().data(user.cell(2, 'title')) == 'Song 3'
    assert table.model().data(user.cell(0, 'artist'), Qt.ItemDataRole.FontRole).bold()
    assert in_files(paths) == UNCHANGED


def test_commands_need_a_selection(user, loaded):
    # tut2.txt: "Clicking OK will write the tags to the selected files."
    # Both commands are enabled by the selection. Synthetic files.
    table, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    assert user.action('&Text File->Tag').isEnabled()
    assert user.action('&Clipboard->Tag').isEnabled()
    user.click_cell(user.cell(0, 'title'), Ctrl)
    assert table.selectedRows == []
    assert not user.action('&Text File->Tag').isEnabled()
    assert not user.action('&Clipboard->Tag').isEnabled()


def test_more_lines_than_files(loaded, tmp_path, qtbot, user, dialogs):
    # Not in the docs; synthetic files and text. A text with more lines than
    # selected files: the extra line is ignored, and no dialog asks about it.
    table, paths = loaded
    user.press(Key.Key_A, Ctrl)
    window = open_text_file(user, qtbot, dialogs, text_file(tmp_path, LINES + 'Artist 4 - Song 4\n'))
    set_pattern(user, window, '%artist% - %title%')
    user.click(window.ok)
    written(user, qtbot, paths, IMPORTED)
    assert in_table(table) == IMPORTED
    assert [name for name, args, kwargs in dialogs.calls] == ['QFileDialog.getOpenFileName']


def test_fewer_lines_than_files(loaded, tmp_path, qtbot, user, dialogs):
    # Not in the docs; synthetic files and text. A text with fewer lines than
    # selected files: the files past the last line keep their tags.
    table, paths = loaded
    user.press(Key.Key_A, Ctrl)
    window = open_text_file(user, qtbot, dialogs, text_file(tmp_path, 'Artist 1 - Song 1\n'))
    set_pattern(user, window, '%artist% - %title%')
    user.click(window.ok)
    expected = [IMPORTED[0], UNCHANGED[1], UNCHANGED[2]]
    written(user, qtbot, paths, expected)
    assert in_table(table) == expected


@pytest.mark.parametrize('line', ['', 'No dash here'], ids=['blank line', 'pattern does not match'])
def test_line_without_tags_leaves_its_file(loaded, tmp_path, qtbot, user, dialogs, line):
    # Not in the docs; synthetic files and text. A blank line, or one the
    # pattern doesn't match, leaves its file as it is, like menus.txt's
    # File->Tag: "A file whose name the pattern doesn't match is left as it
    # is".
    table, paths = loaded
    user.press(Key.Key_A, Ctrl)
    text = f'Artist 1 - Song 1\n{line}\nArtist 3 - Song 3\n'
    window = open_text_file(user, qtbot, dialogs, text_file(tmp_path, text))
    set_pattern(user, window, '%artist% - %title%')
    user.click(window.ok)
    expected = [IMPORTED[0], UNCHANGED[1], IMPORTED[2]]
    written(user, qtbot, paths, expected)
    assert in_table(table) == expected


def test_cancel_the_file_dialog(loaded, qtbot, user, dialogs):
    # Not in the docs; synthetic files and text. Cancelling the file dialog
    # opens no window and writes nothing.
    table, paths = loaded
    user.press(Key.Key_A, Ctrl)
    dialogs.answer('QFileDialog.getOpenFileName', ('', ''))
    user.click_menu('&Text File->Tag')
    qtbot.waitUntil(lambda: len(dialogs.calls) == 1)
    qtbot.wait(100)  # nothing to wait on: no window is expected
    assert not [w for w in QApplication.topLevelWidgets() if isinstance(w, ImportTextFile) and w.isVisible()]
    assert in_files(paths) == UNCHANGED


def test_pattern_is_remembered(loaded, tmp_path, qtbot, user, dialogs):
    # Not in the docs; synthetic files and text. The window opens on the
    # pattern used the last time OK was clicked.
    table, paths = loaded
    user.press(Key.Key_A, Ctrl)
    path = text_file(tmp_path, LINES)
    window = open_text_file(user, qtbot, dialogs, path)
    set_pattern(user, window, '%artist% - %title%')
    user.click(window.ok)
    written(user, qtbot, paths, IMPORTED)
    window = open_text_file(user, qtbot, dialogs, path)
    assert window.patterncombo.currentText() == '%artist% - %title%'
    user.click(window.cancel)
    qtbot.waitUntil(lambda: not window.isVisible())


def test_paste_clipboard_button(loaded, tmp_path, qtbot, user, dialogs):
    # Not in the docs; synthetic files and text. The window's Paste Clipboard
    # button replaces the text with the clipboard's.
    table, paths = loaded
    user.press(Key.Key_A, Ctrl)
    window = open_text_file(user, qtbot, dialogs, text_file(tmp_path, 'Wrong - Wrong\n' * 3))
    QApplication.clipboard().setText(LINES)  # as if copied in another program
    [button] = [b for b in window.findChildren(QPushButton) if b.text() == '&Paste Clipboard']
    user.click(button)
    assert window.file.toPlainText() == LINES
    set_pattern(user, window, '%artist% - %title%')
    user.click(window.ok)
    written(user, qtbot, paths, IMPORTED)
    assert in_table(table) == IMPORTED


def test_empty_clipboard(loaded, qtbot, user):
    # Not in the docs; synthetic files and text. Clipboard->Tag with an empty
    # clipboard opens an empty window, and OK writes nothing.
    table, paths = loaded
    user.press(Key.Key_A, Ctrl)
    user.click_menu('&Clipboard->Tag')
    window = import_window(qtbot)
    assert window.file.toPlainText() == ''
    user.activate(window)
    user.click(window.ok)
    qtbot.waitUntil(lambda: not window.isVisible())
    qtbot.wait(300)  # nothing is written, so there's nothing to wait on
    user.activate()
    assert in_files(paths) == UNCHANGED
    assert in_table(table) == UNCHANGED


@pytest.mark.xfail(strict=True, reason='a text file that is not UTF-8 raises UnicodeDecodeError instead of asking for another file')
def test_text_file_that_is_not_utf8(user, loaded, qtbot, dialogs, tmp_path):
    # menus.txt: "Asks you to open a Text File". The program's own message
    # for a file it can't load is "The file <b>...</b> couldn't be
    # loaded.<br /> Do you want to choose another?". Synthetic Latin-1 file.
    table, paths = loaded
    path = tmp_path / 'latin1.txt'
    path.write_bytes(b'Caf\xe9 - Song\n')
    user.press(Key.Key_A, Ctrl)
    dialogs.answer('QFileDialog.getOpenFileName', (str(path), ''))
    dialogs.answer('QMessageBox.question', QMessageBox.StandardButton.No)
    user.click_menu('&Text File->Tag')
    qtbot.waitUntil(lambda: len(dialogs.calls) == 2)
    assert dialogs.calls[1][0] == 'QMessageBox.question'
    assert "couldn't be loaded" in dialogs.calls[1][1][2]
    assert not [w for w in QApplication.topLevelWidgets() if isinstance(w, ImportTextFile) and w.isVisible()]
    assert in_files(paths) == UNCHANGED


def pick_file(dialogs, path):
    dialogs.answer('QFileDialog.getOpenFileName', (str(path), ''))


# How each command is run, and the answer it needs before its window opens.
COMMANDS = {
    'Clipboard->Tag': (lambda user: user.click_menu('&Clipboard->Tag'), lambda dialogs, path: None),
    'Text File->Tag': (lambda user: user.click_menu('&Text File->Tag'), pick_file),
}


@pytest.mark.xfail(strict=True, reason='the window shows before it is made modal')
@pytest.mark.parametrize('command', COMMANDS.values(), ids=COMMANDS.keys())
def test_window_is_modal(user, loaded, qtbot, dialogs, tmp_path, command):
    # Not in the docs; synthetic files and text. The window blocks the main
    # window while it's open, so the selection it writes to can't change.
    table, paths = loaded
    run, answer = command
    answer(dialogs, text_file(tmp_path, LINES))
    user.press(Key.Key_A, Ctrl)
    run(user)
    window = import_window(qtbot)
    assert QApplication.activeModalWidget() is window
    user.click(window.cancel)
