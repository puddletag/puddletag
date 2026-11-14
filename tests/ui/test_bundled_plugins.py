"""The plugins that come with puddletag, used as a user uses them: ticked
on the Plugins page of Edit->Preferences, then their commands run from the
Plugins and Tag Tools menus, and the File-View and the files checked.
plugins.txt: "To use a plugin, tick it on the Plugins page of
Edit->Preferences, then restart puddletag." No page of the docs describes
the bundled plugins: each test quotes the plugin's own description (its
info file) and says where the docs are silent. Synthetic files.
"""
import os
import pickle
import sys

import mutagen.id3
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

from puddlestuff import audioinfo
from puddlestuff.constants import SAVEDIR
from puddlestuff.puddleobjects import ListButtons, PuddleConfig
from test_plugins import click_check_box, listed_plugins, startup_errors
from test_preferences import tick as tick_list_item

pytestmark = pytest.mark.ui

Ok = QMessageBox.StandardButton.Ok
Shift = Qt.KeyboardModifier.ShiftModifier

PREVIEW_REFUSAL = 'You need to disable preview mode first.'


def forget(monkeypatch, *modules):
    """Python keeps a module it imported, with what an earlier test's
    window left in it: the test starts as a new puddletag process does,
    with these bundled plugins not imported yet."""
    for module in modules:
        monkeypatch.delitem(sys.modules, f'puddlestuff.plugins.{module}', raising=False)


def tick(monkeypatch, *modules):
    """The profile as ticking these plugins on the Plugins page in an
    earlier session leaves it: their folders' names in plugins.to_load."""
    forget(monkeypatch, *modules)
    PuddleConfig().set('plugins', 'to_load', list(modules))


def load(mainwin, user, qtbot, folder, count):
    """Opens the folder and selects its count files, as a user does."""
    mainwin.openDir(str(folder), False)
    qtbot.waitUntil(lambda: mainwin._table.model().rowCount() == count)
    user.activate()
    user.click_cell(user.cell(0, 'title'))
    if count > 1:
        user.click_cell(user.cell(count - 1, 'title'), Shift)


def menu(window, title):
    """The commands in the window's menu-bar menu with this title; none
    when the menu bar has no such menu."""
    menus = {action.text(): action.menu() for action in window.menuBar().actions() if action.menu()}
    if title not in menus:
        return []
    return [action.text() for action in menus[title].actions() if not action.isSeparator()]


def calls(dialogs, name):
    return [args for call, args, kwargs in dialogs.calls if call == name]


def headers(mainwin):
    """The File-View's columns' fields, in order."""
    return [field for title, field in mainwin._table.model().headerdata]


def highlighted(mainwin):
    """Per row, whether the File-View shows it highlighted."""
    model = mainwin._table.model()
    return [model.data(model.index(row, 0), Qt.ItemDataRole.BackgroundRole) == model.permaColor
            for row in range(model.rowCount())]


def in_file(path):
    return audioinfo.usertags(audioinfo.Tag(str(path)))


# Enabling the bundled plugins.

DUPE_NAME = 'Highlight duplicate fields'


@pytest.fixture
def every_plugin(clean_profile, monkeypatch):
    tick(monkeypatch, 'dupe_fields', 'extended_tags', 'id3_tools', 'modified_time', 'save_tags', 'view_all_fields')


@pytest.fixture
def five_plugins(clean_profile, monkeypatch):
    tick(monkeypatch, 'dupe_fields', 'id3_tools', 'modified_time', 'save_tags', 'view_all_fields')


def test_plugins_page_lists_the_bundled_plugins(user):
    # preferences.txt, Plugins: "Plugins are a means with which to extend
    # puddletag... Enable it, then restart." The docs are silent on the
    # names: they are the plugins' own info names.
    dialog = user.open_preferences('Plugins')
    assert listed_plugins(dialog.stack.currentWidget()) == [
        ('Extended Tags', False), (DUPE_NAME, False), ('ID3 Tools', False),
        ('Modtime + 2sec', False), ('Save tags', False), ('View All Fields', False)]
    user.close_preferences(dialog, 'Cancel')


def test_bundled_plugin_ticked_on_the_plugins_page_starts_after_a_restart(monkeypatch, mainwin, user, qtbot, restart):
    # plugins.txt: "To use a plugin, tick it on the Plugins page of
    # Edit->Preferences, then restart puddletag."
    forget(monkeypatch, 'dupe_fields')
    dialog = user.open_preferences('Plugins')
    click_check_box(user, dialog.stack.currentWidget(), DUPE_NAME)
    user.close_preferences(dialog)
    assert PuddleConfig().get('plugins', 'to_load', None) == ['dupe_fields']
    assert 'Dupe highlight' not in menu(mainwin, '&Plugins')

    new = restart()

    assert menu(new, '&Plugins') == ['Dupe highlight']


def test_every_bundled_plugin_ticked_starts_without_errors(every_plugin, mainwin, user, qtbot, make_audio, tmp_path,
                                                           caplog):
    # plugins.txt: "A plugin that can't be loaded is left out, and the
    # reason is written to puddletag's log". The docs are silent on the
    # commands.
    assert startup_errors(caplog, 'setup') == []
    assert sorted(menu(mainwin, '&Plugins')) == [
        'Add 2 seconds to modified time', 'Dupe highlight', 'Export tags', 'Save Extended', 'Show all fields']
    assert menu(mainwin, 'Ta&g Tools')[-2:] == ['&Update to ID3v2.4', '&Convert to UTF-8']
    assert 'Extended Tags' in menu(mainwin, '&Windows')

    make_audio('01.mp3', tmp_path / 'music', title='Song')
    load(mainwin, user, qtbot, tmp_path / 'music', 1)

    assert user.action('&Update to ID3v2.4').isEnabled()


def test_bundled_plugins_commands_are_in_the_window_started_again(five_plugins, mainwin, restart):
    # plugins.txt: "then restart puddletag."
    new = restart()

    commands = ['Add 2 seconds to modified time', 'Dupe highlight', 'Export tags', 'Show all fields']
    assert sorted(menu(new, '&Plugins')) == commands
    assert menu(new, 'Ta&g Tools')[-2:] == ['&Update to ID3v2.4', '&Convert to UTF-8']
    assert sorted(menu(mainwin, '&Plugins')) == commands


# Highlight duplicate fields.

@pytest.fixture
def dupe_highlight(clean_profile, monkeypatch):
    tick(monkeypatch, 'dupe_fields')


@pytest.fixture
def three_files(make_audio, tmp_path):
    return [make_audio(name, tmp_path / 'music', artist=artist, title=title)
            for name, artist, title in (('01.mp3', 'X', 'T1'), ('02.mp3', 'X', 'T2'), ('03.mp3', 'Y', 'T3'))]


def test_dupe_highlight_colours_files_with_the_same_value(dupe_highlight, mainwin, user, qtbot, dialogs,
                                                          three_files, tmp_path):
    # The plugin's info: "Adds shortcut to Plugins to highlight files which
    # have the same value for a field." Files 01 and 02 share an artist.
    before = [in_file(p) for p in three_files]
    load(mainwin, user, qtbot, tmp_path / 'music', 3)

    dialogs.answer('QInputDialog.getText', ('artist', True))
    user.click_menu('Dupe highlight')

    assert highlighted(mainwin) == [True, True, False]
    assert user.action('Dupe highlight').isChecked()
    assert calls(dialogs, 'QInputDialog.getText')[0][1:] == ('puddletag', 'Field to compare')
    assert [in_file(p) for p in three_files] == before


def test_dupe_highlight_clicked_again_clears_the_colour(dupe_highlight, mainwin, user, qtbot, dialogs,
                                                        three_files, tmp_path):
    # The plugin's info: "Adds shortcut to Plugins to highlight files which
    # have the same value for a field." Docs silent on clearing: clicking
    # the ticked command again is the only way a user has.
    before = [in_file(p) for p in three_files]
    load(mainwin, user, qtbot, tmp_path / 'music', 3)
    dialogs.answer('QInputDialog.getText', ('artist', True))
    user.click_menu('Dupe highlight')

    user.click_menu('Dupe highlight')

    assert highlighted(mainwin) == [False] * 3
    assert not user.action('Dupe highlight').isChecked()
    assert [in_file(p) for p in three_files] == before


def test_dupe_highlight_cancelled_stays_unticked(dupe_highlight, mainwin, user, qtbot, dialogs,
                                                 three_files, tmp_path):
    # The plugin's info: "Adds shortcut to Plugins to highlight files which
    # have the same value for a field." Docs silent on Cancel: a command
    # that did nothing shouldn't show as on.
    before = [in_file(p) for p in three_files]
    load(mainwin, user, qtbot, tmp_path / 'music', 3)

    dialogs.answer('QInputDialog.getText', ('', False))
    user.click_menu('Dupe highlight')

    assert not user.action('Dupe highlight').isChecked()
    assert highlighted(mainwin) == [False] * 3
    assert [in_file(p) for p in three_files] == before


def test_dupe_highlight_with_one_file_selected_stays_unticked(dupe_highlight, mainwin, user, qtbot, dialogs,
                                                              three_files, tmp_path):
    # The plugin's info: "Adds shortcut to Plugins to highlight files which
    # have the same value for a field." Docs silent: with one file there is
    # nothing to compare, so the command shouldn't show as on.
    before = [in_file(p) for p in three_files]
    load(mainwin, user, qtbot, tmp_path / 'music', 3)
    user.click_cell(user.cell(0, 'title'))

    dialogs.answer('QInputDialog.getText', ('artist', True))
    user.click_menu('Dupe highlight')

    assert not user.action('Dupe highlight').isChecked()
    assert highlighted(mainwin) == [False] * 3
    assert [in_file(p) for p in three_files] == before


def test_dupe_highlight_colours_same_values_apart(dupe_highlight, mainwin, user, qtbot, dialogs,
                                                  make_audio, tmp_path):
    # The plugin's info: "Adds shortcut to Plugins to highlight files which
    # have the same value for a field." Files 01 and 03 share an artist with
    # 02 between them (synthetic).
    paths = [make_audio(name, tmp_path / 'music', artist=artist, title=title)
             for name, artist, title in (('01.mp3', 'X', 'T1'), ('02.mp3', 'Y', 'T2'), ('03.mp3', 'X', 'T3'))]
    before = [in_file(p) for p in paths]
    load(mainwin, user, qtbot, tmp_path / 'music', 3)

    dialogs.answer('QInputDialog.getText', ('artist', True))
    user.click_menu('Dupe highlight')

    assert highlighted(mainwin) == [True, False, True]
    assert [in_file(p) for p in paths] == before


# Modtime + 2sec.

@pytest.fixture
def modtime(clean_profile, monkeypatch):
    tick(monkeypatch, 'modified_time')


def test_add_two_seconds_keeps_the_fraction(modtime, mainwin, user, qtbot, make_audio, tmp_path):
    # The plugin's info: "Add a shortcut to the plugins menu that increases
    # the selected files' modified time by two seconds." The docs are silent
    # on the fraction of a second; two seconds more is what the info says.
    # The files are synthetic.
    paths = [make_audio(f'0{n}.mp3', tmp_path / 'music', title=f'T{n}') for n in (1, 2)]
    for path in paths:
        os.utime(path, ns=(1_000_000_000_500_000_000, 1_000_000_000_500_000_000))
    load(mainwin, user, qtbot, tmp_path / 'music', 2)

    user.click_menu('Add 2 seconds to modified time')

    # The access time isn't checked: relatime can change it when a file is read.
    qtbot.waitUntil(lambda: [os.stat(p).st_mtime_ns for p in paths] == [1_000_000_002_500_000_000] * 2)
    assert [in_file(p)['title'] for p in paths] == [['T1'], ['T2']]


def test_add_two_seconds_refused_in_preview_mode(modtime, mainwin, user, qtbot, make_audio, tmp_path, dialogs):
    # The plugin's info: "Add a shortcut to the plugins menu that increases
    # the selected files' modified time by two seconds." The docs are silent
    # on Preview Mode; the plugin asks to leave it first. The file is
    # synthetic.
    path = make_audio('01.mp3', tmp_path / 'music', title='Song')
    os.utime(path, (1_000_000_000, 1_000_000_000))
    load(mainwin, user, qtbot, tmp_path / 'music', 1)

    user.click_menu('Enabl&e Preview Mode')
    dialogs.answer('QMessageBox.information', Ok)
    user.press(Qt.Key.Key_M, Qt.KeyboardModifier.ControlModifier)

    assert calls(dialogs, 'QMessageBox.information')[0][1:] == ('puddletag', PREVIEW_REFUSAL)
    assert os.stat(path).st_mtime == 1_000_000_000


@pytest.mark.xfail(strict=True, reason='puddletag spells "occurred" as "occured"')
def test_add_two_seconds_to_a_file_gone_from_disk(modtime, mainwin, user, qtbot, make_audio, tmp_path, dialogs):
    # The plugin's info: "Add a shortcut to the plugins menu that increases
    # the selected files' modified time by two seconds." The docs are silent
    # on a file that is gone; the plugin reports the error. The file is
    # synthetic.
    path = make_audio('01.mp3', tmp_path / 'music', title='Song')
    load(mainwin, user, qtbot, tmp_path / 'music', 1)
    os.remove(path)
    dialogs.answer('QMessageBox.warning', Ok)

    user.click_menu('Add 2 seconds to modified time')

    assert calls(dialogs, 'QMessageBox.warning')[0][1:] == (
        'Error',
        f'An error occurred while setting the modification time of <b>{path}</b>. (No such file or directory)')


# Save tags.

@pytest.fixture
def save_tags_plugin(clean_profile, monkeypatch):
    """Save tags ticked on the Plugins page in an earlier session. Name it
    before mainwin in a test's arguments, so the profile holds it when the
    window is built."""
    tick(monkeypatch, 'save_tags')


@pytest.fixture
def exported_files(save_tags_plugin, mainwin, make_audio, tmp_path, qtbot, user):
    """Two MP3s (T1, T2) loaded and selected, with their bytes: (paths,
    bytes_of). Synthetic."""
    music = tmp_path / 'music'
    paths = [make_audio(f'0{number}.mp3', music, title=f'T{number}') for number in (1, 2)]
    contents = [open(path, 'rb').read() for path in paths]
    load(mainwin, user, qtbot, music, 2)
    return paths, contents


def unchanged(paths, contents):
    return [open(path, 'rb').read() for path in paths] == contents


def test_export_tags_pickles_the_selected_files_tags(exported_files, dialogs, user, tmp_path):
    # Save tags' info: "Adds shortcut to Plugins menu to save the selected
    # files' tags for debugging purposes." The docs don't describe the
    # format: the file holds a list of mutagen files, one per selected file.
    paths, contents = exported_files
    out = tmp_path / 'tags.pickle'
    dialogs.answer('QFileDialog.getSaveFileName', (str(out), '*.*'))

    user.click_menu('Export tags')

    with open(out, 'rb') as f:
        exported = pickle.load(f)
    assert [e.filename for e in exported] == [str(p) for p in paths]
    assert [e.tags['TIT2'].text for e in exported] == [['T1'], ['T2']]
    assert unchanged(paths, contents)
    assert calls(dialogs, 'QFileDialog.getSaveFileName') == [(None, 'Save tags', '~', '*.*')]


def test_export_tags_opens_in_the_last_exports_folder(exported_files, dialogs, user, tmp_path):
    # Save tags' info: "Adds shortcut to Plugins menu to save the selected
    # files' tags for debugging purposes." The docs are silent on the
    # dialog's folder: it starts at the folder of the last export.
    again = tmp_path / 'again'
    again.mkdir()
    dialogs.answer('QFileDialog.getSaveFileName', (str(tmp_path / 'tags.pickle'), '*.*'))
    user.click_menu('Export tags')
    dialogs.answer('QFileDialog.getSaveFileName', (str(again / 'tags.pickle'), '*.*'))

    user.click_menu('Export tags')

    assert calls(dialogs, 'QFileDialog.getSaveFileName')[1][2] == str(tmp_path)


def test_export_tags_cancelled_writes_nothing(exported_files, dialogs, user, tmp_path):
    # Save tags' info: "Adds shortcut to Plugins menu to save the selected
    # files' tags for debugging purposes." The docs are silent on Cancel:
    # nothing is written.
    paths, contents = exported_files
    dialogs.answer('QFileDialog.getSaveFileName', ('', ''))

    user.click_menu('Export tags')

    assert sorted(p.name for p in tmp_path.iterdir()) == ['music']
    assert unchanged(paths, contents)


# View All Fields.

@pytest.fixture
def all_fields(clean_profile, monkeypatch):
    tick(monkeypatch, 'view_all_fields')


def add_genre_on_the_page(user, dialogs):
    window = user.open_preferences('View All Fields')
    page = window.stack.currentWidget()
    [buttons] = page.findChildren(ListButtons)
    dialogs.answer('QInputDialog.getItem', ('genre', True))
    user.click(buttons.addButton)
    user.close_preferences(window)


@pytest.fixture
def song(all_fields, mainwin, make_audio, tmp_path, qtbot, user):
    make_audio('song.mp3', tmp_path / 'music', title='Song', artist='A', genre='Rock')
    load(mainwin, user, qtbot, tmp_path / 'music', 1)


def test_show_all_fields_and_back(song, mainwin, user):
    # The plugin's description: "Adds a shortcut to the Plugins menu to show
    # all fields." The docs are silent on the columns shown; the default
    # fields on the page are __filename and __dirpath.
    before = headers(mainwin)

    user.click_menu('Show all fields')

    assert headers(mainwin) == ['__filename', '__dirpath', 'artist', 'genre', 'title']
    assert [title for title, field in mainwin._table.model().headerdata] == headers(mainwin)
    assert user.action('Show all fields').isChecked()

    user.click_menu('Show all fields')

    assert headers(mainwin) == before
    assert not user.action('Show all fields').isChecked()


def test_view_all_fields_page_adds_a_field(song, mainwin, user, dialogs):
    # Docs silent: the page lists the fields shown first, __filename and
    # __dirpath by default; OK saves the list.
    before = headers(mainwin)

    add_genre_on_the_page(user, dialogs)

    cparser = PuddleConfig(os.path.join(SAVEDIR, 'view_all_fields'))
    assert cparser.get('view_all_fields', 'fields', None) == ['__filename', '__dirpath', 'genre']
    assert headers(mainwin) == before


def test_view_all_fields_page_applies_to_the_shown_fields(song, mainwin, user, dialogs):
    # Docs silent: with Show all fields ticked, the fields saved on the page
    # are the ones shown first.
    user.click_menu('Show all fields')

    add_genre_on_the_page(user, dialogs)

    assert headers(mainwin) == ['__filename', '__dirpath', 'genre', 'artist', 'title']


def test_preferences_ok_keeps_the_columns_while_all_fields_are_shown(song, mainwin, user, restart):
    # preferences.txt, Columns: "In this panel you can modify the columns
    # listed in the file-view." plugins.txt: "Click it again to get your
    # columns back."
    before = headers(mainwin)
    titles = [title for title, field in mainwin._table.model().headerdata]
    user.click_menu('Show all fields')

    window = user.open_preferences('Columns')
    page = window.stack.currentWidget()
    assert [page.listbox.item(i).text() for i in range(page.listbox.count())] == titles
    user.close_preferences(window)

    assert headers(mainwin) == ['__filename', '__dirpath', 'artist', 'genre', 'title']
    assert PuddleConfig().get('tableheader', 'tags', before) == before
    user.click_menu('Show all fields')
    assert headers(mainwin) == before
    assert headers(restart()) == before


def test_quitting_while_all_fields_are_shown_keeps_the_columns(song, mainwin, user, restart):
    # preferences.txt, Columns: "Any unchecked columns will not be shown."
    before = headers(mainwin)
    window = user.open_preferences('Columns')
    page = window.stack.currentWidget()
    tick_list_item(user, page.listbox, page.listbox.item(before.index('track')))
    user.close_preferences(window)
    assert mainwin._table.horizontalHeader().isSectionHidden(before.index('track'))

    user.click_menu('Show all fields')
    new = restart()

    assert headers(new) == before
    assert [i for i in range(len(before)) if new._table.horizontalHeader().isSectionHidden(i)] == [before.index('track')]


# ID3 Tools.

UPDATE = '&Update to ID3v2.4'
CONVERT = '&Convert to UTF-8'


@pytest.fixture
def id3_tools(clean_profile, monkeypatch):
    tick(monkeypatch, 'id3_tools')


@pytest.fixture
def id3v23_preference(clean_profile, monkeypatch):
    """The profile of a user who chose ID3v2.3 as the version to write.
    Startup sets the module's global from the config and nothing puts it
    back."""
    PuddleConfig().set('id3tags', 'v2_option', 3)
    monkeypatch.setattr(audioinfo.id3, 'v2_option', audioinfo.id3.v2_option)


def v23(path):
    """The file as another program wrote it: ID3v2.3."""
    tags = mutagen.id3.ID3(str(path))
    tags.save(v2_version=3)
    return path


def version(path):
    return mutagen.id3.ID3(str(path)).version


def test_update_to_id3v24(id3_tools, mainwin, user, make_audio, qtbot, tmp_path):
    # ID3 Tools (info): "Extra functions for handling ID3 tags added to the
    # Tag Tools menu." The docs are silent: Update to ID3v2.4 rewrites the
    # ID3v2.3 tags of the selected files as ID3v2.4. Synthetic files.
    paths = [v23(make_audio(name, tmp_path / 'music', title=title))
             for name, title in (('01.mp3', 'T1'), ('02.mp3', 'T2'))]
    before = [in_file(path) for path in paths]
    assert [version(path) for path in paths] == [(2, 3, 0)] * 2
    load(mainwin, user, qtbot, tmp_path / 'music', 2)
    user.click_menu(UPDATE)
    qtbot.waitUntil(lambda: [version(path) for path in paths] == [(2, 4, 0)] * 2)
    user.activate()
    assert [in_file(path) for path in paths] == before
    assert [a['__tag'] for a in mainwin._table.model().taginfo] == ['ID3v2.4'] * 2


def test_update_to_id3v24_with_the_id3v23_preference(id3_tools, id3v23_preference, mainwin, user, make_audio,
                                                     qtbot, tmp_path):
    # ID3 Tools (info): "Extra functions for handling ID3 tags added to the
    # Tag Tools menu." The command's name says what it does, whatever
    # version the preferences write by default. Synthetic file.
    path = v23(make_audio('01.mp3', tmp_path / 'music', title='T1'))
    load(mainwin, user, qtbot, tmp_path / 'music', 1)
    user.click_menu(UPDATE)
    qtbot.waitUntil(lambda: version(path) == (2, 4, 0))


def test_convert_to_utf8(id3_tools, mainwin, user, make_audio, qtbot, tmp_path):
    # ID3 Tools (info): "Extra functions for handling ID3 tags added to the
    # Tag Tools menu." The docs are silent: Convert to UTF-8 stores the text
    # frames as UTF-8, which ID3v2.4 has. Synthetic file, written with
    # UTF-16 and Latin-1 frames.
    path = make_audio('01.mp3', tmp_path / 'music', title='x')
    tags = mutagen.id3.ID3(str(path))
    tags.add(mutagen.id3.TIT2(encoding=1, text=['Song']))
    tags.add(mutagen.id3.TPE1(encoding=0, text=['Artist']))
    tags.save(v2_version=3)
    load(mainwin, user, qtbot, tmp_path / 'music', 1)
    user.click_menu(CONVERT)
    qtbot.waitUntil(lambda: version(path) == (2, 4, 0))
    raw = mutagen.id3.ID3(str(path))
    assert [f.encoding for f in (raw['TIT2'], raw['TPE1'])] == [3, 3]
    assert [raw['TIT2'].text, raw['TPE1'].text] == [['Song'], ['Artist']]


def test_id3_tools_need_a_selection(id3_tools, mainwin, user, make_audio, qtbot, tmp_path):
    # ID3 Tools (info): "Extra functions for handling ID3 tags added to the
    # Tag Tools menu." Like the other Tag Tools they work on the selected
    # files, so they are greyed out until a file is selected. Synthetic file.
    make_audio('01.mp3', tmp_path / 'music', title='T1')
    mainwin.openDir(str(tmp_path / 'music'), False)
    qtbot.waitUntil(lambda: mainwin._table.model().rowCount() == 1)
    user.activate()
    user.click(user.table.viewport(), user.table.viewport().rect().bottomRight())
    assert not user.action(UPDATE).isEnabled()
    assert not user.action(CONVERT).isEnabled()
    user.click_cell(user.cell(0, 'title'))
    assert user.action(UPDATE).isEnabled()
    assert user.action(CONVERT).isEnabled()


@pytest.mark.parametrize('command', [UPDATE, CONVERT])
def test_id3_tools_refused_in_preview_mode(id3_tools, mainwin, user, make_audio, qtbot, dialogs, tmp_path,
                                           command):
    # menus.txt, Enable Preview Mode: "When enabled any changes you make will
    # not get written." ID3 Tools write at once, so they refuse, as
    # Modtime + 2sec does. Synthetic file.
    path = v23(make_audio('01.mp3', tmp_path / 'music', title='T1'))
    load(mainwin, user, qtbot, tmp_path / 'music', 1)
    user.click_menu('Enabl&e Preview Mode')
    dialogs.answer('QMessageBox.information', Ok)
    user.click_menu(command)
    assert calls(dialogs, 'QMessageBox.information')[0][1:] == ('puddletag', PREVIEW_REFUSAL)
    assert version(path) == (2, 3, 0)


def test_id3_tools_leave_other_formats_alone(id3_tools, mainwin, user, make_audio, qtbot, tmp_path):
    # ID3 Tools (info): "Extra functions for handling ID3 tags added to the
    # Tag Tools menu." The docs are silent about other formats: a FLAC file
    # among the selected files is left as it is. Synthetic files.
    music = tmp_path / 'music'
    mp3 = v23(make_audio('01.mp3', music, title='T1'))
    flac = make_audio('02.flac', music, title='T2')
    flac_bytes = flac.read_bytes()
    load(mainwin, user, qtbot, music, 2)
    user.click_menu(UPDATE)
    qtbot.waitUntil(lambda: version(mp3) == (2, 4, 0))
    user.activate()
    assert flac.read_bytes() == flac_bytes


@pytest.mark.xfail(strict=True, reason='puddletag spells "occurred" as "occured"')
@pytest.mark.skipif(os.geteuid() == 0, reason='root can write a read-only file')
@pytest.mark.parametrize('command, verb', [(UPDATE, 'updating'), (CONVERT, 'converting')])
def test_id3_tools_on_a_read_only_file(id3_tools, mainwin, user, make_audio, qtbot, dialogs, tmp_path, command,
                                       verb):
    # ID3 Tools (info): "Extra functions for handling ID3 tags added to the
    # Tag Tools menu." The docs are silent about a file that can't be
    # written: as the other Tag Tools do, the user is warned and the file
    # stays as it is. Synthetic file, read-only (0444).
    path = v23(make_audio('01.mp3', tmp_path / 'music', title='T1'))
    before = in_file(path)
    os.chmod(path, 0o444)
    load(mainwin, user, qtbot, tmp_path / 'music', 1)
    dialogs.answer('QMessageBox.warning', Ok)
    user.click_menu(command)
    user.activate()
    assert calls(dialogs, 'QMessageBox.warning')[0][1:] == (
        'Error', f'An error occurred while {verb} <b>{path}</b>. (Permission denied)')
    assert version(path) == (2, 3, 0)
    assert in_file(path) == before
