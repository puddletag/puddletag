"""Preview Mode (menus.txt: "When enabled any changes you make will not get
written"), run as a user runs it: the Preview Mode menu, its shortcuts and
the switch in the status bar. Each change is checked in the table and in
the files. Synthetic files.
"""
import threading

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton

from puddlestuff import audioinfo
from puddlestuff.mainwin.storedtags import StoredTags
from puddlestuff.mainwin.tagpanel import FrameCombo
from puddlestuff.puddleobjects import ProgressWin, PuddleThread
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


@pytest.mark.parametrize('disable', DISABLE.values(), ids=DISABLE.keys())
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


@pytest.mark.parametrize('key, modifier', TAG_PANEL_SAVE.values(), ids=TAG_PANEL_SAVE.keys())
def test_tag_panel_after_preferences(mainwin, user, loaded, qtbot, key, modifier):
    # #378: in Preview Mode, after Preferences' OK, "In the Tag Panel, try
    # to change any tag: the tag will revert back to the previous value".
    table, paths = loaded
    toggle(user)
    window = user.open_preferences()
    user.close_preferences(window)
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


def test_stored_tags_ignore_a_slower_earlier_file(mainwin, user, loaded, qtbot, monkeypatch):
    # menus.txt: "The Stored Tags dialog displays the Tags of the currently
    # selected files as stored on disk". Synthetic: the first file's read is
    # held back so it finishes last, as it can on a busy machine.
    table, paths = loaded
    user.click_menu('Stored Tags')
    [stored] = mainwin.findChildren(StoredTags)
    qtbot.waitUntil(stored.isVisible)
    labels = lambda: [label.text() for label in stored.findChildren(QLabel)]
    release = threading.Event()
    real_tag = audioinfo._Tag

    def held_tag(path, *args, **kwargs):
        if path == str(paths[0]):
            release.wait(10)
        return real_tag(path, *args, **kwargs)

    monkeypatch.setattr(audioinfo, '_Tag', held_tag)
    user.click_cell(user.cell(1, 'title'))
    qtbot.waitUntil(lambda: 'Title 2' in labels())
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(2, 'title'))
    qtbot.waitUntil(lambda: 'Title 3' in labels())
    release.set()
    qtbot.waitUntil(lambda: not any(thread.isRunning() for thread in stored.findChildren(PuddleThread)))
    qtbot.wait(100)
    assert 'Title 3' in labels()
    assert 'Title 1' not in labels()


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


def on_disk(tmp_path):
    return sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob('*'))


ORIGINAL = ['music', 'music/01.mp3', 'music/02.mp3', 'music/03.mp3']


def test_filename_edit_is_shown_not_written(mainwin, user, loaded, qtbot, tmp_path):
    # "When enabled any changes you make will not get written. Instead any
    # values you change that differ from the original will be shown as
    # emboldened text in the File-View" (menus.txt), also for the Filename
    # cell, which renames the file when Preview Mode is off.
    table, paths = loaded
    toggle(user)
    edit(user, qtbot, 0, '__filename', 'new.mp3')
    assert shown(user, 0, '__filename') == ('new.mp3', 'bold')
    assert on_disk(tmp_path) == ORIGINAL
    assert undo_enabled(user)


# "If preview mode has been enabled and some changes were made, they'll get
# written to the files, and Preview Mode is disabled. A single Undo then
# undoes the whole write." (menus.txt) "Editing a Dirname cell renames the
# file's folder, and every file in it moves along. Editing an Extension cell
# renames the file with that extension" (tut3.txt)

RENAMES = {
    'Filename': ('__filename', 'new.mp3', [], [('__filename', 'new.mp3')],
                 ['music', 'music/02.mp3', 'music/03.mp3', 'music/new.mp3']),
    'Extension': ('__ext', 'ogg', [('Extension', '__ext')], [('__filename', '01.ogg'), ('__ext', 'ogg')],
                  ['music', 'music/01.ogg', 'music/02.mp3', 'music/03.mp3']),
    'Dirname': ('__dirname', 'Other', [('Dirname', '__dirname')], [('__dirname', 'Other'), ('__dirpath', 'Other')],
                ['Other', 'Other/01.mp3', 'Other/02.mp3', 'Other/03.mp3']),
}


@pytest.mark.parametrize('field, text, columns, bold, expected', RENAMES.values(), ids=RENAMES.keys())
def test_write_previews_renames(mainwin, user, loaded, qtbot, tmp_path, field, text, columns, bold, expected):
    table, paths = loaded
    table.setHeaderTags(table.model().headerdata + columns)
    toggle(user)
    edit(user, qtbot, 0, field, text)
    new_name = {'__filename': 'new.mp3', '__ext': '01.ogg', '__dirname': '01.mp3'}[field]
    new_folder = tmp_path / ('Other' if field == '__dirname' else 'music')
    # The folder's full path is shown for Dirname
    bold = [(name, str(tmp_path / value) if name == '__dirpath' else value) for name, value in bold]
    assert [shown(user, 0, name) for name, value in bold] == [(value, 'bold') for name, value in bold]
    assert on_disk(tmp_path) == ORIGINAL
    user.press(Key.Key_W, Ctrl)
    qtbot.waitUntil(lambda: on_disk(tmp_path) == expected)
    user.activate()
    assert not preview_mode(mainwin)
    rows = [audio.filepath for audio in table.model().taginfo]
    if field == '__dirname':
        assert rows == [str(new_folder / name) for name in ('01.mp3', '02.mp3', '03.mp3')]
    else:
        assert rows[0] == str(new_folder / new_name)
    user.click_toolbar('&Undo')
    qtbot.waitUntil(lambda: on_disk(tmp_path) == ORIGINAL)
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]
    assert not undo_enabled(user)


def test_dirpath_typing_dropped_in_preview_mode(mainwin, user, loaded, qtbot):
    # "Some cells show file information that can't be changed, such as
    # Length, Bitrate and Dirpath: what you type in them is dropped."
    table, paths = loaded
    toggle(user)
    user.double_click_cell(user.cell(0, '__dirpath'))
    QApplication.focusWidget().selectAll()
    user.type('/elsewhere')
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: table.indexWidget(user.cell(1, '__dirpath')) is not None)
    user.press(Key.Key_Escape)
    assert shown(user, 0, '__dirpath') == (str(paths[0].parent), 'plain')
    assert table.model().taginfo[0].preview == {}
    assert not undo_enabled(user)


def test_tag_to_file_in_preview_mode(mainwin, user, loaded, qtbot, tmp_path):
    # "When enabled any changes you make will not get written. Instead any
    # values you change that differ from the original will be shown as
    # emboldened text in the File-View" (menus.txt): the new file name is
    # one of those changes.
    table, paths = loaded
    toggle(user)
    user.click_cell(user.cell(0, 'title'))
    user.press(Key.Key_F8)
    user.type('%title%')
    user.press(Key.Key_F8)
    user.press(Key.Key_F, Ctrl)
    qtbot.waitUntil(lambda: shown(user, 0, '__filename')[0] == 'Title 1.mp3')
    assert shown(user, 0, '__filename') == ('Title 1.mp3', 'bold')
    assert on_disk(tmp_path) == ORIGINAL
    user.press(Key.Key_W, Ctrl)
    qtbot.waitUntil(lambda: 'music/Title 1.mp3' in on_disk(tmp_path))


def test_undo_of_a_field_the_file_lacks(mainwin, user, loaded, qtbot):
    # "In Preview Mode, Undo undoes the changes made to the previews, one at
    # a time." No file has a comment.
    table, paths = loaded
    toggle(user)
    edit(user, qtbot, 0, 'comment', 'Note')
    assert shown(user, 0, 'comment') == ('Note', 'bold')
    user.activate()
    user.press(Key.Key_Z, Ctrl)
    assert table.model().data(user.cell(0, 'comment')) is None
    assert table.model().taginfo[0].preview == {}
    assert 'comment' not in in_file(paths[0])


def test_filename_set_back(mainwin, user, loaded, qtbot):
    # "Values that you've changed, but are the same as the underlying value
    # will be shown in italics." (menus.txt)
    table, paths = loaded
    toggle(user)
    edit(user, qtbot, 0, '__filename', 'new.mp3')
    user.activate()
    table.setFocus()
    edit(user, qtbot, 0, '__filename', '01.mp3')
    assert shown(user, 0, '__filename') == ('01.mp3', 'italic')


def test_emptying_a_changed_cell_previews_the_removal(mainwin, user, loaded, qtbot):
    # "Empty a cell to remove that field from the file." (tut3.txt) In
    # Preview Mode the removal is shown in bold until it is written
    # (menus.txt).
    table, paths = loaded
    toggle(user)
    edit(user, qtbot, 1, 'title', 'New')
    user.activate()
    table.setFocus()
    user.double_click_cell(user.cell(1, 'title'))
    QApplication.focusWidget().selectAll()
    user.press(Key.Key_Delete)
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: shown(user, 1, 'title')[0] in ('', 'Title 2'))
    user.press(Key.Key_Escape)
    assert shown(user, 1, 'title') == ('', 'bold')
    user.activate()
    user.press(Key.Key_W, Ctrl)
    qtbot.waitUntil(lambda: 'title' not in in_file(paths[1]))


@pytest.mark.xfail(strict=True, reason="Cancel in Write Previews drops the previews of the files it didn't write")
def test_cancel_keeps_the_previews_not_written(mainwin, user, loaded, qtbot, monkeypatch):
    # menus.txt, Write Previews: "If preview mode has been enabled and some
    # changes were made, they'll get written to the files, and Preview Mode
    # is disabled." It says nothing about Cancel: the files not written keep
    # their previews and Preview Mode stays on, as when a file fails to
    # write (the maintainer's decision). The slowdown is synthetic: the only
    # way to click Cancel while the files are being written.
    table, paths = loaded
    toggle(user)
    for row in range(3):
        edit(user, qtbot, row, 'title', f'New {row + 1}')
    model = table.model()
    real, first, go = model.setRowData, threading.Event(), threading.Event()

    def held(*args, **kwargs):
        if first.is_set():
            go.wait(5)
        result = real(*args, **kwargs)
        first.set()
        return result

    monkeypatch.setattr(model, 'setRowData', held)
    try:
        user.press(Key.Key_W, Ctrl)
        qtbot.waitUntil(first.is_set)
        [win] = [w for w in mainwin.findChildren(ProgressWin) if w.isVisible()]
        [cancel] = [b for b in win.findChildren(QPushButton) if b.text() == 'Cancel']
        user.click(cancel)
    finally:
        go.set()
    user.activate()

    # The file being written when Cancel came is finished.
    assert titles_in_files(paths) == [['New 1'], ['New 2'], ['Title 3']]
    assert preview_mode(mainwin)
    assert shown(user, 0, 'title') == ('New 1', 'plain')
    assert shown(user, 1, 'title') == ('New 2', 'plain')
    assert shown(user, 2, 'title') == ('New 3', 'bold')


def test_write_previews_with_nothing_staged(mainwin, user, loaded, qtbot):
    # menus.txt, Write Previews: "If preview mode has been enabled and some
    # changes were made, they'll get written to the files, and Preview Mode
    # is disabled." It says nothing for no changes: nothing is written and
    # Preview Mode stays on (the maintainer's decision).
    table, paths = loaded
    toggle(user)
    user.press(Key.Key_W, Ctrl)
    assert preview_mode(mainwin)
    assert titles_in_files(paths) == [['Title 1'], ['Title 2'], ['Title 3']]
    assert not [w for w in mainwin.findChildren(ProgressWin) if w.isVisible()]
