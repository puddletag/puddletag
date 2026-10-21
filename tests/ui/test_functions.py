"""The Functions window, the Actions window, Quick Actions and the Functions
and Actions docks (tut2.txt, tut3.txt, menus.txt), run from the main window
as a user runs them: the Actions menu, the toolbar and the Tools menu, with
clicks in the dialogs. Each result is checked in the files and in the table.
Synthetic files, tags and function settings.
"""
import os

import mutagen.id3
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QPushButton, QStyle, QStyleOptionViewItem

from puddlestuff import audioinfo
from puddlestuff.actiondlg import ActionWindow, CreateFunction
from puddlestuff.mainwin.action_dialogs import ActionDialog, FunctionDialog

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier

FIELDS = ['album', 'artist', 'comment', 'genre', 'title']
NAMES = ['01.mp3', '02.mp3', '03.mp3']
COMMANDS = ['&Actions', '&Functions', '&QuickActions']


def tags(i):
    return {field: [f'{field} {i}'] for field in FIELDS}


def changed(i, case, fields):
    return dict(tags(i), **{field: [case(f'{field} {i}')] for field in fields})


def upper(text):
    return text.upper()


def mixed(text):
    return text.title()


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    music = tmp_path / 'music'
    paths = []
    for i in (1, 2, 3):
        path = make_audio(f'0{i}.mp3', music, album=f'album {i}', artist=f'artist {i}',
                          genre=f'genre {i}', title=f'title {i}')
        id3 = mutagen.id3.ID3(str(path))
        id3.add(mutagen.id3.COMM(encoding=3, lang='eng', desc='', text=[f'comment {i}']))
        id3.save()
        paths.append(path)
    mainwin.openDir(str(music), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == 3)
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]
    user.activate()
    table.setFocus()
    return table, paths


def in_files(paths):
    return [audioinfo.usertags(audioinfo.Tag(str(p))) for p in paths]


def in_table(table):
    return [audioinfo.usertags(audio) for audio in table.model().taginfo]


def written(qtbot, user, path, field, value):
    qtbot.waitUntil(lambda: audioinfo.Tag(str(path)).get(field) == value)
    user.activate()


def opened(qtbot, kind):
    qtbot.waitUntil(lambda: isinstance(QApplication.activeModalWidget(), kind))
    return QApplication.activeModalWidget()


def pick(user, qtbot, combo, text):
    row = combo.findText(text, Qt.MatchFlag.MatchFixedString)
    assert row != -1, text
    user.click(combo)
    view = combo.view()
    qtbot.waitUntil(view.isVisible)
    # A second click inside the double-click interval is read as one.
    qtbot.wait(QApplication.doubleClickInterval() + 100)
    index = combo.model().index(row, 0)
    view.scrollTo(index)
    user.click(view.viewport(), view.visualRect(index).center())
    qtbot.waitUntil(lambda: not view.isVisible())
    assert combo.currentIndex() == row


def upper_case(user, qtbot, window, fields):
    """Sets UPPER CASE on the Case Conversion function, with these fields."""
    pick(user, qtbot, window.functions, 'Case Conversion')
    function = window.stack.currentWidget()
    pick(user, qtbot, function.controls[0], 'UPPER CASE')
    user.activate(window)
    user.click(function.tagcombo.lineEdit())
    user.press(Key.Key_A, Ctrl)
    user.type(fields)
    assert function.tagcombo.currentText() == fields


def check(user, window, name):
    """Ticks the action's check box."""
    listbox = window.listbox
    [item] = listbox.findItems(name, Qt.MatchFlag.MatchExactly)
    option = QStyleOptionViewItem()
    listbox.initViewItemOption(option)
    option.rect = listbox.visualItemRect(item)
    option.features |= QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
    box = listbox.style().subElementRect(QStyle.SubElement.SE_ItemViewItemCheckIndicator, option, listbox)
    user.click(listbox.viewport(), box.center())
    assert item.checkState() == Qt.CheckState.Checked


def apply_button(dock):
    [button] = [b for b in dock.findChildren(QPushButton) if b.text() == 'Appl&y']
    return button


def select_titles(user):
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(1, 'title'), Shift)


def test_commands_need_a_selection(user, loaded):
    # "Click Apply to apply changes to the selected files" (menus.txt:351,
    # 355) and "run previously defined functions on the selected files"
    # (tut2.txt:50): with no file selected the commands are disabled.
    user.click_cell(user.cell(0, 'title'))
    assert [user.action(name).isEnabled() for name in COMMANDS] == [True] * 3
    user.click_cell(user.cell(0, 'title'), Ctrl)
    assert user.table.selectedRows == []
    assert [user.action(name).isEnabled() for name in COMMANDS] == [False] * 3


FUNCTIONS = {
    'Actions menu': lambda user: user.click_menu('&Functions'),
    'toolbar': lambda user: user.click_toolbar('&Functions'),
}


@pytest.mark.parametrize('open_functions', FUNCTIONS.values(), ids=FUNCTIONS.keys())
def test_functions_selected_cells(user, loaded, qtbot, open_functions):
    # "Having __selected as the field will apply the selected function to
    # the selected cells. So if you have the album field selected in one
    # file and artist in another. The function'll be applied to the album
    # field of the first file and artist of the other respectively."
    # (tut3.txt:89)
    table, paths = loaded
    user.click_cell(user.cell(0, 'album'))
    user.click_cell(user.cell(1, 'artist'), Ctrl)
    open_functions(user)
    window = opened(qtbot, CreateFunction)
    upper_case(user, qtbot, window, '__selected')
    user.click(window.okcancel.okButton)
    written(qtbot, user, paths[1], 'artist', ['ARTIST 2'])
    expected = [changed(1, upper, ['album']), changed(2, upper, ['artist']), tags(3)]
    assert in_files(paths) == expected
    assert in_table(table) == expected


def test_functions_all_fields(user, loaded, qtbot):
    # "__all will write to all the fields found in a file except filename
    # related fields like __dirname, __filename, etc." (tut3.txt:90) The
    # unselected third file is left alone ("each selected file", tut2.txt:34).
    table, paths = loaded
    select_titles(user)
    user.click_toolbar('&Functions')
    window = opened(qtbot, CreateFunction)
    upper_case(user, qtbot, window, '__all')
    user.click(window.okcancel.okButton)
    written(qtbot, user, paths[1], 'title', ['TITLE 2'])
    expected = [changed(1, upper, FIELDS), changed(2, upper, FIELDS), tags(3)]
    assert in_files(paths) == expected
    assert in_table(table) == expected
    assert sorted(os.listdir(paths[0].parent.parent)) == ['music']
    assert sorted(os.listdir(paths[0].parent)) == NAMES
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]


def test_functions_all_but(user, loaded, qtbot):
    # "If you want to write to all fields but the ones you specify use '~'.
    # Eg. ~artist, title, year will write to all but the artist, title and
    # year fields." (tut3.txt:93) The files have no year.
    table, paths = loaded
    select_titles(user)
    user.click_toolbar('&Functions')
    window = opened(qtbot, CreateFunction)
    upper_case(user, qtbot, window, '~artist, title, year')
    user.click(window.okcancel.okButton)
    written(qtbot, user, paths[1], 'album', ['ALBUM 2'])
    rest = ['album', 'comment', 'genre']
    expected = [changed(1, upper, rest), changed(2, upper, rest), tags(3)]
    assert in_files(paths) == expected
    assert in_table(table) == expected
    assert sorted(os.listdir(paths[0].parent)) == NAMES
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]


def test_functions_all_but_selected(user, loaded, qtbot):
    # "~__selected will write to all, but the selected." (tut3.txt:93)
    table, paths = loaded
    user.click_cell(user.cell(0, 'album'))
    user.click_cell(user.cell(1, 'artist'), Ctrl)
    user.click_toolbar('&Functions')
    window = opened(qtbot, CreateFunction)
    upper_case(user, qtbot, window, '~__selected')
    user.click(window.okcancel.okButton)
    written(qtbot, user, paths[1], 'title', ['TITLE 2'])
    expected = [changed(1, upper, [f for f in FIELDS if f != 'album']),
                changed(2, upper, [f for f in FIELDS if f != 'artist']), tags(3)]
    assert in_files(paths) == expected
    assert in_table(table) == expected


ACTIONS = {
    'Actions menu': lambda user: user.click_menu('&Actions'),
    'toolbar': lambda user: user.click_toolbar('&Actions'),
}


@pytest.mark.parametrize('open_actions', ACTIONS.values(), ids=ACTIONS.keys())
def test_actions_window(user, loaded, qtbot, open_actions):
    # Actions "run previously defined functions on the selected files"
    # (tut2.txt:50); the Case Conversion action "changes the album, title
    # and artist fields to 'Mixed Case'" (tut2.txt:58). The window's OK
    # runs the checked actions, and is disabled with none checked.
    table, paths = loaded
    select_titles(user)
    open_actions(user)
    window = opened(qtbot, ActionWindow)
    assert not window.okcancel.okButton.isEnabled()
    check(user, window, 'Case Conversion')
    user.click(window.okcancel.okButton)
    written(qtbot, user, paths[1], 'title', ['Title 2'])
    case = ['album', 'artist', 'title']
    expected = [changed(1, mixed, case), changed(2, mixed, case), tags(3)]
    assert in_files(paths) == expected
    assert in_table(table) == expected


QUICK_ACTIONS = {
    'Actions menu': lambda user: user.click_menu('&QuickActions'),
    'toolbar': lambda user: user.click_toolbar('&QuickActions'),
}


@pytest.mark.parametrize('open_quick_actions', QUICK_ACTIONS.values(), ids=QUICK_ACTIONS.keys())
def test_quick_action(user, loaded, qtbot, open_quick_actions):
    # "a Quick Action runs an action as normal but ignores the fields
    # defined in the functions and uses the selected cells" (tut2.txt:68):
    # Case Conversion on the genre and comment cells leaves album, artist
    # and title alone.
    table, paths = loaded
    user.click_cell(user.cell(0, 'genre'))
    user.click_cell(user.cell(1, 'comment'), Shift)
    open_quick_actions(user)
    window = opened(qtbot, ActionWindow)
    check(user, window, 'Case Conversion')
    user.click(window.okcancel.okButton)
    written(qtbot, user, paths[1], 'comment', ['Comment 2'])
    columns = ['comment', 'genre']
    expected = [changed(1, mixed, columns), changed(2, mixed, columns), tags(3)]
    assert in_files(paths) == expected
    assert in_table(table) == expected


def test_functions_dock_apply(user, loaded, qtbot, mainwin):
    # "Shows the Functions dialog as a tool window. Click Apply to apply
    # changes to the selected files." (menus.txt:351)
    table, paths = loaded
    select_titles(user)
    user.click_menu('Functions')
    [dock] = mainwin.findChildren(FunctionDialog)
    qtbot.waitUntil(dock.isVisible)
    # Only Apply shows (#519 reports OK and Cancel overlapping it).
    assert not dock.okcancel.okButton.isVisible()
    assert not dock.okcancel.cancelButton.isVisible()
    upper_case(user, qtbot, dock, '__selected')
    user.click(apply_button(dock))
    written(qtbot, user, paths[1], 'title', ['TITLE 2'])
    expected = [changed(1, upper, ['title']), changed(2, upper, ['title']), tags(3)]
    assert in_files(paths) == expected
    assert in_table(table) == expected


def test_actions_dock_apply(user, loaded, qtbot, mainwin):
    # "Shows the Actions dialog as a tool window. Click Apply to apply
    # changes to the selected files." (menus.txt:355)
    table, paths = loaded
    select_titles(user)
    user.click_menu('Actions')
    [dock] = mainwin.findChildren(ActionDialog)
    qtbot.waitUntil(dock.isVisible)
    # Only Apply shows (#519 reports OK and Cancel overlapping it).
    assert not dock.okcancel.okButton.isVisible()
    assert not dock.okcancel.cancelButton.isVisible()
    check(user, dock, 'Case Conversion')
    user.click(apply_button(dock))
    written(qtbot, user, paths[1], 'title', ['Title 2'])
    case = ['album', 'artist', 'title']
    expected = [changed(1, mixed, case), changed(2, mixed, case), tags(3)]
    assert in_files(paths) == expected
    assert in_table(table) == expected


def select_all(user):
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(2, 'title'), Shift)


def pick_autonumbering(user, qtbot, window):
    pick(user, qtbot, window.functions, 'Autonumbering')
    user.activate(window)
    user.click(window.stack.currentWidget().tagcombo.lineEdit())
    user.press(Key.Key_A, Ctrl)
    user.type('discnumber')


def open_functions_window(user, qtbot, mainwin):
    user.click_menu('&Functions')
    return opened(qtbot, CreateFunction)


def open_functions_dock(user, qtbot, mainwin):
    user.click_menu('Functions')
    [dock] = mainwin.findChildren(FunctionDialog)
    qtbot.waitUntil(dock.isVisible)
    return dock


@pytest.mark.parametrize('open_dialog', [open_functions_window, open_functions_dock],
                         ids=['window', 'dock'])
def test_autonumbering_function(user, loaded, qtbot, mainwin, open_dialog):
    # "Numbers tracks sequentially beginning with Start." (function.txt:21)
    # #429 and #482 report that running Autonumbering on a field from the
    # Functions window or dock hangs with a KeyError and writes nothing.
    # Synthetic: the field is discnumber, on three files.
    table, paths = loaded
    select_all(user)
    dialog = open_dialog(user, qtbot, mainwin)
    pick_autonumbering(user, qtbot, dialog)
    if isinstance(dialog, FunctionDialog):
        user.click(apply_button(dialog))
    else:
        user.click(dialog.okcancel.okButton)
    written(qtbot, user, paths[2], 'discnumber', ['3'])
    expected = [dict(tags(i), discnumber=[str(i)]) for i in (1, 2, 3)]
    assert in_files(paths) == expected
    assert in_table(table) == expected


def test_function_editor_width_is_bounded(user, loaded, qtbot):
    # #713 reports that editing a function with a long field list makes the
    # dialog wider than the screen. Synthetic: 2,500 characters of fields.
    table, paths = loaded
    select_titles(user)
    user.click_toolbar('&Functions')
    window = opened(qtbot, CreateFunction)
    pick(user, qtbot, window.functions, 'Case Conversion')
    function = window.stack.currentWidget()
    function.tagcombo.setEditText(', '.join(f'field{i:04}' for i in range(250)))
    assert len(function.tagcombo.currentText()) > 2000
    screen = QApplication.primaryScreen().availableGeometry().width()
    assert window.minimumSizeHint().width() < screen


@pytest.mark.parametrize('preview', [False, True], ids=['preview off', 'preview on'])
def test_functions_invalid_regexp(user, loaded, qtbot, dialogs, preview):
    # Synthetic regex `..)` from #576: Replace with RegExp "closes puddletag:
    # FuncError: unbalanced parenthesis at position 2". It should show the
    # error and leave the file unchanged, and set no preview in Preview Mode.
    table, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    if preview:
        user.press(Key.Key_P, Ctrl | Shift)
        assert table.model().previewMode
    user.click_menu('&Functions')
    window = opened(qtbot, CreateFunction)
    pick(user, qtbot, window.functions, 'Replace with RegExp')
    function = window.stack.currentWidget()
    user.activate(window)
    user.click(function.controls[0].combo.lineEdit())
    user.type('..)')
    assert function.controls[0].combo.currentText() == '..)'
    user.click(function.tagcombo.lineEdit())
    user.press(Key.Key_A, Ctrl)
    user.type('title')
    dialogs.answer('QMessageBox.warning', None)
    user.click(window.okcancel.okButton)
    qtbot.waitUntil(lambda: bool(dialogs.calls))
    [(name, args, kwargs)] = dialogs.calls
    assert name == 'QMessageBox.warning'
    assert 'unbalanced parenthesis at position 2' in args[2]
    user.activate()
    assert in_files(paths) == [tags(1), tags(2), tags(3)]
    assert in_table(table) == [tags(1), tags(2), tags(3)]
    assert [audio.preview for audio in table.model().taginfo] == [{}, {}, {}]
