"""Replace (the Tools menu and Ctrl+H), run as a user runs it. menus.txt:
"Open's the Functions dialog with the Replace function. That is all it
does, nothing more." function.txt, Replace: "It works just as you'd expect
from any text editor. The only caveat is that words are designated by these
,.() ![] characters." Each result is checked in the files and in the table.
Synthetic files.
"""
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QStyle, QStyleOptionButton

from puddlestuff import audioinfo
from puddlestuff.actiondlg import CreateFunction

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier

REPLACE = {
    'Ctrl+H': lambda user: user.press(Key.Key_H, Ctrl),
    'Tools menu': lambda user: user.click_menu('Replace...'),
}


def tags(i):
    return {'album': [f'Album {i}'], 'artist': [f'Artist {i}'], 'title': [f'Song song {i}']}


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
    """Three MP3s, each with an album, an artist and a title."""
    paths = [make_audio(f'0{i}.mp3', tmp_path / 'music', **{field: value[0] for field, value in tags(i).items()})
             for i in (1, 2, 3)]
    return load(mainwin, qtbot, user, paths), paths


def in_files(paths):
    return [audioinfo.usertags(audioinfo.Tag(str(p))) for p in paths]


def in_table(table):
    return [audioinfo.usertags(audio) for audio in table.model().taginfo]


def open_replace(user, qtbot, replace=REPLACE['Ctrl+H']):
    """Runs Replace: the Functions window, and its Replace function."""
    replace(user)
    qtbot.waitUntil(lambda: isinstance(QApplication.activeModalWidget(), CreateFunction))
    window = QApplication.activeModalWidget()
    user.activate(window)
    return window, window.stack.currentWidget()


def fill(user, function, search, replacement):
    """Types over the Replace and With boxes' text. Delete drops anything
    the box completes the typed text to."""
    for control, text in ((function.controls[0], search), (function.controls[1], replacement)):
        user.click(control.combo.lineEdit())
        user.press(Key.Key_A, Ctrl)
        user.type(text)
        user.press(Key.Key_Delete)
        assert control.combo.currentText() == text


def tick(user, box):
    """Clicks the check box's indicator, which flips it. A click at the
    box's center misses a box whose text is short."""
    option = QStyleOptionButton()
    box.initStyleOption(option)
    indicator = box.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, box)
    checked = box.isChecked()
    user.click(box, indicator.center())
    assert box.isChecked() != checked


def written(user, qtbot, check):
    """Several files are written in a thread, behind a progress window."""
    qtbot.waitUntil(check)
    user.activate()


@pytest.mark.parametrize('replace', REPLACE.values(), ids=REPLACE.keys())
def test_replace(loaded, qtbot, user, replace):
    # menus.txt: "Open's the Functions dialog with the Replace function."
    # tut3.txt: "Having __selected as the field will apply the selected
    # function to the selected cells." scripting.txt ($replace): "If
    # matchcase is true, a case-sensitive replace is done": Match Case is
    # off, so song matches Song too. Synthetic files.
    table, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(1, 'title'), Shift)
    window, function = open_replace(user, qtbot, replace)
    assert window.functions.currentText() == 'Replace'
    assert function.tagcombo.currentText() == '__selected'
    fill(user, function, 'song', 'tune')
    user.click(window.okcancel.okButton)
    expected = [dict(tags(1), title=['tune tune 1']), dict(tags(2), title=['tune tune 2']), tags(3)]
    written(user, qtbot, lambda: in_files(paths) == expected)
    assert in_table(table) == expected


def test_match_case(loaded, qtbot, user):
    # scripting.txt ($replace): "If matchcase is true, a case-sensitive
    # replace is done." Synthetic files.
    table, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    window, function = open_replace(user, qtbot)
    fill(user, function, 'song', 'tune')
    tick(user, function.controls[2])
    assert function.controls[2].isChecked()
    user.click(window.okcancel.okButton)
    expected = [dict(tags(1), title=['Song tune 1']), tags(2), tags(3)]
    written(user, qtbot, lambda: in_files(paths) == expected)
    assert in_table(table) == expected


def test_whole_word(mainwin, make_audio, tmp_path, qtbot, user):
    # function.txt: "words are designated by these ,.() ![] characters".
    # scripting.txt: "Whole is true implies that only whole word matches
    # are replaced." Synthetic file.
    path = make_audio('01.mp3', tmp_path / 'music', title='Songbook,song.(song) song!')
    table = load(mainwin, qtbot, user, [path])
    user.click_cell(user.cell(0, 'title'))
    window, function = open_replace(user, qtbot)
    fill(user, function, 'song', 'tune')
    tick(user, function.controls[3])
    user.click(window.okcancel.okButton)
    expected = [{'title': ['Songbook,tune.(tune) tune!']}]
    written(user, qtbot, lambda: in_files([path]) == expected)
    assert in_table(table) == expected


def test_selected_cells(loaded, qtbot, user):
    # tut3.txt: "So if you have the album field selected in one file and
    # artist in another. The function'll be applied to the album field of
    # the first file and artist of the other respectively." Synthetic files.
    table, paths = loaded
    user.click_cell(user.cell(0, 'album'))
    user.click_cell(user.cell(1, 'artist'), Ctrl)
    window, function = open_replace(user, qtbot)
    fill(user, function, ' ', '_')
    user.click(window.okcancel.okButton)
    expected = [dict(tags(1), album=['Album_1']), dict(tags(2), artist=['Artist_2']), tags(3)]
    written(user, qtbot, lambda: in_files(paths) == expected)
    assert in_table(table) == expected


def test_preview_mode(loaded, qtbot, user):
    # menus.txt: "When enabled any changes you make will not get written.
    # Instead any values you change that differ from the original will be
    # shown as emboldened text in the File-View". Synthetic files.
    table, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    user.press(Key.Key_P, Ctrl | Shift)
    assert table.model().previewMode
    window, function = open_replace(user, qtbot)
    fill(user, function, 'song', 'tune')
    user.click(window.okcancel.okButton)
    qtbot.waitUntil(lambda: table.model().data(user.cell(0, 'title')) == 'tune tune 1')
    assert table.model().data(user.cell(0, 'title'), Qt.ItemDataRole.FontRole).bold()
    assert in_files(paths) == [tags(1), tags(2), tags(3)]


def test_replace_needs_a_selection(loaded, user):
    # tut3.txt: "Having __selected as the field will apply the selected
    # function to the selected cells." The command is enabled by
    # filesselected. Synthetic files.
    table, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    assert user.action('Replace...').isEnabled()
    user.click_cell(user.cell(0, 'title'), Ctrl)
    assert table.selectedRows == []
    assert not user.action('Replace...').isEnabled()


def test_replacement_with_the_separator_writes_several_values(mainwin, make_audio, tmp_path, qtbot, user):
    # tut3.txt: "Multiple-valued fields are shown like value1\\value2. Enter
    # a value like that and puddletag will assume you want some multiple
    # values." The artist and the replacement are #873's: " & " replaced
    # with \\ gives two artists.
    path = make_audio('01.mp3', tmp_path / 'music', artist='Brandi Carlile & Dylan LeBlanc')
    table = load(mainwin, qtbot, user, [path])
    user.click_cell(user.cell(0, 'artist'))
    window, function = open_replace(user, qtbot)
    fill(user, function, ' & ', '\\\\')
    user.click(window.okcancel.okButton)
    written(user, qtbot, lambda: in_files([path]) != [{'artist': ['Brandi Carlile & Dylan LeBlanc']}])
    expected = [{'artist': ['Brandi Carlile', 'Dylan LeBlanc']}]
    assert in_files([path]) == expected
    assert in_table(table) == expected


@pytest.mark.parametrize('title, expected', [('song song', 'tune tune'), ('song,song song', 'tune,tune tune')])
def test_whole_word_next_to_another(mainwin, make_audio, tmp_path, qtbot, user, title, expected):
    # function.txt: "It works just as you'd expect from any text editor. The
    # only caveat is that words are designated by these ,.() ![]
    # characters." Synthetic files.
    path = make_audio('01.mp3', tmp_path / 'music', title=title)
    table = load(mainwin, qtbot, user, [path])
    user.click_cell(user.cell(0, 'title'))
    window, function = open_replace(user, qtbot)
    fill(user, function, 'song', 'tune')
    tick(user, function.controls[3])
    user.click(window.okcancel.okButton)
    written(user, qtbot, lambda: in_files([path]) != [{'title': [title]}])
    assert in_files([path]) == [{'title': [expected]}]
    assert in_table(table) == [{'title': [expected]}]


def test_whole_word_in_brackets(mainwin, make_audio, tmp_path, qtbot, user):
    # function.txt: "words are designated by these ,.() ![] characters."
    # Synthetic file.
    path = make_audio('01.mp3', tmp_path / 'music', title='[song]')
    table = load(mainwin, qtbot, user, [path])
    user.click_cell(user.cell(0, 'title'))
    window, function = open_replace(user, qtbot)
    fill(user, function, 'song', 'tune')
    tick(user, function.controls[3])
    user.click(window.okcancel.okButton)
    written(user, qtbot, lambda: in_files([path]) != [{'title': ['[song]']}])
    assert in_files([path]) == [{'title': ['[tune]']}]
    assert in_table(table) == [{'title': ['[tune]']}]


def test_window_opens_on_the_selected_text(loaded, qtbot, user):
    # menus.txt: "Open's the Functions dialog with the Replace function."
    # tut3.txt: "Having __selected as the field will apply the selected
    # function to the selected cells." Not in the docs: the Replace and With
    # boxes start with the selected cell's text, and neither check box is
    # ticked. Synthetic files.
    table, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    window, function = open_replace(user, qtbot)
    assert function.controls[0].combo.currentText() == function.controls[1].combo.currentText() == 'Song song 1'
    assert not function.controls[2].isChecked()
    assert not function.controls[3].isChecked()
    assert function.tagcombo.currentText() == '__selected'
    user.click(window.okcancel.cancelButton)
    assert in_files(paths) == [tags(1), tags(2), tags(3)]
