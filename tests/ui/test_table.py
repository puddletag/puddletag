"""The File-View itself, used as a user uses it: the header's right-click
Select Columns, moving a column by dragging its header, dropping files
and folders on it, the tooltip over a cell, Page Down and Page Up, the
status bar, and adding a folder over loaded ones (preferences.txt,
menus.txt). Synthetic files.
"""
import os
import shutil
from pathlib import Path

import pytest
from PyQt6.QtCore import QEvent, QMimeData, QPoint, QPointF, Qt, QTimer, QUrl
from PyQt6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QHelpEvent
from PyQt6.QtWidgets import (QApplication, QCheckBox, QLabel, QMenu, QMessageBox,
                             QStyle, QStyleOptionButton, QStyleOptionViewItem, QToolTip)

from puddlestuff import audioinfo
from puddlestuff.puddlesettings import SettingsDialog
from puddlestuff.tagmodel import ColumnSettings

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
LEFT = Qt.MouseButton.LeftButton
NO_MODIFIER = Qt.KeyboardModifier.NoModifier
Shift = Qt.KeyboardModifier.ShiftModifier

# A fresh profile's columns, left to right.
COLUMNS = ['__filename', 'artist', 'title', 'album', 'track', '__length', 'year',
           '__bitrate', 'genre', 'comment', '__dirpath']


def load(mainwin, qtbot, user, folder):
    """Opens the folder (and its subfolders) and gives the File-View the focus."""
    table = mainwin._table
    count = sum(1 for path in folder.rglob('*') if path.is_file())
    mainwin.openDir(str(folder), False)
    qtbot.waitUntil(lambda: table.model().rowCount() == count)
    user.activate()
    table.setFocus()
    return table


def names(table):
    return [audio['__filename'] for audio in table.model().taginfo]


def stamps(paths):
    """Each file's tags and modification time, to show nothing wrote it."""
    return {path: (audioinfo.usertags(audioinfo.Tag(str(path))), path.stat().st_mtime_ns)
            for path in paths}


def untouched(before):
    assert stamps(before) == before


def fields(table):
    return [field for title, field in table.model().headerdata]


def visual_columns(table):
    header = table.horizontalHeader()
    return [c for c in sorted(range(header.count()), key=header.visualIndex)
            if not header.isSectionHidden(c)]


def shown(table):
    """The fields of the columns the File-View shows, left to right."""
    return [fields(table)[c] for c in visual_columns(table)]


def titles(table):
    """The header's texts, left to right."""
    model = table.model()
    return [model.headerData(c, Qt.Orientation.Horizontal) for c in visual_columns(table)]


def section_center(table, field):
    header = table.horizontalHeader()
    column = fields(table).index(field)
    return QPoint(header.sectionViewportPosition(column) + header.sectionSize(column) // 2,
                  header.height() // 2)


def column_windows():
    """Select Columns opens a window without a parent."""
    return [w for w in QApplication.topLevelWidgets()
            if isinstance(w, ColumnSettings) and w.isVisible()]


def select_columns(mainwin, qtbot, user, field='title'):
    """Right-clicks the column's header and clicks Select Columns. The header
    builds its menu at each right-click, so the item is found in the open
    menu; the menu runs its own event loop, so the pick waits on a timer
    (as user.right_click's). Returns the window that opens, activated."""
    menus = []

    def pick(tries=100):
        menu = QApplication.activePopupWidget()
        if not (isinstance(menu, QMenu) and menu.isVisible()):
            if tries:
                QTimer.singleShot(10, lambda: pick(tries - 1))
            return
        menus.append([a.text() for a in menu.actions()])
        items = [a for a in menu.actions() if a.text() == '&Select Columns']
        if items:
            user.click(menu, menu.actionGeometry(items[0]).center())
        else:
            menu.close()

    header = mainwin._table.horizontalHeader()
    QTimer.singleShot(0, pick)
    # The pointer stays where the last test left it (see user.right_click).
    qtbot.mouseMove(mainwin.windowHandle(), QPoint(5, 5))
    qtbot.mouseClick(mainwin.windowHandle(), Qt.MouseButton.RightButton, NO_MODIFIER,
                     header.viewport().mapTo(mainwin, section_center(mainwin._table, field)))
    assert menus == [['&Select Columns']]
    qtbot.waitUntil(lambda: bool(column_windows()))
    [window] = column_windows()
    user.activate(window)
    return window


def column_item(window, title):
    [item] = window.listbox.findItems(title, Qt.MatchFlag.MatchExactly)
    return item


def click_check_box(user, window, title):
    """Clicks the column's check box in the Select Columns list."""
    listbox = window.listbox
    option = QStyleOptionViewItem()
    listbox.initViewItemOption(option)
    option.rect = listbox.visualItemRect(column_item(window, title))
    option.features |= QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
    box = listbox.style().subElementRect(QStyle.SubElement.SE_ItemViewItemCheckIndicator, option, listbox)
    user.click(listbox.viewport(), box.center())


def click_column_title(user, window, title):
    """Clicks the column's name in the list, to edit its Title and Field."""
    listbox = window.listbox
    user.click(listbox.viewport(), listbox.visualItemRect(column_item(window, title)).center())


def replace_text(user, widget, text):
    user.click(widget)
    user.press(Key.Key_A, Ctrl)
    user.type(text)


def click_ok(qtbot, user, window):
    user.click(window.okbuttons.okButton)
    qtbot.waitUntil(lambda: not window.isVisible())
    user.activate()


def drag_header(qtbot, table, field, before):
    """Drags the column's header onto the left edge of another's, as a user
    moves a column: press, a move past the drag distance, a move to the
    target, release."""
    header = table.horizontalHeader()
    start = section_center(table, field)
    column = fields(table).index(before)
    end = QPoint(header.sectionViewportPosition(column) + 3, header.height() // 2)
    qtbot.mousePress(header.viewport(), LEFT, pos=start)
    qtbot.mouseMove(header.viewport(), QPoint(start.x() - 20, start.y()))
    qtbot.mouseMove(header.viewport(), end)
    qtbot.mouseRelease(header.viewport(), LEFT, pos=end)


def set_preference(mainwin, qtbot, user, name, on):
    """Ticks or clears the box in Preferences' general page and clicks OK.
    The box stretches across the page, so a click at its center misses it:
    the click goes to its indicator."""
    user.click_menu('&Preferences')
    qtbot.waitUntil(lambda: any(w.isVisible() for w in mainwin.findChildren(SettingsDialog)))
    [window] = [w for w in mainwin.findChildren(SettingsDialog) if w.isVisible()]
    user.activate(window)
    [box] = [c for c in window.findChildren(QCheckBox) if c.text() == name]
    if box.isChecked() != on:
        option = QStyleOptionButton()
        box.initStyleOption(option)
        rect = box.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, box)
        user.click(box, rect.center())
    assert box.isChecked() == on
    user.click(window.okbuttons.okButton)
    qtbot.waitUntil(lambda: not window.isVisible())
    user.activate()


def drop(table, *paths):
    """Drops the files and folders on the File-View as a file manager does:
    the drag enters it, moves over it and drops, carrying the paths as URLs.
    QDrag.exec can't run on the offscreen platform, so the three events go
    straight to the viewport."""
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
    viewport = table.viewport()
    pos = viewport.rect().center()
    actions = Qt.DropAction.CopyAction | Qt.DropAction.LinkAction | Qt.DropAction.MoveAction
    enter = QDragEnterEvent(pos, actions, mime, LEFT, NO_MODIFIER)
    QApplication.sendEvent(viewport, enter)
    assert enter.isAccepted()
    move = QDragMoveEvent(pos, actions, mime, LEFT, NO_MODIFIER)
    QApplication.sendEvent(viewport, move)
    assert move.isAccepted()
    QApplication.sendEvent(viewport, QDropEvent(QPointF(pos), actions, mime, LEFT, NO_MODIFIER))


def titles_loaded(table):
    return sorted(audio['title'][0] for audio in table.model().taginfo)


def hover(qtbot, table, index):
    """Rests the pointer on the cell: Qt sends the view a ToolTip help
    event there. Returns the tooltip shown, or None. A tooltip hides only
    after a timer, so the last one is waited away first."""
    QToolTip.hideText()
    qtbot.waitUntil(lambda: not QToolTip.isVisible())
    viewport = table.viewport()
    pos = table.visualRect(index).center()
    QApplication.sendEvent(viewport, QHelpEvent(QEvent.Type.ToolTip, pos, viewport.mapToGlobal(pos)))
    return QToolTip.text() if QToolTip.isVisible() else None


def preview_label(mainwin):
    [label] = [w for w in mainwin.statusBar().findChildren(QLabel) if 'Preview Mode' in w.text()]
    return label


def counter(paths):
    """What the status bar shows for these 1-second files: count, total
    length, total size in whole KB."""
    size = sum(path.stat().st_size for path in paths)
    return f'{len(paths)} (00:{len(paths):02} | {size // 1024} KB)'


@pytest.fixture
def music(mainwin, make_audio, tmp_path, qtbot, user):
    """Three synthetic MP3s in one folder, loaded."""
    folder = tmp_path / 'music'
    paths = [make_audio('01.mp3', folder, album='Album A', artist='Artist A', composer='Composer A',
                        title='one'),
             make_audio('02.mp3', folder, album='Album B', artist='Artist B', title='two'),
             make_audio('03.mp3', folder, album='Album C', artist='Artist C', title='three')]
    table = load(mainwin, qtbot, user, folder)
    assert names(table) == ['01.mp3', '02.mp3', '03.mp3']
    return table, paths


def edit_title(qtbot, user, table, text):
    """Types the text into row 0's title cell and waits for it to land."""
    user.double_click_cell(user.cell(0, 'title'))
    user.type(text)
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: table.model().taginfo[0]['title'] == [text])


# preferences.txt: "By default tooltips will be shown in the file view
# showing the value of a cell on which the mouse is hovered."
def test_tooltip_shows_the_cell_value(mainwin, qtbot, user, music):
    table, paths = music
    assert hover(qtbot, table, user.cell(1, 'title')) == 'two'
    assert hover(qtbot, table, user.cell(0, 'artist')) == 'Artist A'


# preferences.txt: "When in Preview Mode the tooltip will show both the
# Preview and value as stored in the file, when they differ."
def test_tooltip_in_preview_mode_shows_both_values(mainwin, qtbot, user, music):
    table, paths = music
    user.press(Key.Key_P, Ctrl | Shift)
    assert table.model().previewMode
    edit_title(qtbot, user, table, 'uno')
    assert hover(qtbot, table, user.cell(0, 'title')) == 'Preview: uno\nReal: one'
    assert hover(qtbot, table, user.cell(1, 'title')) == 'two'
    assert audioinfo.Tag(str(paths[0]))['title'] == ['one']


# preferences.txt: "... both the Preview and value as stored in the file,
# when they differ." Back to the stored value, they don't.
def test_tooltip_in_preview_mode_with_the_stored_value(mainwin, qtbot, user, music):
    table, paths = music
    user.press(Key.Key_P, Ctrl | Shift)
    assert table.model().previewMode
    edit_title(qtbot, user, table, 'uno')
    edit_title(qtbot, user, table, 'one')
    assert hover(qtbot, table, user.cell(0, 'title')) == 'one'
    assert audioinfo.Tag(str(paths[0]))['title'] == ['one']


# preferences.txt: "Uncheck this box to disable it."
def test_tooltips_turned_off(mainwin, qtbot, user, music):
    table, paths = music
    set_preference(mainwin, qtbot, user, 'Show tooltips in file-view:', False)
    table.setFocus()
    assert hover(qtbot, table, user.cell(1, 'title')) is None


# preferences.txt, Columns: "In this panel you can modify the columns listed
# in the file-view. Any unchecked columns will not be shown. Title is the
# title that'll be displayed on the file-view's header. Data will be
# retrieved from the Field you specify." The header's right-click Select
# Columns opens this same panel.
def test_select_columns_hides_an_unchecked_column(mainwin, qtbot, user, music):
    table, paths = music
    before = stamps(paths)
    assert shown(table) == COLUMNS
    window = select_columns(mainwin, qtbot, user, 'album')
    # In column order, not sorted.
    assert [(window.listbox.item(i).text(), window.listbox.item(i).checkState())
            for i in range(window.listbox.count())] == [
        (title, Qt.CheckState.Checked)
        for title in ['Filename', 'Artist', 'Title', 'Album', 'Track', 'Length', 'Year',
                      'Bitrate', 'Genre', 'Comment', 'Dirpath']]
    click_check_box(user, window, 'Album')
    assert column_item(window, 'Album').checkState() == Qt.CheckState.Unchecked
    click_ok(qtbot, user, window)
    assert shown(table) == [f for f in COLUMNS if f != 'album']
    untouched(before)


# preferences.txt, Columns: "Title is the title that'll be displayed on the
# file-view's header."
def test_select_columns_renames_a_column(mainwin, qtbot, user, music):
    table, paths = music
    before = stamps(paths)
    window = select_columns(mainwin, qtbot, user)
    click_column_title(user, window, 'Album')
    replace_text(user, window.textname, 'Record')
    # The list follows the typing.
    assert column_item(window, 'Record')
    click_ok(qtbot, user, window)
    assert titles(table) == ['Filename', 'Artist', 'Title', 'Record', 'Track', 'Length', 'Year',
                             'Bitrate', 'Genre', 'Comment', 'Dirpath']
    # Same field, so the same data.
    assert table.model().data(user.cell(0, 'album')) == 'Album A'
    untouched(before)


# preferences.txt, Columns: "Data will be retrieved from the Field you
# specify."
def test_select_columns_changes_a_columns_field(mainwin, qtbot, user, music):
    table, paths = music
    before = stamps(paths)
    window = select_columns(mainwin, qtbot, user)
    click_column_title(user, window, 'Comment')
    replace_text(user, window.tag.lineEdit(), 'composer')
    assert window.tag.currentText() == 'composer'
    click_ok(qtbot, user, window)
    assert shown(table) == ['__filename', 'artist', 'title', 'album', 'track', '__length',
                            'year', '__bitrate', 'genre', 'composer', '__dirpath']
    assert titles(table)[9] == 'Comment'
    # data() returns None for a field the file lacks.
    assert [table.model().data(user.cell(row, 'composer')) for row in range(3)] == [
        'Composer A', None, None]
    untouched(before)


def test_hidden_column_stays_hidden_after_a_restart(mainwin, qtbot, user, music, restart):
    # The docs don't cover keeping columns across sessions (synthetic
    # expectation: preferences.txt: "Any unchecked columns will not be
    # shown.").
    table, paths = music
    window = select_columns(mainwin, qtbot, user, 'album')
    click_check_box(user, window, 'Album')
    assert column_item(window, 'Album').checkState() == Qt.CheckState.Unchecked
    click_ok(qtbot, user, window)
    assert shown(table) == [f for f in COLUMNS if f != 'album']

    win = restart()

    assert shown(win._table) == [f for f in COLUMNS if f != 'album']


def test_renamed_column_keeps_its_title_after_a_restart(mainwin, qtbot, user, music, restart):
    # The docs don't cover keeping columns across sessions (synthetic
    # expectation: preferences.txt: "Title is the title that'll be
    # displayed on the file-view's header.").
    table, paths = music
    window = select_columns(mainwin, qtbot, user, 'album')
    click_column_title(user, window, 'Album')
    replace_text(user, window.textname, 'Record')
    click_ok(qtbot, user, window)
    assert titles(table)[3] == 'Record'

    win = restart()

    assert titles(win._table)[3] == 'Record'


def test_drag_a_header_to_move_its_column(mainwin, qtbot, user, music):
    # The docs don't cover moving columns (synthetic expectation: the
    # column moves and the rows keep their order).
    table, paths = music
    before = stamps(paths)

    drag_header(qtbot, table, 'title', before='artist')

    assert shown(table) == ['__filename', 'title', 'artist', 'album', 'track', '__length', 'year',
                            '__bitrate', 'genre', 'comment', '__dirpath']
    # By title the rows would be one, three, two: the drag didn't sort.
    assert names(table) == ['01.mp3', '02.mp3', '03.mp3']
    untouched(before)


def test_moved_column_stays_after_a_restart(mainwin, qtbot, user, music, restart):
    # The docs don't cover moving columns or keeping them across sessions
    # (synthetic expectation: a moved column stays where it was put).
    table, paths = music
    drag_header(qtbot, table, 'title', before='artist')

    win = restart()

    assert shown(win._table)[:3] == ['__filename', 'title', 'artist']
    win.openDir(str(paths[0].parent), False)
    qtbot.waitUntil(lambda: win._table.model().rowCount() == 3)
    # The restarted table works.
    assert win._table.model().taginfo[0]['title'] == ['one']


@pytest.fixture
def folders(mainwin, make_audio, tmp_path, qtbot, user):
    """Folder b loaded; a (with a subfolder), c and loose not. Synthetic."""
    paths = [make_audio('a1.mp3', tmp_path / 'a', title='a1'),
             make_audio('a2.mp3', tmp_path / 'a' / 'sub', title='a2'),
             make_audio('b1.mp3', tmp_path / 'b', title='b1'),
             make_audio('c1.mp3', tmp_path / 'c', title='c1'),
             make_audio('100% #1.mp3', tmp_path / 'loose', title='odd name'),
             make_audio('plain.mp3', tmp_path / 'loose', title='plain')]
    table = load(mainwin, qtbot, user, tmp_path / 'b')
    return table, tmp_path, paths


def dropped(qtbot, user, table, count, *paths):
    """Drops the paths and waits for the rows they load; the loading
    progress window takes the activation."""
    drop(table, *paths)
    qtbot.waitUntil(lambda: table.model().rowCount() == count)
    user.activate()


def test_drop_files_adds_them(mainwin, qtbot, user, folders):
    # The docs are silent on dropping; the paths are synthetic.
    table, tmp_path, paths = folders
    before = stamps(paths)
    dropped(qtbot, user, table, 3, tmp_path / 'loose' / 'plain.mp3', tmp_path / 'loose' / '100% #1.mp3')
    assert titles_loaded(table) == ['b1', 'odd name', 'plain']
    untouched(before)
    assert all(path.exists() for path in paths)


def test_drop_a_folder_adds_it(mainwin, qtbot, user, folders):
    # The docs are silent on dropping; the folders are synthetic.
    table, tmp_path, paths = folders
    dropped(qtbot, user, table, 2, tmp_path / 'c')
    assert titles_loaded(table) == ['b1', 'c1']


def test_drop_several_folders_adds_them(mainwin, qtbot, user, folders):
    # The docs are silent on dropping; the folders are synthetic.
    table, tmp_path, paths = folders
    dropped(qtbot, user, table, 4, tmp_path / 'c', tmp_path / 'loose')
    assert titles_loaded(table) == ['b1', 'c1', 'odd name', 'plain']


def test_drop_files_and_folders_together(mainwin, qtbot, user, folders):
    # The docs are silent on dropping; the paths are synthetic. A file inside
    # a dropped folder is listed once.
    table, tmp_path, paths = folders
    dropped(qtbot, user, table, 4, tmp_path / 'c', tmp_path / 'loose', tmp_path / 'loose' / 'plain.mp3')
    assert titles_loaded(table) == ['b1', 'c1', 'odd name', 'plain']


SUBFOLDERS = {'off': (False, ['a1', 'b1']), 'on': (True, ['a1', 'a2', 'b1'])}


@pytest.mark.parametrize('subfolders, expected', SUBFOLDERS.values(), ids=SUBFOLDERS.keys())
def test_drop_a_folder_with_subfolders(mainwin, qtbot, user, folders, subfolders, expected):
    # "If checked, Subfolders of directories selected for import will be
    # checked for supported files (which'll then be loaded). Otherwise, just
    # files residing in the selected directories will be loaded." The docs
    # don't mention drops: this tests what the program does.
    table, tmp_path, paths = folders
    set_preference(mainwin, qtbot, user, 'Su&bfolders', subfolders)
    dropped(qtbot, user, table, len(expected), tmp_path / 'a')
    assert titles_loaded(table) == expected


TRASH = Path(os.environ['XDG_DATA_HOME'], 'Trash')
Yes = QMessageBox.StandardButton.Yes


@pytest.fixture
def empty_trash():
    """The sandbox's trash outlives each test's profile."""
    shutil.rmtree(TRASH, ignore_errors=True)
    yield
    shutil.rmtree(TRASH, ignore_errors=True)


def test_status_bar_counts_loaded_files(mainwin, qtbot, user, music):
    # Not in the docs; synthetic files. Loading counts the files, their length
    # and their size; the first row is selected after a load.
    table, paths = music
    assert mainwin._totalstats.text() == counter(paths)
    assert mainwin._selectedstats.text() == counter(paths[:1])


def test_status_bar_counts_selected_files(mainwin, qtbot, user, music):
    # Not in the docs; synthetic files. The selected-files counter follows the
    # selection and the all-files counter doesn't.
    table, paths = music
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(2, 'title'), Shift)
    assert mainwin._selectedstats.text() == counter(paths)
    user.click_cell(user.cell(1, 'title'))
    assert mainwin._selectedstats.text() == counter(paths[1:2])
    assert mainwin._totalstats.text() == counter(paths)


def test_status_bar_shows_preview_mode(mainwin, qtbot, user, music):
    # Not in the docs; synthetic files. Ctrl+Shift+P toggles Preview Mode and
    # the status bar's label follows it.
    table, paths = music
    assert preview_label(mainwin).text() == 'Preview Mode: Off'
    assert not table.model().previewMode
    user.press(Key.Key_P, Ctrl | Shift)
    assert preview_label(mainwin).text() == '<b>Preview Mode: On</b>'
    assert table.model().previewMode
    user.press(Key.Key_P, Ctrl | Shift)
    assert preview_label(mainwin).text() == 'Preview Mode: Off'
    assert not table.model().previewMode


def test_double_click_preview_label_toggles_preview_mode(mainwin, qtbot, user, music):
    # Not in the docs; synthetic files. Double-clicking the status bar's
    # Preview Mode label toggles Preview Mode.
    table, paths = music
    label = preview_label(mainwin)
    user.double_click(label, label.rect().center())
    assert table.model().previewMode
    assert label.text() == '<b>Preview Mode: On</b>'
    user.double_click(label, label.rect().center())
    assert not table.model().previewMode
    assert label.text() == 'Preview Mode: Off'


def test_status_bar_after_unload_everything(mainwin, qtbot, user, music):
    # Not in the docs; synthetic files. Unload Everything empties both
    # counters.
    table, paths = music
    user.click_menu('&Unload Everything')
    qtbot.waitUntil(lambda: table.model().rowCount() == 0)
    assert mainwin._totalstats.text() == '00 (00:00:00 | 00 KB)'
    assert mainwin._selectedstats.text() == '00 (00:00:00 | 00 KB)'


def test_status_bar_after_remove_from_list(mainwin, qtbot, user, music):
    # Not in the docs; synthetic files. Remove from List takes the file out of
    # the all-files counter.
    table, paths = music
    user.click_cell(user.cell(1, 'title'))
    user.click_menu('Remove from &List')
    qtbot.waitUntil(lambda: table.model().rowCount() == 2)
    user.activate()
    assert mainwin._totalstats.text() == counter([paths[0], paths[2]])


def test_status_bar_after_move_to_trash(mainwin, qtbot, user, music, dialogs, empty_trash):
    # Not in the docs; synthetic files. Move to Trash takes the file out of
    # the all-files counter.
    table, paths = music
    user.click_cell(user.cell(1, 'title'))
    dialogs.answer('QMessageBox.question', Yes)
    user.click_menu('Move to &Trash')
    qtbot.waitUntil(lambda: not paths[1].exists() and table.model().rowCount() == 2)
    user.activate()
    assert mainwin._totalstats.text() == counter([paths[0], paths[2]])


@pytest.fixture
def sixty(mainwin, make_audio, tmp_path, qtbot, user):
    """Sixty synthetic MP3s in one folder, loaded: more rows than the viewport shows."""
    folder = tmp_path / 'sixty'
    for n in range(60):
        make_audio(f'{n:02}.mp3', folder, title=f't{n}')
    return load(mainwin, qtbot, user, folder)


def fully_shown(table):
    """The first and last rows shown whole in the viewport."""
    height = table.viewport().height()
    top, bottom = table.rowAt(0), table.rowAt(height - 1)
    if table.visualRect(table.model().index(top, 0)).top() < 0:
        top += 1
    if table.visualRect(table.model().index(bottom, 0)).bottom() >= height:
        bottom -= 1
    return top, bottom


def test_page_down_skips_no_row(user, sixty):
    # "Hit page down and top row will be two rows from where cursor focus
    # started ... Missing row 60." (#347) Expected, the reporter's: the row
    # after the last fully shown row becomes the top row.
    table = sixty
    bottom = fully_shown(table)[1]
    user.click_cell(table.model().index(bottom, 2))
    user.press(Key.Key_PageDown)
    assert fully_shown(table)[0] == bottom + 1


def test_page_up_skips_no_row(user, sixty):
    # "Hit page down and top row will be two rows from where cursor focus
    # started ... Missing row 60." (#347) Page Up is Page Down's mirror: the
    # row before the first fully shown row becomes the bottom row.
    table = sixty
    user.press(Key.Key_End, Ctrl)
    top = fully_shown(table)[0]
    user.click_cell(table.model().index(top, 2))
    user.press(Key.Key_PageUp)
    assert fully_shown(table)[1] == top - 1


GET_DIRECTORY = 'QFileDialog.getExistingDirectory'

# The two ways to add a folder to what's loaded.
ADD_A_FOLDER = {
    'Add Folder': lambda user, dialogs, table, folder: add_folder(user, dialogs, folder),
    'drop': lambda user, dialogs, table, folder: drop(table, folder),
}


def add_folder(user, dialogs, folder):
    dialogs.answer(GET_DIRECTORY, str(folder))
    user.click_menu('&Add Folder')


def loaded_over(mainwin, qtbot, user, folders):
    """Loads the first folder, then adds the others, as setup. Returns the
    table, with Subfolders on."""
    set_preference(mainwin, qtbot, user, 'Su&bfolders', True)
    table = mainwin._table
    count = 0
    for i, folder in enumerate(folders):
        count += sum(1 for path in folder.rglob('*') if path.is_file())
        mainwin.openDir(str(folder), bool(i))
        qtbot.waitUntil(lambda: table.model().rowCount() == count)
    user.activate()
    table.setFocus()
    return table


FOLDER_HOLDING_A_LOADED_ONE = "a folder holding a loaded folder removes the other folders' files"


@pytest.mark.xfail(strict=True, reason=FOLDER_HOLDING_A_LOADED_ONE)
@pytest.mark.parametrize('add', ADD_A_FOLDER.values(), ids=ADD_A_FOLDER.keys())
def test_add_folder_holding_a_loaded_folder_keeps_the_others(mainwin, make_audio, tmp_path, qtbot, user, dialogs, add):
    # Add Folder: "Works as Open Folder, but instead of replacing the
    # File-Views's contents, appends the newly loaded files." (synthetic folders)
    m = tmp_path / 'm'
    make_audio('a1.mp3', m / 'a', title='a1')
    make_audio('a2.mp3', m / 'a' / 'sub', title='a2')
    make_audio('b1.mp3', m / 'b', title='b1')
    table = loaded_over(mainwin, qtbot, user, [m / 'a' / 'sub', m / 'b'])
    add(user, dialogs, table, m / 'a')
    qtbot.waitUntil(lambda: table.model().rowCount() == 3)
    user.activate()
    assert titles_loaded(table) == ['a1', 'a2', 'b1']


@pytest.mark.xfail(strict=True, reason="a folder whose name starts with a loaded folder's name loads nothing")
@pytest.mark.parametrize('add', ADD_A_FOLDER.values(), ids=ADD_A_FOLDER.keys())
def test_add_folder_named_like_a_loaded_one(mainwin, make_audio, tmp_path, qtbot, user, dialogs, add):
    # Add Folder: "Works as Open Folder, but instead of replacing the
    # File-Views's contents, appends the newly loaded files." (synthetic folders)
    m = tmp_path / 'm'
    make_audio('x.mp3', m / 'Beatles', title='x')
    make_audio('y.mp3', m / 'Beatles Live', title='y')
    table = loaded_over(mainwin, qtbot, user, [m / 'Beatles'])
    add(user, dialogs, table, m / 'Beatles Live')
    qtbot.waitUntil(lambda: table.model().rowCount() == 2)
    user.activate()
    assert titles_loaded(table) == ['x', 'y']


@pytest.mark.xfail(strict=True, reason=FOLDER_HOLDING_A_LOADED_ONE)
@pytest.mark.parametrize('add', ADD_A_FOLDER.values(), ids=ADD_A_FOLDER.keys())
def test_add_folder_named_like_the_start_of_a_loaded_one(mainwin, make_audio, tmp_path, qtbot, user, dialogs, add):
    # Add Folder: "Works as Open Folder, but instead of replacing the
    # File-Views's contents, appends the newly loaded files." (synthetic folders)
    m = tmp_path / 'm'
    make_audio('x.mp3', m / 'Beatles', title='x')
    make_audio('y.mp3', m / 'Beatles Live', title='y')
    make_audio('z.mp3', m / 'other', title='z')
    table = loaded_over(mainwin, qtbot, user, [m / 'Beatles Live', m / 'other'])
    add(user, dialogs, table, m / 'Beatles')
    qtbot.waitUntil(lambda: table.model().rowCount() == 3)
    user.activate()
    assert titles_loaded(table) == ['x', 'y', 'z']
