"""Preview Mode (menus.txt: "When enabled any changes you make will not get
written"), run as a user runs it: the Preview Mode menu, its shortcuts and
the switch in the status bar. Each change is checked in the table and in
the files. Synthetic files.
"""
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox

from puddlestuff import audioinfo
from puddlestuff.mainwin.storedtags import StoredTags
from puddlestuff.mainwin.tagpanel import FrameCombo
from puddlestuff.puddlesettings import SettingsDialog
from puddlestuff.puddletag import PreviewLabel

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier
Yes = QMessageBox.StandardButton.Yes
No = QMessageBox.StandardButton.No


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    music = tmp_path / 'music'
    paths = [make_audio(f'0{i}.mp3', music, artist=f'Artist {i}', title=f'Title {i}')
             for i in (1, 2, 3)]
    mainwin.openDir(str(music), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == 3)
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]
    user.activate()
    table.setFocus()
    return table, paths


def in_file(path):
    return audioinfo.usertags(audioinfo.Tag(str(path)))


def titles_in_files(paths):
    return [in_file(p)['title'] for p in paths]


def shown(user, row, field):
    """A cell's text and how it's shown: bold, italic or plain."""
    model = user.table.model()
    index = user.cell(row, field)
    font = model.data(index, Qt.ItemDataRole.FontRole)
    return model.data(index), 'bold' if font.bold() else 'italic' if font.italic() else 'plain'


def edit(user, qtbot, row, field, text):
    """Types text into the row's cell."""
    user.double_click_cell(user.cell(row, field))
    QApplication.focusWidget().selectAll()
    user.type(text)
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: shown(user, row, field)[0] == text)
    user.press(Key.Key_Escape)  # the next row's cell, which Enter opened


def switch(mainwin):
    """The status bar's Preview Mode: On/Off."""
    [label] = mainwin.findChildren(PreviewLabel)
    return label


def preview_mode(mainwin):
    return 'Preview Mode: On' in switch(mainwin).text()


def double_click_switch(user, mainwin):
    label = switch(mainwin)
    user.double_click(label, label.rect().center())


def toggle(user):
    user.press(Key.Key_P, Ctrl | Shift)


def undo_enabled(user):
    return user.action('&Undo').isEnabled()


# "When enabled any changes you make will not get written. Instead any
# values you change that differ from the original will be shown as
# emboldened text in the File-View" (menus.txt), whichever way it's
# enabled.

ENABLE = {
    'Preview Mode menu': lambda user, mainwin: user.click_menu('Enabl&e Preview Mode'),
    'Ctrl+Shift+P': lambda user, mainwin: toggle(user),
    'status bar': double_click_switch,
}


@pytest.mark.parametrize('enable', ENABLE.values(), ids=ENABLE.keys())
def test_edit_is_shown_not_written(mainwin, user, loaded, qtbot, enable):
    table, paths = loaded
    assert not preview_mode(mainwin)
    enable(user, mainwin)
    assert preview_mode(mainwin)
    edit(user, qtbot, 0, 'title', 'New')
    assert shown(user, 0, 'title') == ('New', 'bold')
    assert in_file(paths[0])['title'] == ['Title 1']


# Enabled with its shortcut and disabled each way: edits are written
# again.

DISABLE = {
    'Preview Mode menu': lambda user, mainwin: user.click_menu('Disabl&e Preview Mode'),
    'Ctrl+Shift+P': lambda user, mainwin: toggle(user),
    'status bar': double_click_switch,
}


@pytest.mark.parametrize('disable', [
    pytest.param(disable, id=name, marks=pytest.mark.xfail(
        name == 'status bar', strict=True,
        reason="after Ctrl+Shift+P, the switch's double-click enables Preview Mode again"))
    for name, disable in DISABLE.items()])
def test_disable(mainwin, user, loaded, qtbot, disable):
    table, paths = loaded
    toggle(user)
    assert preview_mode(mainwin)
    disable(user, mainwin)
    assert not preview_mode(mainwin)
    edit(user, qtbot, 0, 'title', 'New')
    qtbot.waitUntil(lambda: in_file(paths[0])['title'] == ['New'])
    assert shown(user, 0, 'title') == ('New', 'plain')


def test_value_set_back_in_italics(mainwin, user, loaded, qtbot):
    # "Values that you've changed, but are the same as the underlying value
    # will be shown in italics."
    table, paths = loaded
    toggle(user)
    edit(user, qtbot, 0, 'title', 'New')
    edit(user, qtbot, 0, 'title', 'Title 1')
    assert shown(user, 0, 'title') == ('Title 1', 'italic')


# "If preview mode has been enabled and some changes were made, they'll get
# written to the files, and Preview Mode is disabled."

WRITE = {
    'Preview Mode menu': lambda user: user.click_menu('&Write Previews'),
    'Ctrl+W': lambda user: user.press(Key.Key_W, Ctrl),
}


@pytest.mark.parametrize('write', WRITE.values(), ids=WRITE.keys())
def test_write_previews(mainwin, user, loaded, qtbot, write):
    table, paths = loaded
    toggle(user)
    edit(user, qtbot, 0, 'title', 'New 1')
    edit(user, qtbot, 1, 'title', 'New 2')
    write(user)
    qtbot.waitUntil(lambda: titles_in_files(paths) == [['New 1'], ['New 2'], ['Title 3']])
    user.activate()
    assert not preview_mode(mainwin)
    assert [shown(user, row, 'title') for row in (0, 1)] == [('New 1', 'plain'), ('New 2', 'plain')]


# "Clear Selected Files: Clears the selected files' previews."

CLEAR_FILES = {
    'Preview Mode menu': lambda user: user.click_menu('Clear Selected &Files'),
    'Ctrl+Shift+F': lambda user: user.press(Key.Key_F, Ctrl | Shift),
}


@pytest.mark.parametrize('clear', CLEAR_FILES.values(), ids=CLEAR_FILES.keys())
def test_clear_selected_files(mainwin, user, loaded, qtbot, clear):
    table, paths = loaded
    toggle(user)
    edit(user, qtbot, 0, 'title', 'New 1')
    edit(user, qtbot, 1, 'title', 'New 2')
    user.click_cell(user.cell(0, 'artist'))
    clear(user)
    assert [shown(user, row, 'title') for row in (0, 1)] == [('Title 1', 'plain'), ('New 2', 'bold')]
    assert titles_in_files(paths) == [['Title 1'], ['Title 2'], ['Title 3']]


def test_clear_selected_cells(mainwin, user, loaded, qtbot):
    # "Clears the selected cells' previews."
    table, paths = loaded
    toggle(user)
    edit(user, qtbot, 0, 'title', 'New title')
    edit(user, qtbot, 0, 'artist', 'New artist')
    user.click_cell(user.cell(0, 'title'))
    user.click_menu('Clear Selected &Cells')
    assert [shown(user, 0, field) for field in ('title', 'artist')] == [('Title 1', 'plain'),
                                                                        ('New artist', 'bold')]


# "Undo Last Clear: If you've cleared any previews (but not exited Preview
# Mode), the last one will be undone."

UNDO_CLEAR = {
    'Preview Mode menu': lambda user: user.click_menu('&Undo Last Clear'),
    'Ctrl+Shift+Z': lambda user: user.press(Key.Key_Z, Ctrl | Shift),
}


@pytest.mark.parametrize('undo_clear', UNDO_CLEAR.values(), ids=UNDO_CLEAR.keys())
def test_undo_last_clear(mainwin, user, loaded, qtbot, undo_clear):
    table, paths = loaded
    toggle(user)
    edit(user, qtbot, 0, 'title', 'New 1')
    edit(user, qtbot, 1, 'title', 'New 2')
    for row in (0, 1):
        user.click_cell(user.cell(row, 'artist'))
        user.press(Key.Key_F, Ctrl | Shift)
    undo_clear(user)
    assert [shown(user, row, 'title') for row in (0, 1)] == [('Title 1', 'plain'), ('New 2', 'bold')]


def save_in_tag_panel(user, mainwin, row, field, text, key=Key.Key_S, modifier=Ctrl):
    """Selects the row, types over the field in the Tag Panel and saves:
    Ctrl+S, or the key given."""
    user.click_cell(user.cell(row, field))
    [panel] = mainwin.findChildren(FrameCombo)
    user.click(panel.combos[field].lineEdit())
    user.press(Key.Key_A, Ctrl)
    user.type(text)
    user.press(key, modifier)


TAG_PANEL_SAVE = {'Ctrl+S': (Key.Key_S, Ctrl), 'Enter': (Key.Key_Return, Qt.KeyboardModifier.NoModifier)}


@pytest.mark.parametrize('key, modifier', TAG_PANEL_SAVE.values(), ids=TAG_PANEL_SAVE.keys())
def test_tag_panel_save_updates_the_preview(mainwin, user, loaded, qtbot, key, modifier):
    # menus.txt, Save: "if previews have been enabled ... nothing will get
    # written. Only the preview will get updated." Enter in the field saves
    # too.
    table, paths = loaded
    toggle(user)
    save_in_tag_panel(user, mainwin, 0, 'title', 'Panel', key, modifier)
    assert shown(user, 0, 'title') == ('Panel', 'bold')
    assert in_file(paths[0])['title'] == ['Title 1']


@pytest.mark.parametrize('key, modifier', [
    pytest.param(*keys, id=name, marks=pytest.mark.xfail(
        name == 'Enter', strict=True, reason="#378: the rebuilt fields don't save previews"))
    for name, keys in TAG_PANEL_SAVE.items()])
def test_tag_panel_after_preferences(mainwin, user, loaded, qtbot, key, modifier):
    # #378: in Preview Mode, after Preferences' OK, "In the Tag Panel, try
    # to change any tag: the tag will revert back to the previous value".
    table, paths = loaded
    toggle(user)
    user.click_menu('&Preferences')
    qtbot.waitUntil(lambda: any(w.isVisible() for w in mainwin.findChildren(SettingsDialog)))
    [window] = [w for w in mainwin.findChildren(SettingsDialog) if w.isVisible()]
    user.activate(window)
    user.click(window.okbuttons.okButton)
    qtbot.waitUntil(lambda: not window.isVisible())
    user.activate()
    save_in_tag_panel(user, mainwin, 0, 'title', 'Panel', key, modifier)
    assert shown(user, 0, 'title') == ('Panel', 'bold')
    assert in_file(paths[0])['title'] == ['Title 1']


# "Deleting tags is not allowed from within Preview Mode."

DELETE_TAGS = {
    'Remove Tag (Ctrl+R)': lambda user: user.press(Key.Key_R, Ctrl),
    'Tag Tools menu': lambda user: user.click_menu('Remove ID3v&2 Tag'),
}


@pytest.mark.parametrize('delete', DELETE_TAGS.values(), ids=DELETE_TAGS.keys())
def test_deleting_tags_refused(mainwin, user, loaded, qtbot, dialogs, delete):
    table, paths = loaded
    toggle(user)
    user.click_cell(user.cell(0, 'title'))
    dialogs.answer('QMessageBox.information', QMessageBox.StandardButton.Ok)
    delete(user)
    [(name, (parent, title, message), kwargs)] = dialogs.calls
    assert message == 'Disable Preview Mode first to enable tag deletion.'
    assert (in_file(paths[0])['artist'], in_file(paths[0])['title']) == (['Artist 1'], ['Title 1'])
    assert shown(user, 0, 'title') == ('Title 1', 'plain')


def test_tooltip_shows_both_values(mainwin, user, loaded, qtbot):
    # preferences.txt: "When in Preview Mode the tooltip will show both the
    # Preview and value as stored in the file, when they differ."
    table, paths = loaded
    toggle(user)
    edit(user, qtbot, 0, 'title', 'New')
    edit(user, qtbot, 1, 'title', 'Title 2')
    model = table.model()
    tooltips = [model.data(user.cell(row, 'title'), Qt.ItemDataRole.ToolTipRole) for row in (0, 1)]
    assert tooltips == ['Preview: New\nReal: Title 1', 'Title 2']


def test_stored_tags_show_the_file(mainwin, user, loaded, qtbot):
    # menus.txt: "The Stored Tags dialog displays the Tags of the currently
    # selected files as stored on disk. Useful for when you have previews".
    table, paths = loaded
    user.click_menu('Stored Tags')
    [stored] = mainwin.findChildren(StoredTags)
    qtbot.waitUntil(stored.isVisible)
    labels = lambda: [label.text() for label in stored.findChildren(QLabel)]
    toggle(user)
    edit(user, qtbot, 0, 'title', 'New')
    user.click_cell(user.cell(1, 'title'))
    qtbot.waitUntil(lambda: 'Title 2' in labels())
    user.click_cell(user.cell(0, 'title'))
    qtbot.waitUntil(lambda: 'Title 1' in labels())
    assert 'New' not in labels()


@pytest.mark.parametrize('answer, still_on, title', [(Yes, False, ('Title 1', 'plain')),
                                                     (No, True, ('New', 'bold'))])
def test_disabling_with_previews_asks(mainwin, user, loaded, qtbot, dialogs, answer, still_on, title):
    # menus.txt: "If some files have previews that haven't been written,
    # disabling Preview Mode first asks whether to discard them."
    table, paths = loaded
    toggle(user)
    edit(user, qtbot, 0, 'title', 'New')
    dialogs.answer('QMessageBox.question', answer)
    toggle(user)
    [(name, (parent, caption, message), kwargs)] = dialogs.calls
    assert message == 'Do you want to exit Preview Mode? Unsaved changes will be discarded'
    assert preview_mode(mainwin) == still_on
    assert shown(user, 0, 'title') == title
    assert in_file(paths[0])['title'] == ['Title 1']


# menus.txt: "In Preview Mode, Undo undoes the changes made to the
# previews, one at a time. Edits written to files before Preview Mode was
# enabled can be undone once it's disabled again. Disabling Preview Mode
# forgets the previews' undo history."

def test_undo_steps_back_the_previews(mainwin, user, loaded, qtbot):
    # Back to the file's value, which then shows in italics.
    table, paths = loaded
    toggle(user)
    edit(user, qtbot, 0, 'title', 'First')
    edit(user, qtbot, 0, 'title', 'Second')
    after_each = []
    for i in range(2):
        user.press(Key.Key_Z, Ctrl)
        after_each.append(shown(user, 0, 'title'))
    assert after_each == [('First', 'bold'), ('Title 1', 'italic')]
    assert not undo_enabled(user)
    assert in_file(paths[0])['title'] == ['Title 1']


def test_file_edits_wait_until_preview_mode_is_off(mainwin, user, loaded, qtbot):
    table, paths = loaded
    edit(user, qtbot, 0, 'title', 'New')
    qtbot.waitUntil(lambda: in_file(paths[0])['title'] == ['New'])
    toggle(user)
    user.press(Key.Key_Z, Ctrl)
    assert (in_file(paths[0])['title'], shown(user, 0, 'title')) == (['New'], ('New', 'plain'))
    toggle(user)
    user.press(Key.Key_Z, Ctrl)
    assert (in_file(paths[0])['title'], shown(user, 0, 'title')) == (['Title 1'], ('Title 1', 'plain'))


def test_disabling_forgets_the_preview_history(mainwin, user, loaded, qtbot, dialogs):
    table, paths = loaded
    toggle(user)
    edit(user, qtbot, 0, 'title', 'New')
    assert undo_enabled(user)
    dialogs.answer('QMessageBox.question', Yes)
    toggle(user)
    assert not undo_enabled(user)


def test_one_undo_takes_back_write_previews(mainwin, user, loaded, qtbot):
    # Write Previews: "A single Undo then undoes the whole write."
    table, paths = loaded
    toggle(user)
    edit(user, qtbot, 0, 'title', 'New 1')
    edit(user, qtbot, 1, 'title', 'New 2')
    user.press(Key.Key_W, Ctrl)
    qtbot.waitUntil(lambda: titles_in_files(paths) == [['New 1'], ['New 2'], ['Title 3']])
    user.activate()
    user.press(Key.Key_Z, Ctrl)
    assert titles_in_files(paths) == [['Title 1'], ['Title 2'], ['Title 3']]
    assert not undo_enabled(user)
