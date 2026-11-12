"""The Tag Panel, as a user uses it: select files in the File-View, fill in
a field, Save (menus.txt: "Select some files, fill in some text and save
the changes (File->Save)"). Each save is checked in the files and in the
panel. Synthetic files.
"""
import os

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLineEdit, QStyle, QStyleOptionComboBox, QToolButton

from puddlestuff import audioinfo, constants
from puddlestuff.mainwin import tagpanel
from puddlestuff.mainwin.tagpanel import FrameCombo
from puddlestuff.puddletag import status

pytestmark = pytest.mark.ui

Key = Qt.Key
Alt = Qt.KeyboardModifier.AltModifier
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    """Three MP3s, all selected: the same artist, each its own title, and
    an album in the first two only."""
    music = tmp_path / 'music'
    paths = [make_audio('01.mp3', music, artist='Same', title='T1', album='A1'),
             make_audio('02.mp3', music, artist='Same', title='T2', album='A2'),
             make_audio('03.mp3', music, artist='Same', title='T3')]
    mainwin.openDir(str(music), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == 3)
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]
    user.activate()
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(2, 'title'), Shift)
    assert table.selectedRows == [0, 1, 2]
    # Qt counts the presses of an ambiguous shortcut for the whole app,
    # across windows (see test_alt_letter_again). Pressing Alt+B, the
    # Album field's own letter, starts each test as a session starts.
    user.press(Key.Key_B, Alt)
    [panel] = mainwin.findChildren(FrameCombo)
    return panel, paths


def in_file(path):
    return audioinfo.usertags(audioinfo.Tag(str(path)))


def shown(panel):
    return {field: combo.currentText() for field, combo in panel.combos.items()}


def listed(combo):
    return [combo.itemText(i) for i in range(combo.count())]


def fill(user, panel, field, text):
    """Clicks into the field, selects its text and types over it."""
    user.click(panel.combos[field].lineEdit())
    user.press(Key.Key_A, Ctrl)
    user.type(text)


def saved(qtbot, paths, field, value):
    """Saving several files writes them in a thread, behind a progress
    window."""
    qtbot.waitUntil(lambda: all(in_file(p).get(field) == value for p in paths))


def focused_field(panel):
    widget = QApplication.focusWidget()
    return next((field for field, combo in panel.combos.items()
                 if widget in (combo, combo.lineEdit())), None)


# "Notice that the artist combo box contains Bob Marley & The Wailers.
# This is because all files have the same artist. On occasions where the
# value differs between files it would contain <keep>" (tut1.txt): a
# field one file lacks differs too.

def test_shown_values(loaded):
    panel, paths = loaded
    assert shown(panel) == {'album': '<keep>', 'artist': 'Same', 'comment': '', 'genre': '',
                            'title': '<keep>', 'track': '', 'year': ''}


# Save: "Save's whatever's currently entered in the Tag Panel to the
# selected files" (menus.txt), from File->Save, its toolbar button
# ("click Save", tut1.txt) or Ctrl+S.

SAVE = {
    'File menu': lambda user: user.click_menu('&Save'),
    'toolbar': lambda user: user.click_toolbar('&Save'),
    'Ctrl+S': lambda user: user.press(Key.Key_S, Ctrl),
}


@pytest.mark.parametrize('save', SAVE.values(), ids=SAVE.keys())
def test_save(user, loaded, qtbot, save):
    panel, paths = loaded
    fill(user, panel, 'album', 'New album')
    save(user)
    saved(qtbot, paths, 'album', ['New album'])
    assert [in_file(p) for p in paths] == [
        {'album': ['New album'], 'artist': ['Same'], 'title': ['T1']},
        {'album': ['New album'], 'artist': ['Same'], 'title': ['T2']},
        {'album': ['New album'], 'artist': ['Same'], 'title': ['T3']}]
    assert [audio['album'] for audio in user.table.model().taginfo] == [['New album']] * 3
    assert shown(panel)['album'] == 'New album'


def test_nothing_written_before_save(user, loaded, qtbot):
    # "fill in some text and save the changes": filling in alone writes
    # nothing.
    panel, paths = loaded
    fill(user, panel, 'album', 'New album')
    user.press(Key.Key_Tab)
    qtbot.wait(200)
    assert [in_file(p).get('album') for p in paths] == [['A1'], ['A2'], None]


def test_keep_leaves_each_files_value(user, loaded, qtbot):
    # "<keep>, signifying that upon saving that field will remain unchanged
    # for each file" (tut1.txt): album and title stay <keep>.
    panel, paths = loaded
    fill(user, panel, 'artist', 'New artist')
    user.press(Key.Key_S, Ctrl)
    saved(qtbot, paths, 'artist', ['New artist'])
    assert [in_file(p) for p in paths] == [
        {'album': ['A1'], 'artist': ['New artist'], 'title': ['T1']},
        {'album': ['A2'], 'artist': ['New artist'], 'title': ['T2']},
        {'artist': ['New artist'], 'title': ['T3']}]


def test_blank_removes_the_field(user, loaded, qtbot):
    # "To remove a field, change the text to <blank> and the field'll be
    # removed upon saving." (tut1.txt)
    panel, paths = loaded
    fill(user, panel, 'artist', '<blank>')
    user.press(Key.Key_S, Ctrl)
    saved(qtbot, paths, 'artist', None)
    assert [in_file(p) for p in paths] == [{'album': ['A1'], 'title': ['T1']},
                                           {'album': ['A2'], 'title': ['T2']},
                                           {'title': ['T3']}]
    assert 'artist' not in user.table.model().taginfo[0]


def test_multiple_values(user, loaded, qtbot):
    # "Like in the file-view multiple values are shown like value1\\value2.
    # Entering any value like that will automatically split it." (tut3.txt)
    panel, paths = loaded
    fill(user, panel, 'title', 'One\\\\Two')
    user.press(Key.Key_S, Ctrl)
    saved(qtbot, paths, 'title', ['One', 'Two'])
    assert shown(panel)['title'] == 'One\\\\Two'


def test_genre_list(loaded):
    # "The list of genres as used in the Tag Panel" (preferences.txt): a
    # fresh profile's, ID3's genres, before the selected files' values.
    panel, paths = loaded
    assert listed(panel.combos['genre']) == ['<keep>', '<blank>'] + audioinfo.GENRES + ['']


# "Use & in your Title to create an accelerator eg. '&Artist' will allow
# you to set focus to the relevant combo box by pressing 'Alt+A'"
# (preferences.txt); "Pressing Alt+B will switch the focus to the Album
# field" (tut3.txt). A fresh profile's titles: &Artist, &Title, Al&bum,
# T&rack, &Year, &Genre, &Comment.

LETTERS = {'A': 'artist', 'B': 'album', 'C': 'comment', 'G': 'genre', 'R': 'track', 'T': 'title',
           'Y': 'year'}
# These are also the letters of menus: Qt then alternates between the
# field and the menu, so every other press opens the menu.
MENUS = {'A': '&Actions', 'C': '&Convert', 'G': 'Ta&g Tools', 'T': '&Tools'}


@pytest.mark.parametrize('letter, field', LETTERS.items())
def test_alt_letter(user, loaded, letter, field):
    panel, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    user.press(getattr(Key, 'Key_' + letter), Alt)
    assert focused_field(panel) == field


def again(letter, field):
    if letter not in MENUS:
        return letter, field
    return pytest.param(letter, field, marks=pytest.mark.xfail(
        strict=True, reason=f'Alt+{letter} is also the {MENUS[letter]} menu\'s letter'))


@pytest.mark.parametrize('letter, field', [again(*item) for item in LETTERS.items()])
def test_alt_letter_again(user, loaded, letter, field):
    panel, paths = loaded
    key = getattr(Key, 'Key_' + letter)
    user.click_cell(user.cell(0, 'title'))
    user.press(key, Alt)
    user.click_cell(user.cell(1, 'title'))
    user.press(key, Alt)
    focused = focused_field(panel)
    menu = QApplication.activePopupWidget()
    if menu:
        menu.close()
    assert (focused, menu and menu.title()) == (field, None)


def test_tab_through_the_fields(user, loaded):
    # "I usually just switch to the first (Artist) and TAB through
    # everything." (tut3.txt)
    panel, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    user.press(Key.Key_A, Alt)
    order = [focused_field(panel)]
    for i in range(6):
        user.press(Key.Key_Tab)
        order.append(focused_field(panel))
    assert order == ['artist', 'title', 'album', 'track', 'year', 'genre', 'comment']


def test_save_undone_in_one_step(user, loaded, qtbot):
    # "Edit→Undo puts back all the files a Save wrote to, at once." (Ctrl+Z
    # in a Tag Panel field undoes the typing in the field.)
    panel, paths = loaded
    fill(user, panel, 'album', 'New album')
    user.press(Key.Key_S, Ctrl)
    saved(qtbot, paths, 'album', ['New album'])
    user.activate()
    user.click_menu('&Undo')
    assert [in_file(p).get('album') for p in paths] == [['A1'], ['A2'], None]
    assert [audio.get('album') for audio in user.table.model().taginfo] == [['A1'], ['A2'], None]
    assert not user.action('&Undo').isEnabled()


def test_cleared_field_removed(user, loaded, qtbot):
    # "Clearing a field removes it on saving, as <blank> does."
    panel, paths = loaded
    fill(user, panel, 'artist', '')
    user.press(Key.Key_Delete)
    assert shown(panel)['artist'] == ''
    user.press(Key.Key_S, Ctrl)
    saved(qtbot, paths, 'artist', None)
    assert [in_file(p) for p in paths] == [{'album': ['A1'], 'title': ['T1']},
                                           {'album': ['A2'], 'title': ['T2']},
                                           {'title': ['T3']}]


def test_pick_from_the_list(user, loaded, qtbot):
    # "Each field's list holds <keep>, <blank> and the values the selected
    # files have: pick one to give it to all of them." The file without an
    # album adds an empty value.
    panel, paths = loaded
    combo = panel.combos['album']
    option = QStyleOptionComboBox()
    combo.initStyleOption(option)
    arrow = combo.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, option,
                                         QStyle.SubControl.SC_ComboBoxArrow, combo)
    user.click(combo, arrow.center())
    view = combo.view()
    qtbot.waitUntil(view.isVisible)
    assert listed(combo) == ['<keep>', '<blank>', '', 'A1', 'A2']
    # Qt ignores a click on the list sooner than a double-click's interval
    # after it opened: it could be the end of the click that opened it.
    qtbot.wait(QApplication.doubleClickInterval() + 100)
    user.click(view.viewport(), view.visualRect(combo.model().index(combo.findText('A2'), 0)).center())
    qtbot.waitUntil(lambda: not view.isVisible())
    assert shown(panel)['album'] == 'A2'
    user.press(Key.Key_S, Ctrl)
    saved(qtbot, paths, 'album', ['A2'])


def test_unchanged_save_writes_nothing(user, loaded, qtbot):
    # The docs don't say; this is what puddletag does: nothing is saved,
    # and there's nothing to undo.
    panel, paths = loaded
    for path in paths:
        os.utime(path, (1000000000, 1000000000))
    user.press(Key.Key_S, Ctrl)
    qtbot.wait(200)
    assert [os.stat(p).st_mtime for p in paths] == [1000000000] * 3
    assert not user.action('&Undo').isEnabled()


def test_selecting_other_files_drops_unsaved_text(user, loaded, qtbot):
    # "What you type is written when you Save (File→Save). Selecting other
    # files before that throws it away." #878 asks for a question first.
    panel, paths = loaded
    fill(user, panel, 'album', 'Typed')
    user.click_cell(user.cell(0, 'title'))
    assert shown(panel)['album'] == 'A1'
    user.press(Key.Key_S, Ctrl)
    qtbot.wait(200)
    assert [in_file(p).get('album') for p in paths] == [['A1'], ['A2'], None]


def test_new_genre_joins_the_list(mainwin, user, loaded, qtbot):
    # "A genre you save in the Tag Panel that isn't in the list is added to
    # it" (preferences.txt): offered for other files, and kept when
    # puddletag closes.
    panel, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(1, 'title'), Shift)
    fill(user, panel, 'genre', 'Synthetic Genre')
    user.press(Key.Key_S, Ctrl)
    saved(qtbot, paths[:2], 'genre', ['Synthetic Genre'])
    user.activate()
    user.click_cell(user.cell(2, 'title'))
    assert 'Synthetic Genre' in listed(panel.combos['genre'])
    mainwin.close()
    with open(os.path.join(constants.CONFIGDIR, 'genres')) as genres:
        assert 'Synthetic Genre' in genres.read().splitlines()


def test_nothing_selected(user, loaded):
    # The docs don't say; this is what puddletag does.
    panel, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(0, 'title'), Ctrl)
    assert user.table.selectedRows == []
    assert shown(panel) == dict.fromkeys(panel.combos, '')
    assert not any(combo.isEnabled() for combo in panel.combos.values())
    assert not user.action('&Save').isEnabled()


def preview(user):
    """Ctrl+Shift+P, Preview Mode's shortcut."""
    user.press(Key.Key_P, Ctrl | Shift)


def pick(user, qtbot, panel, field, text):
    """Opens the field's list with its arrow and clicks text, as
    test_pick_from_the_list does."""
    combo = panel.combos[field]
    option = QStyleOptionComboBox()
    combo.initStyleOption(option)
    arrow = combo.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, option,
                                         QStyle.SubControl.SC_ComboBoxArrow, combo)
    user.click(combo, arrow.center())
    view = combo.view()
    qtbot.waitUntil(view.isVisible)
    qtbot.wait(QApplication.doubleClickInterval() + 100)
    user.click(view.viewport(), view.visualRect(combo.model().index(combo.findText(text), 0)).center())
    qtbot.waitUntil(lambda: not view.isVisible())


def settings_page(user):
    """Edit > Preferences > Tag Panel: the window and its page."""
    window = user.open_preferences('Tag Panel')
    return window, window.stack.currentWidget()


def page_button(page, tooltip):
    [button] = [b for b in page.findChildren(QToolButton) if b.toolTip() == tooltip]
    return button


def rows(page):
    table = page._table
    return [table.texts(row) for row in range(table.rowCount())]


def click_row(user, page, row, modifier=Qt.KeyboardModifier.NoModifier):
    """Clicks the row's Title cell."""
    table = page._table
    user.click(table.viewport(), table.visualItemRect(table.item(row, 0)).center(), modifier)


def type_into_editor(user, text):
    """Types over the open cell editor's text and presses Enter."""
    QApplication.focusWidget().selectAll()
    user.type(text)
    user.press(Key.Key_Return)


def edit_cell(user, page, row, column, text):
    """Double-clicks the cell and types over it."""
    table = page._table
    user.double_click(table.viewport(), table.visualItemRect(table.item(row, column)).center())
    type_into_editor(user, text)


def panel_rows(panel):
    """The panel's fields, row by row, each row left to right."""
    combos = sorted(panel.combos.items(), key=lambda item: (item[1].y(), item[1].x()))
    shown = {}
    for field, combo in combos:
        shown.setdefault(combo.y(), []).append(field)
    return list(shown.values())


def editor_open(page):
    editor = QApplication.focusWidget()
    return isinstance(editor, QLineEdit) and editor.parent() is page._table.viewport()


# Preferences > Tag Panel: "puddletag will show the Title above a combo box
# that'll be populated using the field you specify in the Field column."
# "Row refers to the row number in which to show the field. If more than
# one row contains the same number, the fields will be listed on one row."
# (preferences.txt)

def test_settings_add_makes_a_field_on_a_new_row(mainwin, user):
    # The docs don't say what Add does; this is what puddletag does.
    window, page = settings_page(user)
    user.click(page_button(page, 'Add'))
    assert rows(page)[-1] == ['Title', 'field', '5']
    assert editor_open(page)
    type_into_editor(user, 'Disc')
    edit_cell(user, page, 7, 1, 'discnumber')
    user.close_preferences(window)
    [panel] = mainwin.findChildren(FrameCombo)
    assert panel_rows(panel) == [['artist'], ['title'], ['album'], ['track', 'year', 'genre'],
                                 ['comment'], ['discnumber']]
    assert panel.labels['discnumber'].text() == 'Disc'
    assert tagpanel.loadsettings()[5] == [('Disc', 'discnumber')]


def test_settings_edit_renames_a_title(mainwin, user):
    window, page = settings_page(user)
    click_row(user, page, 0)
    user.click(page_button(page, 'Edit'))
    type_into_editor(user, 'Band')
    user.close_preferences(window)
    [panel] = mainwin.findChildren(FrameCombo)
    assert panel.labels['artist'].text() == 'Band'
    assert panel_rows(panel) == [['artist'], ['title'], ['album'], ['track', 'year', 'genre'],
                                 ['comment']]


def test_settings_duplicate_puts_two_fields_on_one_row(mainwin, user):
    window, page = settings_page(user)
    click_row(user, page, 2)
    user.click(page_button(page, 'Duplicate'))
    assert rows(page)[-1] == ['Al&bum', 'album', '2']
    assert editor_open(page)
    type_into_editor(user, 'Album artist')
    edit_cell(user, page, 7, 1, 'albumartist')
    user.close_preferences(window)
    [panel] = mainwin.findChildren(FrameCombo)
    assert panel_rows(panel)[2] == ['album', 'albumartist']


def test_settings_remove_drops_the_selected_rows(mainwin, user):
    # The docs don't say what Remove does; the rows left make the panel.
    window, page = settings_page(user)
    click_row(user, page, 5)
    click_row(user, page, 6, Ctrl)
    user.click(page_button(page, 'Remove'))
    assert [r[1] for r in rows(page)] == ['artist', 'title', 'album', 'track', 'year']
    user.close_preferences(window)
    [panel] = mainwin.findChildren(FrameCombo)
    assert panel_rows(panel) == [['artist'], ['title'], ['album'], ['track', 'year']]


def test_settings_remove_with_the_delete_key(mainwin, user, qtbot):
    window, page = settings_page(user)
    click_row(user, page, 6)
    user.press(Key.Key_Delete)
    # A shortcut presses the button with animateClick: a moment later.
    qtbot.waitUntil(lambda: len(rows(page)) == 6)
    assert [r[1] for r in rows(page)] == ['artist', 'title', 'album', 'track', 'year', 'genre']
    user.close_preferences(window, 'Cancel')


def test_settings_move_up_changes_the_order_on_a_row(mainwin, user):
    # The docs don't say; this is what puddletag does: moving changes the
    # order within a row, never the row.
    window, page = settings_page(user)
    click_row(user, page, 5)
    user.click(page_button(page, 'Move Up'))
    assert rows(page)[4:6] == [['&Genre', 'genre', '3'], ['&Year', 'year', '3']]
    user.close_preferences(window)
    [panel] = mainwin.findChildren(FrameCombo)
    assert panel_rows(panel)[3] == ['track', 'genre', 'year']


def test_settings_move_down_changes_the_order_on_a_row(mainwin, user):
    # The docs don't say; this is what puddletag does.
    window, page = settings_page(user)
    click_row(user, page, 3)
    user.click(page_button(page, 'Move Down'))
    user.close_preferences(window)
    [panel] = mainwin.findChildren(FrameCombo)
    assert panel_rows(panel)[3] == ['year', 'track', 'genre']


def test_settings_buttons_greyed_out_without_rows(mainwin, user):
    # The docs don't say; this is what puddletag does.
    window, page = settings_page(user)
    for i in range(7):
        click_row(user, page, 0)
        user.click(page_button(page, 'Remove'))
    assert rows(page) == []
    assert [page_button(page, tip).isEnabled() for tip in ('Edit', 'Duplicate', 'Remove')] == [False] * 3
    assert page_button(page, 'Add').isEnabled()
    user.close_preferences(window, 'Cancel')


@pytest.mark.xfail(strict=True, reason="Preferences' OK empties the Tag Panel while files are selected")
def test_ok_keeps_the_selected_files_in_the_panel(mainwin, user, loaded):
    # The docs don't say; the panel shows the selected files.
    panel, paths = loaded
    before = shown(panel)
    window = user.open_preferences('General')
    user.close_preferences(window)
    [panel] = mainwin.findChildren(FrameCombo)
    assert shown(panel) == before


@pytest.mark.xfail(strict=True, reason="Preferences' OK with a new layout leaves the Tag Panel empty "
                                       "while files are selected")
def test_ok_with_a_new_layout_shows_the_selected_files(mainwin, user, loaded):
    # The docs don't say; the panel shows the selected files.
    panel, paths = loaded
    window, page = settings_page(user)
    click_row(user, page, 0)
    user.click(page_button(page, 'Edit'))
    type_into_editor(user, 'Band')
    user.close_preferences(window)
    [panel] = mainwin.findChildren(FrameCombo)
    assert shown(panel)['artist'] == 'Same'


# Preview Mode: "While in Preview Mode, you can edit fields as normal (via
# the main view window, Tag Panel or Extended Tags view) before committing
# any changes." (tut4.txt) "To remove a field, change the text to <blank>
# and the field'll be removed upon saving." (tut1.txt)

def test_blank_in_preview_mode_removes_the_field(user, loaded, qtbot):
    panel, paths = loaded
    preview(user)
    pick(user, qtbot, panel, 'album', '<blank>')
    assert [dict(audio.preview) for audio in user.table.model().taginfo] == [{'album': ''}] * 3
    user.click_menu('&Write Previews')
    qtbot.waitUntil(lambda: all(in_file(p).get('album') is None for p in paths[:2]))
    assert [in_file(p).get('album') for p in paths] == [None] * 3


@pytest.mark.xfail(strict=True, reason="<keep> in Preview Mode previews the text <keep>")
def test_keep_in_preview_mode_keeps_each_files_value(user, loaded, qtbot):
    # "<keep>, signifying that upon saving that field will remain unchanged
    # for each file" (tut1.txt)
    panel, paths = loaded
    preview(user)
    pick(user, qtbot, panel, 'album', 'A1')
    pick(user, qtbot, panel, 'album', '<keep>')
    assert [audio.get('album') for audio in user.table.model().taginfo] == [['A1']] * 3


@pytest.mark.xfail(strict=True, reason="the Tag Panel raises AttributeError for <keep> typed before "
                                       "any file was selected")
def test_keep_typed_before_any_folder_is_loaded(mainwin, user):
    # The docs don't say; this is what puddletag should do.
    user.activate()
    preview(user)
    edit = mainwin.findChildren(FrameCombo)[0].combos['artist'].lineEdit()
    user.click(edit)
    user.type('<keep>')
    # Leaving the field finishes the edit, which saves. Focus goes to the
    # table: another field would save again when the window closes.
    user.click(user.table.viewport())
    assert edit.text() == '<keep>'


@pytest.mark.xfail(strict=True, reason="each Preview Mode toggle connects the Tag Panel's fields again")
def test_preview_mode_toggled_connects_the_fields_once(user, loaded, qtbot):
    # The docs don't say; one pick is one change.
    panel, paths = loaded
    seen = []
    panel.onetomanypreview.connect(seen.append)
    for i in range(5):
        preview(user)
    pick(user, qtbot, panel, 'album', '<blank>')
    assert seen == [{'album': ''}]


@pytest.fixture
def differing_genres(mainwin, make_audio, tmp_path, qtbot, user):
    """Two MP3s with the genres Aa and Bb, both selected."""
    music = tmp_path / 'genres'
    paths = [make_audio('01.mp3', music, artist='Same', title='T1', genre='Aa'),
             make_audio('02.mp3', music, artist='Same', title='T2', genre='Bb')]
    mainwin.openDir(str(music), False)
    qtbot.waitUntil(lambda: mainwin._table.model().rowCount() == 2)
    user.activate()
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(1, 'title'), Shift)
    assert mainwin._table.selectedRows == [0, 1]
    user.press(Key.Key_B, Alt)
    [panel] = mainwin.findChildren(FrameCombo)
    return panel, paths


@pytest.mark.xfail(strict=True, reason="Save adds <keep> to the genre list when the files' genres differ")
def test_save_with_differing_genres_adds_no_keep(user, differing_genres, qtbot):
    # "A genre you save in the Tag Panel that isn't in the list is added to
    # it" (preferences.txt): <keep> is no genre.
    panel, paths = differing_genres
    assert shown(panel)['genre'] == '<keep>'
    fill(user, panel, 'album', 'X')
    user.press(Key.Key_S, Ctrl)
    saved(qtbot, paths, 'album', ['X'])
    assert '<keep>' not in status['genres']
    assert [in_file(p)['genre'] for p in paths] == [['Aa'], ['Bb']]
