"""Preferences as a user drives it: Edit > Preferences, a page picked in
its list, its options changed, then OK, Cancel, Esc or Enter; the config
files and the main window checked, also after a restart (preferences.txt,
menus.txt, translate.txt, tags.txt). Files and profiles are synthetic."""
import os

import mutagen.id3
import pytest
from PyQt6.QtCore import QFile, QIODevice, QPoint, Qt, QTranslator
from PyQt6.QtWidgets import (QApplication, QCheckBox, QColorDialog, QComboBox, QLabel, QLineEdit, QMenu,
                             QMessageBox, QPushButton, QRadioButton, QStyle, QStyleOptionButton,
                             QStyleOptionViewItem, QToolButton)

from puddlestuff import audioinfo, confirmations, constants, puddlesettings
from puddlestuff.mainwin.tagpanel import FrameCombo
from puddlestuff.mainwin.tagsources import SortOptionEditor
from puddlestuff.puddleobjects import PuddleConfig
from puddlestuff.puddlesettings import SettingsDialog

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier
OK = QMessageBox.StandardButton.Ok


def config_files():
    """Each file puddletag keeps in its config and data folders, by path,
    except the log and the window sizes, which closing any window saves."""
    files = {}
    for top in (constants.CONFIGDIR, constants.SAVEDIR):
        for folder, _, names in os.walk(top):
            for name in names:
                if name not in ('puddletag.log', 'windowsizes'):
                    with open(os.path.join(folder, name), 'rb') as f:
                        files[os.path.join(folder, name)] = f.read()
    return files


def saved(section, key, filename=None):
    """A value in puddletag's config (puddletag.conf, or the named file in
    the config folder); None when it isn't saved."""
    cparser = PuddleConfig(os.path.join(constants.CONFIGDIR, filename)) if filename else PuddleConfig()
    return cparser.get(section, key, None)


def restarted(restart, qtbot, user):
    """Quits puddletag and starts it again; returns the new window and a
    user driving it."""
    win = restart()
    return win, type(user)(qtbot, win)


def load(win, qtbot, folder, count):
    """Loads the folder's files into the File-View; returns its model."""
    win.openDir(str(folder), False)
    qtbot.waitUntil(lambda: win._table.model().rowCount() == count)
    return win._table.model()


def find_box(widget, text):
    [box] = [b for b in widget.findChildren((QCheckBox, QRadioButton)) if b.text() == text]
    return box


def click_box(user, box):
    """Clicks a check box's or radio button's indicator: the box stretches
    across the page, and a click at its center misses its label."""
    option = QStyleOptionButton()
    box.initStyleOption(option)
    element = (QStyle.SubElement.SE_RadioButtonIndicator if isinstance(box, QRadioButton)
               else QStyle.SubElement.SE_CheckBoxIndicator)
    user.click(box, box.style().subElementRect(element, option, box).center())


def button(widget, name):
    """The visible button named name, without its '&': icon-only buttons
    by their tooltip, the others by their text."""
    [found] = [b for b in widget.findChildren((QPushButton, QToolButton))
               if b.isVisible() and name in (b.toolTip(), b.text().replace('&', ''))]
    return found


def buddy(widget, label):
    """The box a label names (its text starts with label)."""
    [found] = [l.buddy() for l in widget.findChildren(QLabel) if l.text().startswith(label)]
    return found


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


def replace_text(user, box, text):
    """Clicks into a text box, selects what's there and types text."""
    user.click(box)
    user.press(Key.Key_A, Ctrl)
    user.type(text)


def type_over(user, text):
    """Types over the open editor's text and presses Enter."""
    QApplication.focusWidget().selectAll()
    user.type(text)
    user.press(Key.Key_Return)


def edit_item(user, view, rect, text):
    """Double-clicks the item at rect in a table or list and types over
    its text."""
    user.double_click(view.viewport(), rect.center())
    type_over(user, text)


def tick(user, listbox, item):
    """Clicks a list item's check box: the style's check indicator rect."""
    option = QStyleOptionViewItem()
    listbox.initViewItemOption(option)
    option.rect = listbox.visualItemRect(item)
    option.features |= QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
    rect = listbox.style().subElementRect(QStyle.SubElement.SE_ItemViewItemCheckIndicator, option, listbox)
    user.click(listbox.viewport(), rect.center())


def edit_cell(user, qtbot, row, field, text):
    """Types text into the File-View's cell and waits until it shows."""
    user.double_click_cell(user.cell(row, field))
    type_over(user, text)
    qtbot.waitUntil(lambda: user.table.model().data(user.cell(row, field)) == text)
    user.press(Key.Key_Escape)  # the next row's cell, which Enter opened


def warnings_shown(dialogs):
    """The texts of the warnings shown so far."""
    return [args[2] for name, args, kwargs in dialogs.calls if name == 'QMessageBox.warning']


def colour_window(qtbot, page):
    qtbot.waitUntil(lambda: any(w.isVisible() for w in page.findChildren(QColorDialog)))
    [window] = [w for w in page.findChildren(QColorDialog) if w.isVisible()]
    return window


def pick_colour(user, qtbot, page, row, html, close='OK'):
    """Double-clicks the Colours page's row, types the colour into the
    colour window's HTML box and clicks its OK or Cancel; returns the
    row's colour while the window was open."""
    listbox = page.listbox
    user.double_click(listbox.viewport(), listbox.visualItemRect(listbox.item(row, 0)).center())
    window = colour_window(qtbot, page)
    user.activate(window)
    [box] = [b for b in window.findChildren(QLineEdit) if b.text().startswith('#')]
    replace_text(user, box, html)
    live = listbox.item(row, 0).background().color().getRgb()[:3]
    user.click(button(window, close))
    qtbot.waitUntil(lambda: not window.isVisible())
    user.activate(page.window())
    return live


# The window

def edit_colours(user, qtbot, page):
    pick_colour(user, qtbot, page, 1, '#010203')


def edit_confirmations(user, qtbot, page):
    click_box(user, find_box(page, 'Confirm when exiting preview mode.'))


def edit_general(user, qtbot, page):
    click_box(user, find_box(page, 'Show &gridlines'))


def edit_genres(user, qtbot, page):
    user.click(button(page, 'Add'))
    user.type('Synthetic Genre')
    user.press(Key.Key_Return)


def edit_mappings(user, qtbot, page):
    table = page._table
    user.click(table.viewport(), table.visualItemRect(table.item(0, 0)).center())
    user.click(button(page, 'Remove'))


def edit_playlist(user, qtbot, page):
    click_box(user, find_box(page, '&Write extended info'))


def edit_plugins(user, qtbot, page):
    [item] = page._listbox.findItems('View All Fields', Qt.MatchFlag.MatchExactly)
    tick(user, page._listbox, item)


def edit_tag_panel(user, qtbot, page):
    table = page._table
    edit_item(user, table, table.visualItemRect(table.item(0, 2)), '7')


def edit_tags(user, qtbot, page):
    click_box(user, find_box(page, 'Write ID3v2.&3'))


PAGE_EDITS = {'Colours': edit_colours, 'Confirmations': edit_confirmations, 'General': edit_general,
              'Genres': edit_genres, 'Mappings': edit_mappings, 'Playlist': edit_playlist,
              'Plugins': edit_plugins, 'Tag Panel': edit_tag_panel, 'Tags': edit_tags}


class SyntheticTranslation(QTranslator):
    def translate(self, context, source, disambiguation=None, n=-1):
        return 'Synthetic Settings Title' if (context, source) == ('Settings', 'puddletag settings') else None


def fail_tag_panel(user, window):
    """Types x into the Tag Panel page's first Row cell, which OK refuses."""
    table = window.stack.currentWidget()._table
    edit_item(user, table, table.visualItemRect(table.item(0, 2)), 'x')


@pytest.fixture(autouse=True)
def pinned_id3_options(monkeypatch):
    """Pages OK'd here set the ID3 options at once; the test puts them back."""
    monkeypatch.setattr(audioinfo.id3, 'v1_option', audioinfo.id3.v1_option)
    monkeypatch.setattr(audioinfo.id3, 'v2_option', audioinfo.id3.v2_option)


@pytest.fixture(autouse=True)
def restored_confirmations(monkeypatch):
    """OK on the Confirmations page changes a module-level dict that
    outlives the test's profile; the test puts it back."""
    monkeypatch.setattr(confirmations, '_confirmations',
                        {name: list(entry) for name, entry in confirmations._confirmations.items()})


@pytest.mark.parametrize('page', sorted(PAGE_EDITS))
def test_cancel_on_a_page_leaves_the_config_as_it_was(mainwin, qtbot, user, page):
    # preferences.txt: "**Cancel** or **Esc** closes the window without
    # saving anything", whatever page was edited (synthetic edits).
    from puddlestuff.puddletag import status
    before = config_files()
    genres = list(status['genres'])
    window = user.open_preferences(page)
    PAGE_EDITS[page](user, qtbot, window.stack.currentWidget())
    user.close_preferences(window, 'Cancel')
    assert config_files() == before
    assert status['genres'] == genres
    assert mainwin._table.showGrid() is True


def test_ok_with_nothing_changed_keeps_every_value(mainwin, qtbot, user):
    # Docs silent (synthetic): OK on a window nobody edited changes no value.
    for page in PAGE_EDITS:
        window = user.open_preferences(page)
        PAGE_EDITS[page](user, qtbot, window.stack.currentWidget())
        user.close_preferences(window)
    before = config_files()
    window = user.open_preferences()
    user.close_preferences(window)
    assert config_files() == before


def test_switching_pages_keeps_earlier_edits(mainwin, qtbot, user):
    # Docs silent (synthetic): an edit on one page survives a visit to another.
    window = user.open_preferences()
    general = window.stack.currentWidget()
    edit_general(user, qtbot, general)
    for page in ('Tags', 'General'):
        [row] = [r for r, (title, *_) in window._widgets.items() if title == page]
        index = window.model.index(row, 0)
        user.click(window.listbox.viewport(), window.listbox.visualRect(index).center())
        qtbot.waitUntil(lambda: window.stack.currentWidget() is window._widgets[row][1])
        if page == 'Tags':
            edit_tags(user, qtbot, window.stack.currentWidget())
    assert not find_box(general, 'Show &gridlines').isChecked()
    user.close_preferences(window)
    assert saved('Show &gridlines', 'value', 'gensettings') is False
    assert saved('id3tags', 'v2_option') == 3
    assert mainwin._table.showGrid() is False


def test_page_that_fails_names_itself_and_stays_open(mainwin, qtbot, user, dialogs):
    # preferences.txt: "If the values on a page can't be saved (for instance
    # a row in the Tag Panel that isn't a number), a warning names the page,
    # the window stays open".
    window = user.open_preferences('Tag Panel')
    fail_tag_panel(user, window)
    dialogs.answer('QMessageBox.warning', OK)
    user.click(window.okbuttons.okButton)
    qtbot.waitUntil(lambda: bool(warnings_shown(dialogs)))
    assert '<b>Tag Panel</b>' in warnings_shown(dialogs)[0]
    assert window.isVisible()
    user.close_preferences(window, 'Cancel')


def test_cancel_after_a_page_fails_saves_nothing(mainwin, qtbot, user, dialogs):
    # preferences.txt: "a warning names the page, the window stays open and
    # nothing is saved." Cancel then leaves the config as it was.
    before = config_files()
    window = user.open_preferences()
    edit_general(user, qtbot, window.stack.currentWidget())
    [row] = [r for r, (title, *_) in window._widgets.items() if title == 'Tag Panel']
    index = window.model.index(row, 0)
    user.click(window.listbox.viewport(), window.listbox.visualRect(index).center())
    qtbot.waitUntil(lambda: window.stack.currentWidget() is window._widgets[row][1])
    fail_tag_panel(user, window)
    dialogs.answer('QMessageBox.warning', OK)
    user.click(window.okbuttons.okButton)
    qtbot.waitUntil(lambda: bool(warnings_shown(dialogs)))
    user.close_preferences(window, 'Cancel')
    assert config_files() == before
    assert mainwin._table.showGrid() is True


def test_esc_closes_without_saving(mainwin, qtbot, user):
    # preferences.txt: "**Cancel** or **Esc** closes the window without
    # saving anything".
    before = config_files()
    window = user.open_preferences()
    edit_general(user, qtbot, window.stack.currentWidget())
    user.press(Key.Key_Escape)
    qtbot.waitUntil(lambda: not window.isVisible())
    user.activate()
    assert config_files() == before
    assert mainwin._table.showGrid() is True


def test_esc_remembers_the_window_size(mainwin, qtbot, user, restart):
    # Docs silent (synthetic): Esc saves the window's size, as OK and Cancel do.
    window = user.open_preferences()
    # The offscreen screen is 800 pixels wide, and a window is restored within it.
    window.resize(750, 500)
    qtbot.waitUntil(lambda: window.size().width() == 750)
    user.press(Key.Key_Escape)
    qtbot.waitUntil(lambda: not window.isVisible())
    win, user = restarted(restart, qtbot, user)
    window = user.open_preferences()
    assert (window.width(), window.height()) == (750, 500)


def test_enter_clicks_ok(mainwin, qtbot, user):
    # preferences.txt: "**Enter** clicks **OK**".
    window = user.open_preferences()
    edit_general(user, qtbot, window.stack.currentWidget())
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=1000)
    assert saved('Show &gridlines', 'value', 'gensettings') is False
    assert mainwin._table.showGrid() is False
    assert not [w for w in window.findChildren(SortOptionEditor) if w.isVisible()]


def test_preferences_opened_twice_is_one_window(mainwin, qtbot, user):
    # menus.txt (Edit): "Preferences ... Opens the Preferences dialog."
    window = user.open_preferences()
    user.activate()
    user.click_menu('&Preferences')
    qtbot.waitUntil(window.isActiveWindow)
    assert [w for w in mainwin.findChildren(SettingsDialog) if w.isVisible()] == [window]


def test_window_title_is_translated(mainwin, qtbot, user):
    # translate.txt: puddletag's texts can be translated. The translation is
    # synthetic.
    translator = SyntheticTranslation()
    QApplication.installTranslator(translator)
    try:
        window = user.open_preferences()
        title = window.windowTitle()
        user.close_preferences(window, 'Cancel')
    finally:
        QApplication.removeTranslator(translator)
    assert title == 'Synthetic Settings Title'


# General: language, sort options, sort order after a restart

def language_combo(window):
    [combo] = window.stack.currentWidget().findChildren(QComboBox)
    return combo


def sort_by_menu(mainwin):
    [menu] = [m for m in mainwin.findChildren(QMenu) if m.title() == 'Sort &By']
    return menu


def sort_by(mainwin, qtbot, user, option):
    """Tools > Sort By > option."""
    sort_menu = sort_by_menu(mainwin)
    [action] = [a for a in sort_menu.actions() if a.text() == option]
    bar = mainwin.menuBar()
    [tools] = [m for m in bar.findChildren(QMenu) if m.title() == '&Tools']
    # The pointer stays where the last test left it (see user.right_click).
    qtbot.mouseMove(mainwin.windowHandle(), QPoint(5, 5))
    user.click(bar, bar.actionGeometry(tools.menuAction()).center())
    qtbot.waitUntil(tools.isVisible)
    user.click(tools, tools.actionGeometry(sort_menu.menuAction()).center())
    qtbot.waitUntil(sort_menu.isVisible)
    user.click(sort_menu, sort_menu.actionGeometry(action).center())
    qtbot.waitUntil(lambda: not tools.isVisible())
    user.activate()


def add_sort_option(window, qtbot, user, dialogs, text):
    """Edit sort options > Add > text > OK; the Preferences window gets the
    activation back."""
    user.click(button(window.stack.currentWidget(), 'Edit sort options'))
    qtbot.waitUntil(lambda: any(w.isVisible() for w in window.findChildren(SortOptionEditor)))
    [editor] = [w for w in window.findChildren(SortOptionEditor) if w.isVisible()]
    user.activate(editor)
    dialogs.answer('QInputDialog.getItem', (text, True))
    user.click(button(editor, 'Add'))
    qtbot.waitUntil(lambda: editor.listbox.count() == 4)
    user.click(button(editor, 'OK'))
    qtbot.waitUntil(lambda: not editor.isVisible())
    user.activate(window)


@pytest.mark.parametrize('shown, saved_value', [('de', 'de'), ('Default', 'default'), ('<Autodetect>', 'auto')],
                         ids=['picked', 'default', 'autodetect'])
def test_language_is_saved_and_shown_again(mainwin, qtbot, user, restart, shown, saved_value):
    # translate.txt:38: "you'll have the option to switch to the language in **Edit->Preferences**"
    window = user.open_preferences()
    pick(user, qtbot, language_combo(window), 'fr')
    user.close_preferences(window)
    window = user.open_preferences()
    pick(user, qtbot, language_combo(window), shown)
    user.close_preferences(window)

    assert saved('main', 'lang') == saved_value
    win, user = restarted(restart, qtbot, user)
    window = user.open_preferences()
    assert language_combo(window).currentText() == shown


def test_translation_in_the_data_folder_is_offered_after_a_restart(mainwin, qtbot, user, restart):
    # translate.txt:38: "Copy the .qm to ~/.local/share/puddletag/translations ... Next time you start
    # puddletag you'll have the option to switch to the language in Edit->Preferences". Synthetic: the
    # shipped German file copied as puddletag_xx.qm.
    source = QFile('translations:puddletag_de.qm')
    assert source.open(QIODevice.OpenModeFlag.ReadOnly)
    os.makedirs(constants.TRANSDIR, exist_ok=True)
    with open(os.path.join(constants.TRANSDIR, 'puddletag_xx.qm'), 'wb') as f:
        f.write(bytes(source.readAll()))

    win, user = restarted(restart, qtbot, user)
    window = user.open_preferences()

    combo = language_combo(window)
    assert 'xx' in [combo.itemText(row) for row in range(combo.count())]


def test_edit_sort_options_adds_a_sort_by_item(mainwin, qtbot, user, dialogs):
    # preferences.txt:43: "Any field-lists you add will create a menu item in the **Tools->Sort By** menu."
    window = user.open_preferences()
    add_sort_option(window, qtbot, user, dialogs, 'artist, title')
    user.close_preferences(window)

    assert 'artist/title' in [a.text() for a in sort_by_menu(mainwin).actions()]
    assert saved('table', 'sortoptions') == ['__filename,track,__dirpath', 'track, album',
                                             '__filename,album,__dirpath', 'artist, title']


@pytest.mark.xfail(strict=True, reason='Edit sort options saves at its own OK, before Preferences is OK\'d '
                                       'or cancelled')
def test_edit_sort_options_then_cancel_changes_nothing(mainwin, qtbot, user, dialogs):
    # preferences.txt, Edit sort options: "The list you edit here is saved when you click **OK** in
    # Preferences, like every other page."
    before = config_files()
    window = user.open_preferences()
    add_sort_option(window, qtbot, user, dialogs, 'artist, title')
    user.close_preferences(window, 'Cancel')

    assert 'artist/title' not in [a.text() for a in sort_by_menu(mainwin).actions()]
    assert config_files() == before


@pytest.mark.xfail(strict=True, reason='the sort order picked is not used after a restart (#243, #558)')
def test_sort_picked_is_used_after_a_restart(mainwin, make_audio, tmp_path, qtbot, user, restart):
    # preferences.txt:49: "This sort order will be used when loading dirs unless changed (by clicking a
    # header or using another Sort Option.) It is saved across sessions." Synthetic files.
    make_audio('a.mp3', tmp_path / 'first', title='A')
    make_audio('c.mp3', tmp_path / 'second', album='Same', tracknumber='2')
    make_audio('d.mp3', tmp_path / 'second', album='Same', tracknumber='1')
    load(mainwin, qtbot, tmp_path / 'first', 1)
    sort_by(mainwin, qtbot, user, 'track/album')

    win, user = restarted(restart, qtbot, user)
    model = load(win, qtbot, tmp_path / 'second', 2)

    assert [os.path.basename(a.filepath) for a in model.taginfo] == ['d.mp3', 'c.mp3']


# Mappings

def mapping_rows(page):
    table = page._table
    return [tuple(table.item(r, c).text() for c in range(3)) for r in range(table.rowCount())]


def click_mapping(user, page, row, column):
    table = page._table
    user.click(table.viewport(), table.visualItemRect(table.item(row, column)).center())


def add_mapping(user, page, tag, original, target):
    """Clicks "+" and types the row over its placeholders: Tab moves to
    the next cell's editor, Enter ends."""
    user.click(button(page, 'Add'))
    for text, key in ((tag, Key.Key_Tab), (original, Key.Key_Tab), (target, Key.Key_Return)):
        QApplication.focusWidget().selectAll()
        user.type(text)
        user.press(key)


def mappings_file():
    return os.path.join(constants.CONFIGDIR, 'mappings')


def test_mapping_renames_the_field_after_a_restart(mainwin, user, qtbot, restart, make_audio, tmp_path):
    # preferences.txt: "if you want the performer to be shown as albumartist
    # for ID3 files. You'd set up a mapping with ID3 as the Tag, performer as
    # the Original Field and albumartist as the Target. Now any files that
    # contained the performer field before the mapping will instead show it
    # as albumartist." The file is synthetic.
    path = make_audio('01.mp3', tmp_path / 'music', title='One')
    tag = mutagen.id3.ID3(path)
    tag.add(mutagen.id3.TXXX(encoding=3, desc='performer', text=['Synthetic Performer']))
    tag.save()
    window = user.open_preferences('Mappings')
    page = window.stack.currentWidget()
    add_mapping(user, page, 'ID3', 'performer', 'albumartist')
    user.close_preferences(window)

    win, user = restarted(restart, qtbot, user)
    model = load(win, qtbot, tmp_path / 'music', 1)

    assert model.taginfo[0]['albumartist'] == ['Synthetic Performer']
    # `in` follows the mapping, so 'performer' would be found as albumartist
    assert 'performer' not in list(model.taginfo[0])
    assert mutagen.id3.ID3(path).getall('TXXX:performer')[0].text == ['Synthetic Performer']
    assert not mutagen.id3.ID3(path).getall('TPE2')


def test_edited_mapping_renames_the_field_after_a_restart(mainwin, user, qtbot, restart, make_audio, tmp_path):
    # tags.txt: "VorbisComment: tracknumber shows as track, and date as
    # year." preferences.txt: the Mappings table's cells can be edited.
    make_audio('01.flac', tmp_path / 'music', date='2001')
    window = user.open_preferences('Mappings')
    page = window.stack.currentWidget()
    row = mapping_rows(page).index(('VorbisComment', 'date', 'year'))
    click_mapping(user, page, row, 2)
    user.click(button(page, 'Edit'))
    type_over(user, 'released')
    user.close_preferences(window)

    win, user = restarted(restart, qtbot, user)
    model = load(win, qtbot, tmp_path / 'music', 1)

    assert model.taginfo[0]['released'] == ['2001']
    assert 'year' not in model.taginfo[0]


def test_removed_mapping_shows_the_files_own_field(mainwin, user, qtbot, restart, make_audio, tmp_path):
    # tags.txt: "VorbisComment: tracknumber shows as track, and date as
    # year." preferences.txt: "The mapping doesn't work in reverse".
    make_audio('01.flac', tmp_path / 'music', date='2001')
    window = user.open_preferences('Mappings')
    page = window.stack.currentWidget()
    row = mapping_rows(page).index(('VorbisComment', 'date', 'year'))
    click_mapping(user, page, row, 0)
    user.click(button(page, 'Remove'))
    user.close_preferences(window)

    win, user = restarted(restart, qtbot, user)
    model = load(win, qtbot, tmp_path / 'music', 1)

    assert model.taginfo[0]['date'] == ['2001']
    assert 'year' not in model.taginfo[0]


def test_duplicated_mapping_is_saved_with_its_edit(mainwin, user, qtbot, restart):
    # preferences.txt: the Mappings table has a Duplicate button, whose copy
    # is edited like any row.
    window = user.open_preferences('Mappings')
    page = window.stack.currentWidget()
    row = mapping_rows(page).index(('VorbisComment', 'date', 'year'))
    click_mapping(user, page, row, 0)
    user.click(button(page, 'Duplicate'))
    type_over(user, 'APEv2')
    user.close_preferences(window)

    win, user = restarted(restart, qtbot, user)
    window = user.open_preferences('Mappings')
    rows = mapping_rows(window.stack.currentWidget())

    assert ('VorbisComment', 'date', 'year') in rows
    assert ('APEv2', 'date', 'year') in rows
    with open(mappings_file()) as f:
        lines = f.read().split('\n')
    assert 'VorbisComment,date,year' in lines
    assert 'APEv2,date,year' in lines


def test_old_musicbrainz_album_id_mapping_still_applies(mainwin, qtbot, restart, make_audio, tmp_path):
    # tags.txt: "mbrainz_album_id TXXX:MusicBrainz Album Id". The profile is
    # synthetic: it holds the spelling older versions saved.
    path = make_audio('01.mp3', tmp_path / 'music', title='One')
    tag = mutagen.id3.ID3(path)
    tag.add(mutagen.id3.TXXX(encoding=3, desc='MusicBrainz Album Id', text=['synthetic-album-id']))
    tag.save()
    with open(mappings_file(), 'w') as f:
        f.write('ID3,MusicBrainz Album ID,mbrainz_album_id\n')

    win = restart()
    model = load(win, qtbot, tmp_path / 'music', 1)

    assert model.taginfo[0]['mbrainz_album_id'] == ['synthetic-album-id']


@pytest.mark.xfail(strict=True, reason='a comma in a mapping is saved and the row is dropped at the next start')
def test_mapping_with_a_comma_is_refused(mainwin, user, qtbot, dialogs):
    # preferences.txt: "A field can't contain a comma: **OK** refuses it with
    # a warning." The warning names the page.
    window = user.open_preferences('Mappings')
    page = window.stack.currentWidget()
    before = config_files()
    add_mapping(user, page, 'ID3', 'performer', 'album,artist')
    dialogs.answer('QMessageBox.warning', OK)
    user.click(window.okbuttons.okButton)
    qtbot.waitUntil(lambda: bool(warnings_shown(dialogs)))

    assert '<b>Mappings</b>' in warnings_shown(dialogs)[0]
    assert window.isVisible()
    assert config_files().get(mappings_file()) == before.get(mappings_file())
    user.close_preferences(window, 'Cancel')


@pytest.mark.xfail(strict=True, reason='Add then OK saves the placeholder row Tag,Source,Target')
def test_new_row_left_as_it_is_is_not_saved(mainwin, user, qtbot, restart):
    # Synthetic: a row added and left as its placeholders (Tag, Source,
    # Target) says nothing, so OK doesn't save it.
    window = user.open_preferences('Mappings')
    page = window.stack.currentWidget()
    user.click(button(page, 'Add'))
    user.press(Key.Key_Escape)  # closes the editor; the row keeps its placeholders
    assert window.isVisible()
    user.close_preferences(window)

    win, user = restarted(restart, qtbot, user)
    window = user.open_preferences('Mappings')

    assert ('Tag', 'Source', 'Target') not in mapping_rows(window.stack.currentWidget())
    if os.path.exists(mappings_file()):
        with open(mappings_file()) as f:
            assert 'Tag,Source,Target' not in f.read()


@pytest.mark.xfail(strict=True,
                   reason='any OK writes mappings, so later changes to the built-in mappings never reach the user')
def test_ok_without_changes_writes_no_mappings_file(mainwin, user, qtbot, restart):
    # preferences.txt: "The mappings are saved to the **mappings** file ...
    # only when they differ from the built-in ones. When they're the same
    # again, the file is removed".
    window = user.open_preferences('Mappings')
    defaults = mapping_rows(window.stack.currentWidget())
    user.close_preferences(window)

    assert not os.path.exists(mappings_file())

    with open(mappings_file(), 'w') as f:
        f.write('\n'.join(','.join(row) for row in defaults))
    win, user = restarted(restart, qtbot, user)
    window = user.open_preferences('Mappings')
    user.close_preferences(window)

    assert not os.path.exists(mappings_file())


@pytest.mark.xfail(strict=True, reason='a mappings row whose Tag is puddletag hides other rows with its field')
def test_puddletag_row_hides_no_other_row(mainwin, user, qtbot, restart):
    # Synthetic: a mappings file with a row whose Tag is puddletag next to
    # a row with the same Original field; the page shows every row.
    with open(mappings_file(), 'w') as f:
        f.write('ID3,artist,singer\npuddletag,artist,performer\n')

    win, user = restarted(restart, qtbot, user)
    window = user.open_preferences('Mappings')

    assert sorted(mapping_rows(window.stack.currentWidget())) == [
        ('ID3', 'artist', 'singer'), ('puddletag', 'artist', 'performer')]


# Genres: "The list of genres as used in the Tag Panel." and "Edit to your
# hearts content." (preferences.txt). The genre name is synthetic.

def genres_page(user):
    """Opens the Genres page; returns the window, the page and a function
    listing the genres the list shows."""
    window = user.open_preferences('Genres')
    page = window.stack.currentWidget()
    return window, page, lambda: [page.listbox.item(i).text() for i in range(page.listbox.count())]


def click_genre(user, page, row):
    user.click(page.listbox.viewport(), page.listbox.visualItemRect(page.listbox.item(row)).center())


def test_new_genre_reaches_the_tag_panel_and_the_genres_file(mainwin, make_audio, tmp_path, qtbot, user, restart):
    # preferences.txt: "The list is saved to **~/.config/puddletag/genres**
    # when puddletag quits. A new genre shows in the Tag Panel's list from the
    # next file you select."
    music = tmp_path / 'music'
    make_audio('01.mp3', music, title='One')
    make_audio('02.mp3', music, title='Two')
    load(mainwin, qtbot, music, 2)
    user.click_cell(user.cell(0, 'title'))
    window, page, texts = genres_page(user)
    user.click(button(page, 'Add'))
    user.type('Synthetic Genre')
    user.press(Key.Key_Return)
    user.close_preferences(window)
    user.click_cell(user.cell(1, 'title'))
    [panel] = mainwin.findChildren(FrameCombo)
    combo = panel.combos['genre']
    assert 'Synthetic Genre' in [combo.itemText(i) for i in range(combo.count())]
    restart()
    with open(os.path.join(constants.CONFIGDIR, 'genres')) as f:
        assert f.read().splitlines()[-1] == 'Synthetic Genre'


@pytest.mark.xfail(strict=True, reason='#470: a new genre moved while still being typed loses its name')
def test_new_genre_moved_while_typed_keeps_its_name(mainwin, user):
    # #470: a new genre moved up before Enter lost its name.
    from puddlestuff.puddletag import status
    window, page, texts = genres_page(user)
    user.click(button(page, 'Add'))
    user.type('Synthetic Genre')
    user.click(button(page, 'Move Up'))
    assert texts()[-3:] == ['Vocal', 'Synthetic Genre', 'World Music']
    user.close_preferences(window)
    assert status['genres'][-2] == 'Synthetic Genre'


def test_edited_genre_is_renamed(mainwin, user):
    from puddlestuff.puddletag import status
    window, page, texts = genres_page(user)
    first = texts()[0]
    click_genre(user, page, 0)
    user.click(button(page, 'Edit'))
    type_over(user, 'Synthetic Genre')
    user.close_preferences(window)
    assert status['genres'][0] == 'Synthetic Genre'
    assert first not in status['genres']


def test_removed_genre_is_gone(mainwin, user):
    from puddlestuff.puddletag import status
    window, page, texts = genres_page(user)
    before = len(texts())
    last = texts()[-1]
    click_genre(user, page, before - 1)
    user.click(button(page, 'Remove'))
    user.close_preferences(window)
    assert last not in status['genres']
    assert len(status['genres']) == before - 1


def test_three_genres_moved_down_together(mainwin, user):
    from puddlestuff.puddletag import status
    window, page, texts = genres_page(user)
    g = texts()[:4]
    click_genre(user, page, 0)
    viewport = page.listbox.viewport()
    user.click(viewport, page.listbox.visualItemRect(page.listbox.item(2)).center(), Shift)
    user.click(button(page, 'Move Down'))
    user.close_preferences(window)
    assert status['genres'][:4] == [g[3], g[0], g[1], g[2]]


# Tags, Colours, Plugins and Confirmations

def one_song(make_audio, tmp_path):
    return make_audio('01.mp3', tmp_path / 'music', title='One')


def test_write_id3v2_3_writes_v2_3(mainwin, user, qtbot, make_audio, tmp_path):
    # preferences.txt: "puddletag supports writing ID3v2.4 (text as UTF-8)
    # and ID3v2.3 (text as UTF-16, as it has no UTF-8)".
    path = str(one_song(make_audio, tmp_path))
    load(mainwin, qtbot, tmp_path / 'music', 1)
    window = user.open_preferences('Tags')
    click_box(user, find_box(window.stack.currentWidget(), 'Write ID3v2.&3'))
    user.close_preferences(window)

    edit_cell(user, qtbot, 0, 'title', 'Two')
    qtbot.waitUntil(lambda: mutagen.id3.ID3(path).getall('TIT2')[0].text == ['Two'])

    tag = mutagen.id3.ID3(path)
    assert tag.version == (2, 3, 0)
    assert tag.getall('TIT2')[0].encoding == 1
    window = user.open_preferences('Tags')
    assert find_box(window.stack.currentWidget(), 'Write ID3v2.&3').isChecked()
    user.close_preferences(window, 'Cancel')


@pytest.mark.parametrize('choice, had_v1, title', [
    ("Remove ID3v1 tag.", True, None),
    ("Update the ID3v1 tag's values only if an ID3v1 tag is present.", False, None),
    ("Update the ID3v1 tag's values only if an ID3v1 tag is present.", True, b'Two'),
    ("Create an ID3v1 tag if it's not present. Otherwise update it.", False, b'Two'),
])
def test_id3v1_choice(choice, had_v1, title, mainwin, user, qtbot, make_audio, tmp_path):
    # preferences.txt: "puddletag writes only ID3v2 tags. For the ID3v1 tag,
    # choose what saving does", each choice as the window words it. The
    # ID3v1 tag of had_v1 is synthetic.
    path = str(one_song(make_audio, tmp_path))
    if had_v1:
        mutagen.id3.ID3(path).save(v1=2)
    load(mainwin, qtbot, tmp_path / 'music', 1)
    window = user.open_preferences('Tags')
    page = window.stack.currentWidget()
    pick(user, qtbot, buddy(page, 'puddletag writes only &ID3v2 tags'), choice)
    index = buddy(page, 'puddletag writes only &ID3v2 tags').currentIndex()
    user.close_preferences(window)

    edit_cell(user, qtbot, 0, 'title', 'Two')
    qtbot.waitUntil(lambda: mutagen.id3.ID3(path).getall('TIT2')[0].text == ['Two'])

    with open(path, 'rb') as f:
        tail = f.read()[-128:]
    v1_title = tail[3:33].rstrip(b'\x00 ') if tail[:3] == b'TAG' else None
    assert v1_title == title
    assert saved('id3tags', 'v1_option') == index


def test_restrict_incoming_files_loads_only_matching_files(mainwin, user, qtbot, make_audio, tmp_path, restart):
    # preferences.txt: '"*.mp3; *.ogg; *.aac" will only load filenames ...
    # ending with ...'.
    make_audio('01.mp3', tmp_path / 'music')
    make_audio('02.flac', tmp_path / 'music')
    window = user.open_preferences('Tags')
    replace_text(user, buddy(window.stack.currentWidget(), '&Restrict incoming files'), '*.mp3')
    user.close_preferences(window)

    model = load(mainwin, qtbot, tmp_path / 'music', 1)
    qtbot.wait(200)

    assert [os.path.basename(audio.filepath) for audio in model.taginfo] == ['01.mp3']
    assert saved('table', 'filespec') == ['*.mp3']
    win, _ = restarted(restart, qtbot, user)
    model = load(win, qtbot, tmp_path / 'music', 1)
    qtbot.wait(200)
    assert [os.path.basename(audio.filepath) for audio in model.taginfo] == ['01.mp3']


def test_artwork_pattern_is_kept_after_a_restart(mainwin, user, qtbot, restart):
    # preferences.txt: "Default pattern to use when saving artwork: The
    # pattern used for the name of an image file when you save artwork."
    from puddlestuff.puddletag import status
    window = user.open_preferences('Tags')
    replace_text(user, buddy(window.stack.currentWidget(), 'Default &pattern to use when saving artwork'),
                 'cover')
    user.close_preferences(window)

    assert status['cover_pattern'] == 'cover'
    assert saved('tags', 'cover_pattern') == 'cover'
    win, new_user = restarted(restart, qtbot, user)
    window = new_user.open_preferences('Tags')
    assert buddy(window.stack.currentWidget(), 'Default &pattern to use when saving artwork').text() == 'cover'
    assert status['cover_pattern'] == 'cover'
    new_user.close_preferences(window, 'Cancel')


def test_picked_colour_reaches_the_table(mainwin, user, qtbot, make_audio, tmp_path):
    # preferences.txt: "Defines the background colours to used in various
    # puddletag dialogs."
    one_song(make_audio, tmp_path)
    load(mainwin, qtbot, tmp_path / 'music', 1)
    window = user.open_preferences('Colours')
    live = pick_colour(user, qtbot, window.stack.currentWidget(), 1, '#010203')
    user.close_preferences(window)

    user.press(Key.Key_P, Ctrl | Shift)
    edit_cell(user, qtbot, 0, 'title', 'Two')
    # A selected row shows the selection colour instead.
    user.click_cell(user.cell(0, 'title'), Ctrl)
    qtbot.waitUntil(lambda: not user.table.selectedIndexes())

    assert live == (1, 2, 3)
    assert saved('table', 'preview_color') == [1, 2, 3]
    background = user.table.model().data(user.cell(0, 'title'), Qt.ItemDataRole.BackgroundRole)
    assert background.getRgb()[:3] == (1, 2, 3)


def test_colour_window_cancel_reverts_the_colour(mainwin, user, qtbot):
    # preferences.txt: "Defines the background colours to used in various
    # puddletag dialogs." The colour window's Cancel leaves the colour as it was.
    window = user.open_preferences('Colours')
    page = window.stack.currentWidget()
    live = pick_colour(user, qtbot, page, 1, '#010203', 'Cancel')

    assert live == (1, 2, 3)
    assert page.listbox.item(1, 0).background().color().getRgb()[:3] == (192, 255, 192)
    user.close_preferences(window)
    assert saved('table', 'preview_color') == [192, 255, 192]


def test_picked_colours_survive_a_restart(mainwin, user, qtbot, restart):
    # preferences.txt: "Defines the background colours to used in various
    # puddletag dialogs."
    window = user.open_preferences('Colours')
    page = window.stack.currentWidget()
    pick_colour(user, qtbot, page, 1, '#010203')
    pick_colour(user, qtbot, page, 2, '#040506')
    user.close_preferences(window)

    win, new_user = restarted(restart, qtbot, user)
    window = new_user.open_preferences('Colours')
    page = window.stack.currentWidget()
    assert page.listbox.item(1, 0).background().color().getRgb()[:3] == (1, 2, 3)
    assert page.listbox.item(2, 0).background().color().getRgb()[:3] == (4, 5, 6)
    assert win._table.model().previewBackground.getRgb()[:3] == (1, 2, 3)
    assert saved('extendedtags', 'add') == [4, 5, 6]
    new_user.close_preferences(window, 'Cancel')


def test_enabled_plugin_adds_its_page(mainwin, user, qtbot, restart, monkeypatch):
    # preferences.txt: "Enable it, then restart." The plugin adds its page
    # class to a module list that would outlive the test.
    monkeypatch.setattr(puddlesettings, 'config_widgets', [])
    window = user.open_preferences('Plugins')
    page = window.stack.currentWidget()
    [item] = page._listbox.findItems('View All Fields', Qt.MatchFlag.MatchExactly)
    tick(user, page._listbox, item)
    user.close_preferences(window)

    win, new_user = restarted(restart, qtbot, user)
    window = new_user.open_preferences('View All Fields')

    assert 'View All Fields' in [title for title, *_ in window._widgets.values()]
    new_user.close_preferences(window, 'Cancel')


@pytest.mark.xfail(strict=True, reason='a saved confirmation keeps the wording it was saved with')
def test_confirmation_shows_the_programs_wording(mainwin, user, qtbot, restart, monkeypatch):
    # preferences.txt: "Confirmations let you know that you're about to do
    # something that can't be reversed." The program's wording is shown, not
    # the one an earlier profile saved (synthetic).
    monkeypatch.setitem(confirmations._confirmations, 'trash_files',
                        list(confirmations._confirmations['trash_files']))
    cparser = PuddleConfig(os.path.join(constants.CONFIGDIR, 'confirmations'))
    cparser.set('Config0', 'name', 'trash_files')
    cparser.set('Config0', 'value', True)
    cparser.set('Config0', 'description', 'Synthetic old wording')

    win, new_user = restarted(restart, qtbot, user)
    window = new_user.open_preferences('Confirmations')

    texts = [box.text() for box in window.stack.currentWidget().findChildren(QCheckBox)]
    assert 'Confirm when moving files to the trash.' in texts
    assert 'Synthetic old wording' not in texts
    new_user.close_preferences(window, 'Cancel')
