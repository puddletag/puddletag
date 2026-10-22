"""The Filesystem dock (tut3.txt, menus.txt), used as a user uses it:
folders clicked in its tree, its right-click menu and Go to parent
folder. Each load is checked in the table and on disk. Synthetic files.
"""
import pytest
from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtWidgets import QApplication, QCheckBox, QMenu, QMessageBox, QStyle, QStyleOptionButton

from puddlestuff import audioinfo
from puddlestuff.mainwin.dirview import DirView, DirViewWidget
from puddlestuff.puddlesettings import SettingsDialog

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
NoModifier = Qt.KeyboardModifier.NoModifier
Shift = Qt.KeyboardModifier.ShiftModifier
No = QMessageBox.StandardButton.No
Yes = QMessageBox.StandardButton.Yes


@pytest.fixture
def music(make_audio, tmp_path):
    """a/01.mp3, a/sub/02.mp3, b/03.mp3 and c/04.mp3, each titled after
    its folder, keyed by folder."""
    return {name: make_audio(f'0{i}.mp3', tmp_path / name, artist='Artist', title=f'Title {name}')
            for i, name in enumerate(['a', 'a/sub', 'b', 'c'], 1)}


def in_file(path):
    return audioinfo.usertags(audioinfo.Tag(str(path)))


def loaded_paths(table):
    """Sorted: several folders load in no set order."""
    return sorted(audio.filepath for audio in table.model().taginfo)


def wait_for_rows(qtbot, table, paths):
    """Files load through a progress window: wait for the rows."""
    expected = sorted(str(p) for p in paths)
    qtbot.waitUntil(lambda: loaded_paths(table) == expected)


def tree(mainwin):
    [view] = mainwin.findChildren(DirView)
    return view


def selected_folders(view):
    model = view.model()
    return sorted({model.filePath(index) for index in view.selectedIndexes()})


def folder_pos(qtbot, view, path):
    """Where the folder's row is. scrollTo expands its parents, as a user
    does; the model lists each folder in a thread, so rows move until it's
    done: the position is taken in the check that finds the folder under
    it, and used right away."""
    index = view.model().index(str(path))
    view.scrollTo(index)
    pos = []
    qtbot.waitUntil(lambda: view.indexAt(view.visualRect(index).center()) == index
                    and not pos.append(view.visualRect(index).center()))
    return pos[-1]


def click_folder(user, qtbot, view, path, modifier=NoModifier):
    user.click(view.viewport(), folder_pos(qtbot, view, path), modifier)


def right_click(user, qtbot, widget, pos, text):
    """Right-clicks pos in widget and clicks text in the menu that opens;
    returns the menu's items. user.right_click finds a command by its
    data/shortcuts name; the dock builds its menu at each right-click."""
    menus = []

    def pick(tries=100):
        menu = QApplication.activePopupWidget()
        if not (isinstance(menu, QMenu) and menu.isVisible()):
            if tries:
                QTimer.singleShot(10, lambda: pick(tries - 1))
            return
        menus.append([action.text() for action in menu.actions()])
        found = [action for action in menu.actions() if action.text() == text]
        if found:
            user.click(menu, menu.actionGeometry(found[0]).center())
        else:
            menu.close()

    QTimer.singleShot(0, pick)
    window = widget.window()
    # As in user.right_click: a move to where the pointer already is sends
    # no mouse event.
    qtbot.mouseMove(window.windowHandle(), QPoint(5, 5))
    qtbot.mouseClick(window.windowHandle(), Qt.MouseButton.RightButton, NoModifier,
                     widget.mapTo(window, pos))
    assert menus, 'no right-click menu opened'
    assert text in menus[0], f'{text} is not in the right-click menu'
    user.activate(window)
    return menus[0]


def right_click_folder(user, qtbot, view, path, text):
    return right_click(user, qtbot, view.viewport(), folder_pos(qtbot, view, path), text)


def click_check_box(user, box):
    """At its indicator: the box stretches, and a click at its center
    misses it."""
    option = QStyleOptionButton()
    box.initStyleOption(option)
    user.click(box, box.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, box).center())


def open_preferences(mainwin, qtbot, user):
    user.click_menu('&Preferences')
    qtbot.waitUntil(lambda: any(w.isVisible() for w in mainwin.findChildren(SettingsDialog)))
    [window] = [w for w in mainwin.findChildren(SettingsDialog) if w.isVisible()]
    user.activate(window)
    return window


def set_subfolders(mainwin, qtbot, user, checked):
    """Preferences → General → Subfolders (its first page)."""
    window = open_preferences(mainwin, qtbot, user)
    [box] = [c for c in window.findChildren(QCheckBox) if c.text() == 'Su&bfolders']
    if box.isChecked() != checked:
        click_check_box(user, box)
    assert box.isChecked() == checked
    user.click(window.okbuttons.okButton)
    qtbot.waitUntil(lambda: not window.isVisible())
    user.activate()


def edit(user, qtbot, row, field, text):
    """Types text into the row's cell."""
    user.double_click_cell(user.cell(row, field))
    QApplication.focusWidget().selectAll()
    user.type(text)
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: user.table.model().data(user.cell(row, field)) == text)
    user.press(Key.Key_Escape)  # the next row's cell, which Enter opened


def titles(table):
    return sorted(audio['title'][0] for audio in table.model().taginfo)


def test_lists_folders_only(mainwin, music, tmp_path, qtbot, user):
    # menus.txt: "Displays the filesystem window which lists directories."
    (tmp_path / 'loose.mp3').write_bytes(b'')  # synthetic: a file beside the folders
    view = tree(mainwin)
    assert view.isVisible()
    assert user.action('Filesystem').isChecked()
    folder_pos(qtbot, view, tmp_path / 'a')
    model = view.model()
    root = model.index(str(tmp_path))

    def names():
        return sorted(model.fileName(model.index(row, 0, root)) for row in range(model.rowCount(root)))

    qtbot.waitUntil(lambda: names() == ['a', 'b', 'c'])


@pytest.mark.parametrize('subfolders', [False, True], ids=['off', 'on'])
def test_click_opens_folder(mainwin, music, tmp_path, qtbot, user, subfolders):
    # tut3.txt: "Click on a folder to open it." preferences.txt: "If checked,
    # Subfolders of directories selected for import will be checked for
    # supported files (which'll then be loaded). Otherwise, just files
    # residing in the selected directories will be loaded."
    set_subfolders(mainwin, qtbot, user, subfolders)
    view = tree(mainwin)
    click_folder(user, qtbot, view, tmp_path / 'a')
    expected = [music['a']] + ([music['a/sub']] if subfolders else [])
    wait_for_rows(qtbot, mainwin._table, expected)
    user.activate()
    assert titles(mainwin._table) == sorted(f'Title {name}' for name in ['a', 'a/sub'][:len(expected)])
    assert in_file(music['a'])['title'] == ['Title a']
    assert in_file(music['a/sub'])['title'] == ['Title a/sub']


def test_click_another_folder_replaces_the_files(mainwin, music, tmp_path, qtbot, user):
    # Synthetic (docs-silent): a click opens the folder as Open Folder does,
    # replacing the files shown.
    set_subfolders(mainwin, qtbot, user, False)
    view = tree(mainwin)
    click_folder(user, qtbot, view, tmp_path / 'a')
    wait_for_rows(qtbot, mainwin._table, [music['a']])
    user.activate()
    click_folder(user, qtbot, view, tmp_path / 'b')
    wait_for_rows(qtbot, mainwin._table, [music['b']])
    user.activate()
    assert selected_folders(view) == [str(tmp_path / 'b')]
    assert titles(mainwin._table) == ['Title b']
    assert in_file(music['a'])['title'] == ['Title a']
    assert in_file(music['b'])['title'] == ['Title b']


@pytest.mark.parametrize('modifier, folders', [(Ctrl, ['a', 'c']), (Shift, ['a', 'b', 'c'])],
                         ids=['Ctrl', 'Shift'])
def test_select_several_folders(mainwin, music, tmp_path, qtbot, user, modifier, folders):
    # tut3.txt: "You can select more than one folder at a time."
    set_subfolders(mainwin, qtbot, user, False)
    view = tree(mainwin)
    click_folder(user, qtbot, view, tmp_path / 'a')
    wait_for_rows(qtbot, mainwin._table, [music['a']])
    user.activate()
    click_folder(user, qtbot, view, tmp_path / 'c', modifier)
    wait_for_rows(qtbot, mainwin._table, [music[name] for name in folders])
    user.activate()
    assert selected_folders(view) == [str(tmp_path / name) for name in folders]
    assert titles(mainwin._table) == [f'Title {name}' for name in folders]
    for name in folders:
        assert in_file(music[name])['title'] == [f'Title {name}']


def test_ctrl_click_unloads_a_folder(mainwin, music, tmp_path, qtbot, user):
    # Synthetic (docs-silent): unselecting a folder unloads its files.
    set_subfolders(mainwin, qtbot, user, False)
    view = tree(mainwin)
    click_folder(user, qtbot, view, tmp_path / 'a')
    wait_for_rows(qtbot, mainwin._table, [music['a']])
    user.activate()
    click_folder(user, qtbot, view, tmp_path / 'b', Ctrl)
    wait_for_rows(qtbot, mainwin._table, [music['a'], music['b']])
    user.activate()
    click_folder(user, qtbot, view, tmp_path / 'a', Ctrl)
    wait_for_rows(qtbot, mainwin._table, [music['b']])
    user.activate()
    assert selected_folders(view) == [str(tmp_path / 'b')]
    assert titles(mainwin._table) == ['Title b']
    assert in_file(music['a'])['title'] == ['Title a']
    assert in_file(music['b'])['title'] == ['Title b']


def test_click_non_ascii_folder(mainwin, make_audio, tmp_path, qtbot, user):
    # preferences.txt: "If checked, Subfolders of directories selected for
    # import will be checked for supported files (which'll then be loaded)."
    # #398: folders with a Λ "are not descended in to search for files".
    # Synthetic names.
    first = make_audio('01.mp3', tmp_path / 'Λ folder', title='First')
    second = make_audio('02 Λ.mp3', tmp_path / 'Λ folder' / 'Λ', title='Second')
    set_subfolders(mainwin, qtbot, user, True)
    click_folder(user, qtbot, tree(mainwin), tmp_path / 'Λ folder')
    wait_for_rows(qtbot, mainwin._table, [first, second])
    user.activate()
    assert titles(mainwin._table) == ['First', 'Second']
    assert in_file(first)['title'] == ['First']
    assert in_file(second)['title'] == ['Second']


def test_right_click_loads_nothing(mainwin, music, tmp_path, qtbot, user):
    # Synthetic (docs-silent): a right-click only opens the menu.
    set_subfolders(mainwin, qtbot, user, False)
    view = tree(mainwin)
    click_folder(user, qtbot, view, tmp_path / 'a')
    wait_for_rows(qtbot, mainwin._table, [music['a']])
    user.activate()
    right_click_folder(user, qtbot, view, tmp_path / 'b', 'Show Header')
    wait_for_rows(qtbot, mainwin._table, [music['a']])
    assert selected_folders(view) == [str(tmp_path / 'a')]
    assert titles(mainwin._table) == ['Title a']
    assert in_file(music['a'])['title'] == ['Title a']
    assert in_file(music['b'])['title'] == ['Title b']


def test_ctrl_click_unloads_subfolders(mainwin, music, tmp_path, qtbot, user):
    # preferences.txt: "If checked, Subfolders of directories selected for
    # import will be checked for supported files (which'll then be loaded)."
    # So unselecting a folder unloads its subfolders' files too (synthetic).
    view = tree(mainwin)
    set_subfolders(mainwin, qtbot, user, True)
    click_folder(user, qtbot, view, tmp_path / 'a')
    wait_for_rows(qtbot, mainwin._table, [music['a'], music['a/sub']])
    user.activate()
    click_folder(user, qtbot, view, tmp_path / 'b', Ctrl)
    wait_for_rows(qtbot, mainwin._table, [music['a'], music['a/sub'], music['b']])
    user.activate()
    click_folder(user, qtbot, view, tmp_path / 'a', Ctrl)
    wait_for_rows(qtbot, mainwin._table, [music['b']])
    assert selected_folders(view) == [str(tmp_path / 'b')]
    for name in ['a', 'a/sub', 'b']:
        assert in_file(music[name])['title'] == [f'Title {name}']


# Unsaved previews and clicks in the tree

def with_preview(mainwin, qtbot, tmp_path, user, music):
    """Subfolders off, folder a loaded by a click and its title edited in
    Preview Mode; returns the table and the tree."""
    set_subfolders(mainwin, qtbot, user, False)
    table, view = mainwin._table, tree(mainwin)
    click_folder(user, qtbot, view, tmp_path / 'a')
    wait_for_rows(qtbot, table, [music['a']])
    user.activate()
    user.click_menu('Enabl&e Preview Mode')
    edit(user, qtbot, 0, 'title', 'New')
    return table, view


def assert_preview_kept(user, table):
    model = table.model()
    index = user.cell(0, 'title')
    assert model.data(index) == 'New'
    assert model.data(index, Qt.ItemDataRole.FontRole).bold()


@pytest.mark.parametrize('answer', [pytest.param(No, id='No'), pytest.param(Yes, id='Yes')])
def test_click_with_previews_asks(mainwin, qtbot, tmp_path, user, dialogs, music, answer):
    # Synthetic (docs-silent): like Open Folder, a click that replaces the
    # files asks before dropping unsaved previews; No keeps the table and
    # the tree as they were.
    table, view = with_preview(mainwin, qtbot, tmp_path, user, music)
    dialogs.answer('QMessageBox.question', answer)
    click_folder(user, qtbot, view, tmp_path / 'b')
    qtbot.waitUntil(lambda: not dialogs.unused_answers(), timeout=2000)
    if answer == No:
        assert loaded_paths(table) == [str(music['a'])]
        assert_preview_kept(user, table)
        assert selected_folders(view) == [str(tmp_path / 'a')]
    else:
        wait_for_rows(qtbot, table, [music['b']])
        qtbot.waitUntil(lambda: selected_folders(view) == [str(tmp_path / 'b')])
    assert in_file(music['a'])['title'] == ['Title a']


def test_ctrl_click_keeps_previews(mainwin, qtbot, tmp_path, user, dialogs, music):
    # Synthetic (docs-silent): like Add Folder, adding a folder keeps the
    # previews and asks nothing.
    table, view = with_preview(mainwin, qtbot, tmp_path, user, music)
    click_folder(user, qtbot, view, tmp_path / 'b', Ctrl)
    wait_for_rows(qtbot, table, [music['a'], music['b']])
    assert not dialogs.calls
    assert_preview_kept(user, table)
    assert in_file(music['a'])['title'] == ['Title a']


@pytest.mark.xfail(strict=True, reason='https://github.com/puddletag/puddletag/issues/59')
def test_arrow_keys_open_the_next_folder(mainwin, music, tmp_path, qtbot, user):
    # "Click on a folder to open it." (tut3.txt); issue #59: "Cannot navigate
    # Filesystem view using arrow keys on the keyboard".
    set_subfolders(mainwin, qtbot, user, False)
    view = tree(mainwin)
    table = mainwin._table
    click_folder(user, qtbot, view, tmp_path / 'a')
    wait_for_rows(qtbot, table, [music['a']])
    user.activate()
    user.press(Key.Key_Down)
    wait_for_rows(qtbot, table, [music['b']])
    user.activate()
    user.press(Key.Key_Down)
    wait_for_rows(qtbot, table, [music['c']])
    for name in ['a', 'b', 'c']:
        assert in_file(music[name])['title'] == [f'Title {name}']


def test_subfolders_box(mainwin, music, tmp_path, qtbot, user):
    # preferences.txt: "If checked, Subfolders of directories selected for
    # import will be checked for supported files (which'll then be loaded).
    # Otherwise, just files residing in the selected directories will be
    # loaded." The dock's box is the same setting.
    box = mainwin.findChildren(DirViewWidget)[0].subfolderCheck
    click_check_box(user, box)
    assert not box.isChecked()
    click_check_box(user, box)
    assert box.isChecked()
    click_folder(user, qtbot, tree(mainwin), tmp_path / 'a')
    wait_for_rows(qtbot, mainwin._table, [music['a'], music['a/sub']])
    assert in_file(music['a'])['title'] == ['Title a']


def test_subfolders_box_follows_preferences(mainwin, qtbot, user):
    # Synthetic (docs-silent): the dock's box shows the setting Preferences
    # changed.
    box = mainwin.findChildren(DirViewWidget)[0].subfolderCheck
    assert box.isChecked()
    set_subfolders(mainwin, qtbot, user, False)
    assert not box.isChecked()


def test_right_click_menu_items(mainwin, music, tmp_path, qtbot, user):
    # "Right click on any folder to get a Context Menu." (tut3.txt)
    # "Right click on a directory and click on **Refresh Directory** to
    # refresh it. Also in that context menu, **Show Header** ... and **Open
    # in File Manager** ..." (menus.txt)
    view = tree(mainwin)
    items = right_click_folder(user, qtbot, view, tmp_path / 'a', 'Show Header')
    assert items == ['Refresh Directory', 'Show Header', 'Open in File Manager']


def test_show_header(mainwin, music, tmp_path, qtbot, user):
    # "**Show Header** will show the Filesystem header which displays extra
    # info." (menus.txt)
    view = tree(mainwin)
    assert view.isHeaderHidden()
    right_click_folder(user, qtbot, view, tmp_path / 'a', 'Show Header')
    assert not view.isHeaderHidden()
    header = view.header()
    items = right_click(user, qtbot, header.viewport(),
                        QPoint(header.sectionViewportPosition(0) + 5, header.height() // 2), 'Size')
    assert items == ['Name', 'Size', 'Type', 'Date Modified']
    assert not header.isSectionHidden(1)


def test_hide_header(mainwin, music, tmp_path, qtbot, user):
    # Synthetic (docs-silent): once shown, the same item reads Hide Header
    # and hides it.
    view = tree(mainwin)
    right_click_folder(user, qtbot, view, tmp_path / 'a', 'Show Header')
    assert not view.isHeaderHidden()
    items = right_click_folder(user, qtbot, view, tmp_path / 'a', 'Hide Header')
    assert items == ['Refresh Directory', 'Hide Header', 'Open in File Manager']
    assert view.isHeaderHidden()


def test_open_in_file_manager(mainwin, music, tmp_path, qtbot, user, monkeypatch):
    # "**Open in File Manager** will open the directory in the desktop's
    # file manager." (menus.txt)
    opened = []
    monkeypatch.setattr('puddlestuff.mainwin.dirview.QDesktopServices.openUrl',
                        lambda url: opened.append(url.toLocalFile()))
    view = tree(mainwin)
    right_click_folder(user, qtbot, view, tmp_path / 'b', 'Open in File Manager')
    assert opened == [str(tmp_path / 'b')]
    assert mainwin._table.model().rowCount() == 0


def test_refresh_directory(mainwin, music, tmp_path, qtbot, user):
    # "Right click on a directory and click on **Refresh Directory** to
    # refresh it." (menus.txt) The new folder shows through the model's
    # file watcher, whatever Refresh Directory does.
    view = tree(mainwin)
    model = view.model()
    parent = model.index(str(tmp_path))

    def names():
        return sorted(model.fileName(model.index(row, 0, parent)) for row in range(model.rowCount(parent)))

    folder_pos(qtbot, view, tmp_path / 'a')
    qtbot.waitUntil(lambda: names() == ['a', 'b', 'c'])
    (tmp_path / 'new').mkdir()
    right_click_folder(user, qtbot, view, tmp_path, 'Refresh Directory')
    qtbot.waitUntil(lambda: 'new' in names())


GO_TO_PARENT = {
    'Actions menu': lambda user: user.click_menu('&Go to parent folder'),
    'toolbar': lambda user: user.click_toolbar('&Go to parent folder'),
}


@pytest.mark.parametrize('run', GO_TO_PARENT.values(), ids=GO_TO_PARENT.keys())
def test_go_to_parent_folder(mainwin, music, tmp_path, qtbot, user, run):
    # menus.txt: "Opens the filesystem dock (if not already opened) and
    # navigates to the folder which contains the selected file."
    view = tree(mainwin)
    set_subfolders(mainwin, qtbot, user, True)
    mainwin.openDir(str(tmp_path / 'a'), False)
    wait_for_rows(qtbot, mainwin._table, [music['a'], music['a/sub']])
    qtbot.waitUntil(lambda: selected_folders(view) == [str(tmp_path / 'a')] and view.isEnabled())
    user.activate()
    user.click_menu('Filesystem')
    qtbot.waitUntil(lambda: not view.isVisible())
    row = [audio.filepath for audio in mainwin._table.model().taginfo].index(str(music['a/sub']))
    user.click_cell(user.cell(row, 'title'))
    run(user)
    qtbot.waitUntil(lambda: selected_folders(view) == [str(tmp_path / 'a' / 'sub')] and view.isEnabled())
    assert view.isVisible()
    assert user.action('Filesystem').isChecked()
    assert view.model().filePath(view.currentIndex()) == str(tmp_path / 'a' / 'sub')
    assert view.isExpanded(view.model().index(str(tmp_path / 'a')))
    assert view.viewport().rect().intersects(view.visualRect(view.currentIndex()))
    # It only navigates: nothing is loaded.
    assert loaded_paths(mainwin._table) == sorted(str(p) for p in (music['a'], music['a/sub']))
    assert in_file(music['a'])['title'] == ['Title a']


def test_go_to_parent_folder_greyed_out_without_selection(mainwin, music, tmp_path, qtbot, user):
    # Synthetic (docs-silent beyond "the selected file"): with no file
    # selected there is no folder to go to.
    set_subfolders(mainwin, qtbot, user, False)
    mainwin.openDir(str(tmp_path / 'a'), False)
    wait_for_rows(qtbot, mainwin._table, [music['a']])
    user.activate()
    action = user.action('&Go to parent folder')
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(0, 'title'), Ctrl)
    assert not action.isEnabled()
    user.click_cell(user.cell(0, 'title'))
    assert action.isEnabled()


def test_go_to_parent_folder_greyed_out_with_no_files(mainwin, user):
    # Synthetic (docs-silent): with no files loaded nothing is selected.
    assert not user.action('&Go to parent folder').isEnabled()


def test_go_to_parent_folder_after_unloading_a_folder(mainwin, qtbot, user, music, tmp_path):
    # menus.txt: "Opens the filesystem dock (if not already opened) and
    # navigates to the folder which contains the selected file." It works
    # every time, also right after a Ctrl-click that unselected a folder.
    view = tree(mainwin)
    set_subfolders(mainwin, qtbot, user, True)
    click_folder(user, qtbot, view, tmp_path / 'a')
    wait_for_rows(qtbot, user.table, [music['a'], music['a/sub']])
    user.activate()
    click_folder(user, qtbot, view, tmp_path / 'b', Ctrl)
    wait_for_rows(qtbot, user.table, [music['a'], music['a/sub'], music['b']])
    user.activate()
    click_folder(user, qtbot, view, tmp_path / 'b', Ctrl)
    wait_for_rows(qtbot, user.table, [music['a'], music['a/sub']])
    assert selected_folders(view) == [str(tmp_path / 'a')]
    user.activate()
    row = [audio.filepath for audio in user.table.model().taginfo].index(str(music['a/sub']))
    user.click_cell(user.cell(row, 'title'))
    user.click_menu('&Go to parent folder')
    qtbot.waitUntil(lambda: selected_folders(view) == [str(tmp_path / 'a' / 'sub')] and view.isEnabled(),
                    timeout=2000)
    assert in_file(music['a'])['title'] == ['Title a']
