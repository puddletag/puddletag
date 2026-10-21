"""Selection and order in the File-View, run as a user runs them: Edit's
Select Next/Previous Directory, Invert Selection, Select Column, Select
All, Move Selected Up/Down and Increase/Decrease Font (menus.txt), Tools'
Sort By and the right-click menu's (preferences.txt), and a click on a
column header. Each is checked in the table and on disk, where none of
them writes. Synthetic files.
"""
import pytest
from PyQt6.QtCore import QLocale, QPoint, Qt, QTimer
from PyQt6.QtWidgets import QApplication, QMenu

from puddlestuff import audioinfo
from puddlestuff.puddleobjects import PuddleConfig

pytestmark = pytest.mark.ui

Key = Qt.Key
Alt = Qt.KeyboardModifier.AltModifier
Ctrl = Qt.KeyboardModifier.ControlModifier
Keypad = Qt.KeyboardModifier.KeypadModifier
Meta = Qt.KeyboardModifier.MetaModifier
Shift = Qt.KeyboardModifier.ShiftModifier

COLUMNS = 11  # a fresh profile's File-View columns


def load(mainwin, qtbot, user, *folders):
    """Opens the first folder, adds the others (as Add Folder does), and
    gives the File-View the focus."""
    table = mainwin._table
    count = 0
    for i, folder in enumerate(folders):
        count += len(list(folder.iterdir()))
        mainwin.openDir(str(folder), bool(i))
        qtbot.waitUntil(lambda: table.model().rowCount() == count)
    user.activate()
    table.setFocus()
    return table


def names(table):
    return [audio['__filename'] for audio in table.model().taginfo]


def selected_cells(table):
    fields = [field for title, field in table.model().headerdata]
    return sorted((index.row(), fields[index.column()])
                  for index in table.selectionModel().selectedIndexes())


def selected_rows(table):
    return sorted({index.row() for index in table.selectionModel().selectedIndexes()})


def stamps(paths):
    """Each file's tags and modification time, to show nothing wrote it."""
    return {path: (audioinfo.usertags(audioinfo.Tag(str(path))), path.stat().st_mtime_ns)
            for path in paths}


def untouched(before):
    assert stamps(before) == before


def click_header(user, field):
    """Clicks the column's header, as a user sorts by it."""
    table = user.table
    header = table.horizontalHeader()
    column = [f for title, f in table.model().headerdata].index(field)
    x = header.sectionViewportPosition(column) + header.sectionSize(column) // 2
    user.click(header.viewport(), QPoint(x, header.height() // 2))


def sort_by_menu(mainwin):
    [menu] = [m for m in mainwin.findChildren(QMenu) if m.title() == 'Sort &By']
    return menu


def sort_option(mainwin, option):
    [action] = [a for a in sort_by_menu(mainwin).actions() if a.text() == option]
    return action


def pick_sort_option(mainwin, qtbot, user, option):
    """Tools→Sort By→option."""
    sort_by = sort_by_menu(mainwin)
    action = sort_option(mainwin, option)
    bar = mainwin.menuBar()
    [tools] = [m for m in bar.findChildren(QMenu) if m.title() == '&Tools']
    # The pointer stays where the last test left it (see user.right_click).
    qtbot.mouseMove(mainwin.windowHandle(), QPoint(5, 5))
    user.click(bar, bar.actionGeometry(tools.menuAction()).center())
    qtbot.waitUntil(tools.isVisible)
    user.click(tools, tools.actionGeometry(sort_by.menuAction()).center())
    qtbot.waitUntil(sort_by.isVisible)
    user.click(sort_by, sort_by.actionGeometry(action).center())
    qtbot.waitUntil(lambda: not tools.isVisible())
    user.activate()


def right_click_sort_option(mainwin, qtbot, user, index, option):
    """Right-clicks the cell and picks Sort By→option. The menus run their
    own event loops, so the picks wait on a timer, as user.right_click's."""
    sort_by = sort_by_menu(mainwin)
    action = sort_option(mainwin, option)
    picked = []

    def pick(tries=100):
        menu = QApplication.activePopupWidget()
        if not (isinstance(menu, QMenu) and menu.isVisible()):
            if tries:
                QTimer.singleShot(10, lambda: pick(tries - 1))
            return
        if action in menu.actions():
            picked.append(option)
            user.click(menu, menu.actionGeometry(action).center())
        elif sort_by.menuAction() in menu.actions():
            if not sort_by.isVisible():
                user.click(menu, menu.actionGeometry(sort_by.menuAction()).center())
            QTimer.singleShot(10, lambda: pick(tries - 1))
        else:
            menu.close()

    table = user.table
    table.scrollTo(index)
    window = table.window()
    QTimer.singleShot(0, pick)
    qtbot.mouseMove(window.windowHandle(), QPoint(5, 5))
    qtbot.mouseClick(window.windowHandle(), Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier,
                     table.viewport().mapTo(window, table.visualRect(index).center()))
    assert picked, f'{option} was not picked from the right-click menu'
    user.activate(window)


def font_size(user):
    return user.table.model().data(user.cell(0, 'title'), Qt.ItemDataRole.FontRole).pointSize()


SELECT_NEXT = {
    'Edit menu': lambda user: user.click_menu('Select &Next Directory'),
    'shortcut': lambda user: user.press(Key.Key_N, Ctrl),
}
SELECT_PREVIOUS = {
    'Edit menu': lambda user: user.click_menu('Select &Previous Directory'),
    'shortcut': lambda user: user.press(Key.Key_N, Ctrl | Shift),
}


@pytest.fixture
def two_folders(mainwin, make_audio, tmp_path, qtbot, user):
    a = tmp_path / 'a'
    b = tmp_path / 'b'
    paths = [make_audio('a1.mp3', a, title='alpha'),
             make_audio('a2.mp3', a, title='charlie'),
             make_audio('b1.mp3', b, title='bravo'),
             make_audio('b2.mp3', b, title='delta')]
    table = load(mainwin, qtbot, user, a, b)
    assert names(table) == ['a1.mp3', 'a2.mp3', 'b1.mp3', 'b2.mp3']
    return table, paths


@pytest.fixture
def one_folder(mainwin, make_audio, tmp_path, qtbot, user):
    a = tmp_path / 'a'
    paths = [make_audio('a1.mp3', a, title='alpha'),
             make_audio('a2.mp3', a, title='charlie')]
    return load(mainwin, qtbot, user, a), paths


def click(user, row, field):
    user.click_cell(user.cell(row, field))


def ctrl_click(user, row, field):
    user.click_cell(user.cell(row, field), Ctrl)


def run(user, command):
    command(user)
    user.activate()  # a menu click takes the activation


@pytest.mark.parametrize('select', SELECT_NEXT.values(), ids=SELECT_NEXT.keys())
def test_select_next_directory_selects_the_folder(user, two_folders, select):
    # "Select a file. Invoke this menu item. All the files with the same
    # __dirpath will be selected."
    table, paths = two_folders
    before = stamps(paths)
    click(user, 0, 'title')
    run(user, select)
    assert selected_rows(table) == [0, 1]
    assert selected_cells(table) == [(0, 'title'), (1, 'title')]
    untouched(before)


def test_select_next_directory_again_selects_the_next_folder(user, two_folders):
    # "Invoke this menu item again, then puddletag will pick the first file
    # (going down in the File-View) with a different __dirpath to those
    # selected and select all files with that __dirpath."
    table, paths = two_folders
    before = stamps(paths)
    click(user, 0, 'title')
    user.press(Key.Key_N, Ctrl)
    user.press(Key.Key_N, Ctrl)
    assert selected_cells(table) == [(2, 'title'), (3, 'title')]
    untouched(before)


@pytest.mark.parametrize('select', SELECT_PREVIOUS.values(), ids=SELECT_PREVIOUS.keys())
def test_select_previous_directory(user, two_folders, select):
    # "Does what the previous menu item does except it checks for the first
    # differing file by going up in the File-View."
    table, paths = two_folders
    before = stamps(paths)
    click(user, 3, 'title')
    run(user, select)
    assert selected_rows(table) == [2, 3]
    run(user, select)
    assert selected_cells(table) == [(0, 'title'), (1, 'title')]
    untouched(before)


def test_select_next_directory_with_several_folders_selected(user, two_folders):
    # "If you have multiple files with differing __dirpaths selected then
    # puddletag will select all the files belonging to those __dirpaths. It
    # will not do anything if you invoke this menu item again though."
    table, paths = two_folders
    before = stamps(paths)
    click(user, 1, 'title')
    ctrl_click(user, 2, 'title')
    user.press(Key.Key_N, Ctrl)
    assert selected_rows(table) == [0, 1, 2, 3]
    cells = selected_cells(table)
    user.press(Key.Key_N, Ctrl)
    assert selected_cells(table) == cells
    untouched(before)


def test_select_next_directory_wraps_to_the_first_folder(user, two_folders):
    # The docs don't say; this is what puddletag does: from the last folder,
    # Select Next Directory goes on with the first.
    table, paths = two_folders
    before = stamps(paths)
    click(user, 3, 'title')
    user.press(Key.Key_N, Ctrl)
    user.press(Key.Key_N, Ctrl)
    assert selected_rows(table) == [0, 1]
    untouched(before)


def test_select_previous_directory_wraps_to_the_last_folder(user, two_folders):
    # The docs don't say; this is what puddletag does: from the first
    # folder, Select Previous Directory goes on with the last.
    table, paths = two_folders
    before = stamps(paths)
    click(user, 0, 'title')
    user.press(Key.Key_N, Ctrl | Shift)
    user.press(Key.Key_N, Ctrl | Shift)
    assert selected_rows(table) == [2, 3]
    untouched(before)


def test_select_next_directory_after_a_sort(user, two_folders):
    # The docs don't say; this is what puddletag does: the folders are
    # followed in the table's order, so with the files sorted by title
    # (alpha, bravo, charlie, delta) each folder is two separate rows.
    table, paths = two_folders
    before = stamps(paths)
    click_header(user, 'title')
    assert names(table) == ['a1.mp3', 'b1.mp3', 'a2.mp3', 'b2.mp3']
    click(user, 0, 'title')
    user.press(Key.Key_N, Ctrl)
    assert selected_rows(table) == [0, 2]
    user.press(Key.Key_N, Ctrl)
    assert selected_rows(table) == [1, 3]
    user.press(Key.Key_N, Ctrl | Shift)
    assert selected_rows(table) == [0, 2]
    untouched(before)


@pytest.mark.timeout(10)
def test_select_next_directory_with_one_folder(user, one_folder):
    # The docs don't say; this is what puddletag does: with one folder
    # loaded, whole and selected, nothing changes.
    table, paths = one_folder
    before = stamps(paths)
    click(user, 0, 'title')
    user.press(Key.Key_N, Ctrl)
    assert selected_rows(table) == [0, 1]
    user.press(Key.Key_N, Ctrl)
    assert selected_rows(table) == [0, 1]
    untouched(before)


def test_select_previous_directory_with_one_folder(user, one_folder):
    # The docs don't say; this is what puddletag does: with one folder
    # loaded, whole and selected, nothing changes.
    table, paths = one_folder
    before = stamps(paths)
    click(user, 0, 'title')
    user.press(Key.Key_N, Ctrl | Shift)
    assert selected_rows(table) == [0, 1]
    user.press(Key.Key_N, Ctrl | Shift)
    assert selected_rows(table) == [0, 1]
    untouched(before)


def test_select_directory_needs_a_selection(user, two_folders):
    # The docs don't say; this is what puddletag does: with nothing
    # selected, both items are greyed out and Ctrl+N selects nothing.
    table, paths = two_folders
    before = stamps(paths)
    click(user, 0, 'title')
    ctrl_click(user, 0, 'title')
    assert selected_cells(table) == []
    assert not user.action('Select &Next Directory').isEnabled()
    assert not user.action('Select &Previous Directory').isEnabled()
    user.press(Key.Key_N, Ctrl)
    assert selected_cells(table) == []
    untouched(before)


INVERT = {
    'Edit menu': lambda user: user.click_menu('&Invert Selection'),
    'shortcut': lambda user: user.press(Key.Key_A, Ctrl | Shift),
}
SELECT_ALL = {
    'Edit menu': lambda user: user.click_menu('Select &All'),
    'shortcut': lambda user: user.press(Key.Key_A, Ctrl),
}
SELECT_COLUMN = {
    'Edit menu': lambda user: user.click_menu('&Select Column'),
    'shortcut': lambda user: user.press(Key.Key_C, Alt | Meta),
}


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    music = tmp_path / 'music'
    paths = [make_audio(f'0{i}.mp3', music, artist=f'Artist {i}', title=f'Title {i}')
             for i in (1, 2, 3)]
    table = load(mainwin, qtbot, user, music)
    assert names(table) == ['01.mp3', '02.mp3', '03.mp3']
    return table, stamps(paths)


@pytest.mark.parametrize('invert', INVERT.values(), ids=INVERT.keys())
def test_invert_selection(user, loaded, invert):
    # "Selects all the cells that aren't currently selected. Deselects those
    # that are."
    table, before = loaded
    user.click_cell(user.cell(1, 'title'))
    invert(user)
    cells = selected_cells(table)
    assert len(cells) == 3 * COLUMNS - 1
    assert (1, 'title') not in cells
    user.activate()
    user.press(Key.Key_A, Ctrl | Shift)
    assert selected_cells(table) == [(1, 'title')]
    untouched(before)


@pytest.mark.parametrize('select_column', SELECT_COLUMN.values(), ids=SELECT_COLUMN.keys())
def test_select_column(user, loaded, select_column):
    # "Select's the column of whichever cell you last selected." The cell
    # clicked before it stays selected too.
    table, before = loaded
    user.click_cell(user.cell(0, 'artist'))
    user.click_cell(user.cell(2, 'title'), Ctrl)
    select_column(user)
    assert selected_cells(table) == [(0, 'artist'), (0, 'title'), (1, 'title'), (2, 'title')]
    untouched(before)


@pytest.mark.parametrize('select_all', SELECT_ALL.values(), ids=SELECT_ALL.keys())
def test_select_all(user, loaded, select_all):
    # "It's obvious if you think about it."
    table, before = loaded
    user.click_cell(user.cell(1, 'title'))
    select_all(user)
    assert len(selected_cells(table)) == 3 * COLUMNS
    assert selected_rows(table) == [0, 1, 2]
    untouched(before)


def test_selection_commands_enabled(mainwin, user, make_audio, tmp_path, qtbot):
    # The docs don't say; this is what puddletag does: Select All and Invert
    # Selection work as soon as files are loaded, Select Column only once a
    # cell is selected.
    assert not user.action('Select &All').isEnabled()
    assert not user.action('&Invert Selection').isEnabled()
    assert not user.action('&Select Column').isEnabled()
    music = tmp_path / 'music'
    make_audio('01.mp3', music, artist='Artist 1', title='Title 1')
    load(mainwin, qtbot, user, music)
    assert user.action('Select &All').isEnabled()
    assert user.action('&Invert Selection').isEnabled()
    assert not user.action('&Select Column').isEnabled()
    user.click_cell(user.cell(0, 'title'))
    assert user.action('&Select Column').isEnabled()


@pytest.fixture
def four(mainwin, make_audio, tmp_path, qtbot, user):
    music = tmp_path / 'music'
    paths = [make_audio(f'0{i}.mp3', music, artist=f'Artist {i}', title=f'Title {i}')
             for i in (1, 2, 3, 4)]
    table = load(mainwin, qtbot, user, music)
    assert names(table) == ['01.mp3', '02.mp3', '03.mp3', '04.mp3']
    return table, stamps(paths)


def test_ctrl_shift_end_selects_to_the_last_row(user, four):
    # The docs don't say; this is what a user expects (#206): Ctrl+Shift+End
    # extends the selection from the current cell to the last row, as
    # Shift+Down extends it by one row.
    table, before = four
    user.click_cell(user.cell(1, 'title'))
    user.press(Key.Key_End, Ctrl | Shift)
    assert selected_rows(table) == [1, 2, 3]
    untouched(before)


def test_ctrl_shift_home_selects_to_the_first_row(user, four):
    # The docs don't say; this is what a user expects (#206): Ctrl+Shift+Home
    # extends the selection from the current cell to the first row.
    table, before = four
    user.click_cell(user.cell(2, 'title'))
    user.press(Key.Key_Home, Ctrl | Shift)
    assert selected_rows(table) == [0, 1, 2]
    untouched(before)


@pytest.fixture
def music(mainwin, make_audio, tmp_path, qtbot, user):
    folder = tmp_path / 'music'
    paths = [make_audio(f'0{i}.mp3', folder, title=f'Title {i}') for i in (1, 2, 3, 4)]
    table = load(mainwin, qtbot, user, folder)
    assert names(table) == ['01.mp3', '02.mp3', '03.mp3', '04.mp3']
    return table, paths


MOVE_UP = {
    'Edit menu': lambda user: user.click_menu('Move Selected &Up'),
    'shortcut': lambda user: user.press(Key.Key_Plus, Ctrl | Keypad),
}
MOVE_DOWN = {
    'Edit menu': lambda user: user.click_menu('Move Selected Do&wn'),
    'shortcut': lambda user: user.press(Key.Key_Minus, Ctrl | Keypad),
}


@pytest.mark.parametrize('move', MOVE_UP.values(), ids=MOVE_UP.keys())
def test_move_selected_up(user, music, move):
    # "Moves the selected files up one row in the File-View."
    table, paths = music
    before = stamps(paths)
    user.click_cell(user.cell(2, 'title'))
    move(user)
    assert names(table) == ['01.mp3', '03.mp3', '02.mp3', '04.mp3']
    # The docs don't say; this is what puddletag does: the selection follows
    # the moved file.
    assert selected_cells(table) == [(1, 'title')]
    untouched(before)


@pytest.mark.parametrize('move', MOVE_DOWN.values(), ids=MOVE_DOWN.keys())
def test_move_selected_down(user, music, move):
    # "Moves the selected files down one row in the File-View."
    table, paths = music
    before = stamps(paths)
    user.click_cell(user.cell(1, 'title'))
    move(user)
    assert names(table) == ['01.mp3', '03.mp3', '02.mp3', '04.mp3']
    # The docs don't say; this is what puddletag does: the selection follows
    # the moved file.
    assert selected_cells(table) == [(2, 'title')]
    untouched(before)


def test_move_a_block_up(user, music):
    # "Moves the selected files up one row in the File-View."
    table, paths = music
    before = stamps(paths)
    user.click_cell(user.cell(1, 'title'))
    user.click_cell(user.cell(2, 'title'), Shift)
    user.press(Key.Key_Plus, Ctrl | Keypad)
    assert names(table) == ['02.mp3', '03.mp3', '01.mp3', '04.mp3']
    # The docs don't say; this is what puddletag does: the selection follows
    # the moved files.
    assert selected_rows(table) == [0, 1]
    untouched(before)


def test_move_rows_apart(user, music):
    # "Moves the selected files up one row in the File-View.", and down.
    table, paths = music
    before = stamps(paths)
    user.click_cell(user.cell(1, 'title'))
    user.click_cell(user.cell(3, 'title'), Ctrl)
    user.press(Key.Key_Plus, Ctrl | Keypad)
    assert names(table) == ['02.mp3', '01.mp3', '04.mp3', '03.mp3']
    # The docs don't say; this is what puddletag does: the selection follows
    # the moved files.
    assert selected_rows(table) == [0, 2]
    user.press(Key.Key_Minus, Ctrl | Keypad)
    assert names(table) == ['01.mp3', '02.mp3', '03.mp3', '04.mp3']
    assert selected_rows(table) == [1, 3]
    untouched(before)


def test_move_up_with_the_first_row(user, music):
    # "Moves the selected files up one row in the File-View." The docs don't
    # say what happens with the first row selected; this is what puddletag
    # does: nothing moves, the other selected rows neither.
    table, paths = music
    before = stamps(paths)
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(2, 'title'), Ctrl)
    user.press(Key.Key_Plus, Ctrl | Keypad)
    assert names(table) == ['01.mp3', '02.mp3', '03.mp3', '04.mp3']
    assert selected_rows(table) == [0, 2]
    untouched(before)


def test_move_down_with_the_last_row(user, music):
    # "Moves the selected files down one row in the File-View." The docs
    # don't say what happens with the last row selected; this is what
    # puddletag does: nothing moves.
    table, paths = music
    before = stamps(paths)
    user.click_cell(user.cell(3, 'title'))
    user.press(Key.Key_Minus, Ctrl | Keypad)
    assert names(table) == ['01.mp3', '02.mp3', '03.mp3', '04.mp3']
    assert selected_rows(table) == [3]
    untouched(before)


@pytest.mark.xfail(strict=True, reason='Moving rows reports a changed range that ends past the last column')
def test_move_reports_valid_cells(user, music, qtlog):
    # "Moves the selected files up one row in the File-View." Qt warns when a
    # model reports a changed range that isn't made of its cells.
    table, paths = music
    user.click_cell(user.cell(1, 'title'))
    user.press(Key.Key_Plus, Ctrl | Keypad)
    user.press(Key.Key_Minus, Ctrl | Keypad)
    assert [record.message for record in qtlog.records
            if 'invalid index range' in record.message] == []


def test_refresh_after_a_move(user, music, qtbot):
    # "Moves the selected files up one row in the File-View." The docs don't
    # say what Refresh does after it; this is what puddletag does: it sorts
    # the files again, so the moved order goes.
    table, paths = music
    before = stamps(paths)
    user.click_cell(user.cell(2, 'title'))
    user.press(Key.Key_Plus, Ctrl | Keypad)
    assert names(table) == ['01.mp3', '03.mp3', '02.mp3', '04.mp3']
    user.press(Key.Key_F5)
    qtbot.waitUntil(lambda: names(table) == ['01.mp3', '02.mp3', '03.mp3', '04.mp3'])
    untouched(before)


@pytest.fixture
def albums(mainwin, make_audio, tmp_path, qtbot, user):
    music = tmp_path / 'music'
    paths = [make_audio(f'{name}.mp3', music, title=title, album=album, tracknumber=track)
             for name, title, album, track in [('a', 'alpha', 'xray', '4'),
                                               ('b', 'bravo', 'yankee', '3'),
                                               ('c', 'charlie', 'xray', '2'),
                                               ('d', 'delta', 'yankee', '1')]]
    table = load(mainwin, qtbot, user, music)
    assert names(table) == ['a.mp3', 'b.mp3', 'c.mp3', 'd.mp3']
    return table, paths


SORT_BY = {
    'Tools menu': lambda mainwin, qtbot, user, option: pick_sort_option(mainwin, qtbot, user, option),
    'right-click menu': lambda mainwin, qtbot, user, option:
        right_click_sort_option(mainwin, qtbot, user, user.cell(0, 'title'), option),
}


def test_sort_by_menu(mainwin, albums):
    # "Any field-lists you add will create a menu item in the Tools->Sort By
    # menu." A fresh profile's options are puddletag's three defaults.
    [tools] = [m for m in mainwin.menuBar().findChildren(QMenu) if m.title() == '&Tools']
    assert sort_by_menu(mainwin).menuAction() in tools.actions()
    assert [a.text() for a in sort_by_menu(mainwin).actions()] == [
        '__filename/track/__dirpath', 'track/album', '__filename/album/__dirpath']


@pytest.mark.parametrize('sort_by', SORT_BY.values(), ids=SORT_BY.keys())
def test_sort_by(mainwin, qtbot, user, albums, sort_by):
    # "Provided a single file (or none at all) is selected, clicking on a
    # menu item will sort the file-view in order of the fields defined. So
    # track/__dirpath/album will sort the file-view by track first, then
    # __dirpath then album. It's equivalent to clicking the relevant headers
    # in order in the file-view."
    table, paths = albums
    before = stamps(paths)
    user.click_cell(user.cell(0, 'title'))
    sort_by(mainwin, qtbot, user, 'track/album')
    assert names(table) == ['c.mp3', 'a.mp3', 'd.mp3', 'b.mp3']
    untouched(before)


def test_sort_by_equals_clicking_headers(user, albums):
    # "It's equivalent to clicking the relevant headers in order in the
    # file-view." Track first, then album: the same order as Sort By
    # track/album.
    table, paths = albums
    before = stamps(paths)
    click_header(user, 'track')
    assert names(table) == ['d.mp3', 'c.mp3', 'b.mp3', 'a.mp3']
    click_header(user, 'album')
    assert names(table) == ['c.mp3', 'a.mp3', 'd.mp3', 'b.mp3']
    untouched(before)


def test_sort_by_again_reverses(mainwin, qtbot, user, albums):
    # "Click on it again and the sort order will be reversed: the same
    # fields, in descending order." (preferences.txt:47)
    table, paths = albums
    before = stamps(paths)
    pick_sort_option(mainwin, qtbot, user, 'track/album')
    assert names(table) == ['c.mp3', 'a.mp3', 'd.mp3', 'b.mp3']
    pick_sort_option(mainwin, qtbot, user, 'track/album')
    assert names(table) == ['b.mp3', 'd.mp3', 'a.mp3', 'c.mp3']
    untouched(before)


def test_sort_by_with_nothing_selected(mainwin, qtbot, user, albums):
    # "Provided a single file (or none at all) is selected, clicking on a
    # menu item will sort the file-view in order of the fields defined."
    table, paths = albums
    before = stamps(paths)
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(0, 'title'), Ctrl)
    assert selected_cells(table) == []
    pick_sort_option(mainwin, qtbot, user, 'track/album')
    assert names(table) == ['c.mp3', 'a.mp3', 'd.mp3', 'b.mp3']
    untouched(before)


def test_sort_by_several_selected_files(mainwin, qtbot, user, albums):
    # "Provided a single file (or none at all) is selected, clicking on a
    # menu item will sort the file-view ..." The docs say nothing about
    # several files; this is what puddletag does: only the selected files
    # are sorted, into the rows they hold (b's track 3 and d's track 1
    # swap), and the selection stays on those rows.
    table, paths = albums
    before = stamps(paths)
    user.click_cell(user.cell(1, 'title'))
    user.click_cell(user.cell(3, 'title'), Ctrl)
    pick_sort_option(mainwin, qtbot, user, 'track/album')
    assert names(table) == ['a.mp3', 'd.mp3', 'c.mp3', 'b.mp3']
    assert selected_rows(table) == [1, 3]
    untouched(before)


def test_sort_by_used_when_loading(mainwin, make_audio, tmp_path, qtbot, user, albums):
    # "This sort order will be used when loading dirs unless changed (by
    # clicking a header or using another Sort Option.)" By file name the new
    # folder would load as e, f.
    table, paths = albums
    more = tmp_path / 'more'
    paths += [make_audio('e.mp3', more, album='xray', tracknumber='2'),
              make_audio('f.mp3', more, album='xray', tracknumber='1')]
    before = stamps(paths)
    pick_sort_option(mainwin, qtbot, user, 'track/album')
    mainwin.openDir(str(more), False)
    qtbot.waitUntil(lambda: names(table) == ['f.mp3', 'e.mp3'])
    untouched(before)


def test_sort_by_saved(mainwin, qtbot, user, albums):
    # "This sort order will be used when loading dirs unless changed (by
    # clicking a header or using another Sort Option.) It is saved across
    # sessions."
    table, paths = albums
    before = stamps(paths)
    pick_sort_option(mainwin, qtbot, user, 'track/album')
    mainwin.close()
    assert PuddleConfig().get('table', 'sort_fields', None) == ['track', 'album']
    assert PuddleConfig().get('table', 'sort_reverse', None) is False
    untouched(before)


def test_sort_by_replaced_by_a_header_click_when_saved(mainwin, qtbot, user, albums):
    # "This sort order will be used when loading dirs unless changed (by
    # clicking a header or using another Sort Option.) It is saved across
    # sessions."
    table, paths = albums
    before = stamps(paths)
    pick_sort_option(mainwin, qtbot, user, 'track/album')
    click_header(user, 'title')
    mainwin.close()
    assert PuddleConfig().get('table', 'sort_fields', None) == ['title']
    untouched(before)


@pytest.fixture
def three(mainwin, make_audio, tmp_path, qtbot, user):
    """Three files with titles charlie, alpha and bravo."""
    music = tmp_path / 'music'
    paths = [make_audio(f'{name}.mp3', music, title=title)
             for name, title in [('a', 'charlie'), ('b', 'alpha'), ('c', 'bravo')]]
    table = load(mainwin, qtbot, user, music)
    return table, paths


def test_header_click_sorts_ascending_then_descending(user, three):
    # The docs don't say which order comes first; this is what puddletag
    # does: the first click sorts ascending, the second descending.
    table, paths = three
    before = stamps(paths)
    header = table.horizontalHeader()
    click_header(user, 'title')
    assert [audio['title'] for audio in table.model().taginfo] == [['alpha'], ['bravo'], ['charlie']]
    assert header.sortIndicatorSection() == 2
    assert header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
    click_header(user, 'title')
    assert [audio['title'] for audio in table.model().taginfo] == [['charlie'], ['bravo'], ['alpha']]
    assert header.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
    untouched(before)


def test_header_sort_keeps_ties_in_order(user, mainwin, make_audio, tmp_path, qtbot):
    # The docs don't say; this is what puddletag does: files with the same
    # album keep the order they had, and the second click reverses the whole
    # list.
    music = tmp_path / 'music'
    paths = [make_audio(f'{name}.mp3', music, title=name, album=album)
             for name, album in [('a', 'xray'), ('b', 'yankee'), ('c', 'xray'), ('d', 'yankee')]]
    table = load(mainwin, qtbot, user, music)
    before = stamps(paths)
    click_header(user, 'album')
    assert names(table) == ['a.mp3', 'c.mp3', 'b.mp3', 'd.mp3']
    click_header(user, 'album')
    assert names(table) == ['b.mp3', 'd.mp3', 'a.mp3', 'c.mp3']
    untouched(before)


@pytest.mark.xfail(QLocale.system().collation().name() == 'C', strict=True,
                   reason="Numbers sort as text under the C locale")
def test_header_sorts_numbers_by_value(user, mainwin, make_audio, tmp_path, qtbot):
    # The docs don't say how numbers sort; natural_sort_key's own docstring
    # does: "Natural means sorting numbers by their numeric value, e.g. 100
    # comes after 99." So track 10 comes after 2 and 1.
    music = tmp_path / 'music'
    paths = [make_audio(f'{name}.mp3', music, title=name, tracknumber=track)
             for name, track in [('a', '10'), ('b', '2'), ('c', '1')]]
    table = load(mainwin, qtbot, user, music)
    before = stamps(paths)
    click_header(user, 'track')
    assert names(table) == ['c.mp3', 'b.mp3', 'a.mp3']
    untouched(before)


def test_header_sort_saved(user, mainwin, three):
    # "This sort order will be used when loading dirs unless changed (by
    # clicking a header or using another Sort Option.) It is saved across
    # sessions." (preferences.txt:49)
    table, paths = three
    before = stamps(paths)
    click_header(user, 'title')
    click_header(user, 'title')
    mainwin.close()
    config = PuddleConfig()
    assert config.get('table', 'sort_fields', []) == ['title']
    assert config.get('table', 'sort_reverse', False, True) is True
    untouched(before)


INCREASE_FONT = {
    'Edit menu': lambda user: user.click_menu('&Increase Font'),
    'shortcut': lambda user: user.press(Key.Key_Plus, Ctrl | Shift | Keypad),
}
DECREASE_FONT = {
    'Edit menu': lambda user: user.click_menu('&Decrease Font'),
    'shortcut': lambda user: user.press(Key.Key_Minus, Ctrl | Shift | Keypad),
}


@pytest.fixture
def one_file(mainwin, make_audio, tmp_path, qtbot, user):
    music = tmp_path / 'music'
    paths = [make_audio('01.mp3', music, title='Title 1')]
    table = load(mainwin, qtbot, user, music)
    return table, paths


@pytest.mark.parametrize('increase', INCREASE_FONT.values(), ids=INCREASE_FONT.keys())
def test_increase_font(mainwin, user, one_file, increase):
    # "Increases the File-View font." The docs don't say the row height; this
    # is what puddletag does: it stays as it was.
    table, paths = one_file
    before = stamps(paths)
    size = font_size(user)
    height = table.verticalHeader().defaultSectionSize()
    increase(user)
    assert font_size(user) == size + 1
    assert table.verticalHeader().defaultSectionSize() == height
    untouched(before)


@pytest.mark.parametrize('decrease', DECREASE_FONT.values(), ids=DECREASE_FONT.keys())
def test_decrease_font(mainwin, user, one_file, decrease):
    # "Increases the File-View font, but in reverse."
    table, paths = one_file
    before = stamps(paths)
    size = font_size(user)
    decrease(user)
    assert font_size(user) == size - 1
    untouched(before)


@pytest.mark.xfail(strict=True, reason='Decrease Font goes below 1 point, and the File-View '
                                       'falls back to the default size')
def test_decrease_font_stops_at_one_point(mainwin, user, one_file):
    # The docs don't say; this is what a user expects: Decrease Font stops
    # at the smallest size, 1 point.
    table, paths = one_file
    before = stamps(paths)
    size = font_size(user)
    for _ in range(size + 2):
        user.press(Key.Key_Minus, Ctrl | Shift | Keypad)
    assert font_size(user) == 1
    untouched(before)


@pytest.mark.xfail(strict=True, reason='Changing the font reports a changed range that starts '
                                       'past the last row')
def test_font_change_reports_valid_cells(mainwin, user, one_file, qtlog):
    # The docs don't say; this is what a user expects: changing the font
    # makes Qt report no invalid index range.
    table, paths = one_file
    before = stamps(paths)
    user.press(Key.Key_Plus, Ctrl | Shift | Keypad)
    assert not [r for r in qtlog.records if 'invalid index range' in r.message]
    untouched(before)


def test_font_size_saved(mainwin, user, one_file):
    # The docs don't say; this is what puddletag does: closing the window
    # saves the size, for the next start.
    table, paths = one_file
    before = stamps(paths)
    size = font_size(user)
    user.press(Key.Key_Plus, Ctrl | Shift | Keypad)
    mainwin.close()
    assert PuddleConfig().get('table', 'fontsize', 0, True) == size + 1
    untouched(before)
