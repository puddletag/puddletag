"""Plugins, used as plugins.txt and preferences.txt describe them: a
folder in the user's plugin folder holding __init__.py and info, ticked on
the Plugins page of Preferences, loaded when puddletag starts again. Each
test writes its own synthetic plugins, except the docs' example tag
source, which is extracted from the archive the docs offer.
"""
import gzip
import importlib.util
import logging
import sys
import tarfile
from pathlib import Path

import pytest
from PyQt6.QtCore import QModelIndex, Qt
from PyQt6.QtWidgets import QApplication, QPushButton, QStyle, QStyleOptionViewItem

from puddlestuff import audioinfo, tagsources
from puddlestuff.constants import PLUGINDIR
from puddlestuff.mainwin.tagsources import SimpleDialog
from puddlestuff.masstag.dialogs import MassTagEdit, MassTagWindow, MTProfileEdit, TSProfileEdit
from puddlestuff.pluginloader import InfoWidget
from puddlestuff.puddleobjects import PuddleConfig
from puddlestuff.puddlesettings import SettingsDialog

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier

DOCS = Path(__file__).parents[2] / 'docsrc'


@pytest.fixture(autouse=True)
def new_process(clean_profile):
    """Each test starts as a new puddletag process does: no plugin
    imported and only the built-in tag sources. MainWin adds a ticked
    plugin's sources to a module-level list and Python keeps the module it
    imported, so both are put back before and after each test, and before a
    restart through start_again (a test names this fixture to get the
    function that does it)."""
    saved = list(tagsources.tagsources)

    def forget():
        tagsources.tagsources[:] = saved
        for name in [n for n, module in sys.modules.items() if n.startswith('puddlestuff.plugins.')
                     and (getattr(module, '__file__', None) or '').startswith(PLUGINDIR)]:
            del sys.modules[name]
        importlib.invalidate_caches()

    forget()
    yield forget
    forget()


def start_again(restart, new_process):
    """Quits puddletag and starts it again, as a new process: see
    new_process. Returns the new window."""
    new_process()
    return restart()


def write_plugin(module, name, code, missing=(), **values):
    """A plugin in the user's plugin folder, laid out as plugins.txt says:
    <module>/__init__.py holding code, and <module>/info with the five keys
    in its [info] section, but those in missing; values replace the
    defaults. Synthetic."""
    folder = Path(PLUGINDIR) / module
    folder.mkdir(parents=True)
    keys = dict({'author': 'Synthetic Author', 'description': 'A synthetic plugin', 'name': name,
                 'puddletag_version': '2.5.0', 'version': '1.0'}, **values)
    lines = [f'{key} = {value}' for key, value in keys.items() if key not in missing]
    (folder / 'info').write_text('[info]\n' + '\n'.join(lines) + '\n')
    (folder / '__init__.py').write_text(code)
    return folder


def source_code(*names):
    """A plugin's __init__.py whose tagsources list holds one source per
    name; each finds nothing. Synthetic."""
    classes = [f"class Source{n}:\n"
               f"    group_by = ['album']\n"
               f"    name = {name!r}\n\n"
               f"    def search(self, album, artists):\n"
               f"        return []\n\n\n" for n, name in enumerate(names)]
    return ''.join(classes) + f"tagsources = [{', '.join(f'Source{n}' for n in range(len(names)))}]\n"


def tick(*modules):
    """The profile as ticking these plugins on the Plugins page in an
    earlier session leaves it: their folders' names in plugins.to_load."""
    PuddleConfig().set('plugins', 'to_load', list(modules))


def imported(module):
    return f'puddlestuff.plugins.{module}' in sys.modules


def tag_sources_window():
    from puddlestuff.puddletag import status
    return status['dialogs']['Tag Sources']


def listed_sources():
    """The names in the Tag Sources window's Source box."""
    box = tag_sources_window().sourcelist
    return [box.itemText(n) for n in range(box.count())]


def open_preferences(user, qtbot, mainwin):
    user.click_menu('&Preferences')
    qtbot.waitUntil(lambda: any(w.isVisible() for w in mainwin.findChildren(SettingsDialog)))
    [dialog] = [w for w in mainwin.findChildren(SettingsDialog) if w.isVisible()]
    user.activate(dialog)
    return dialog


def plugins_page(user, qtbot, mainwin):
    """Opens Preferences on its Plugins page; returns the dialog and the
    page."""
    dialog = open_preferences(user, qtbot, mainwin)
    [row] = [r for r, w in dialog._widgets.items() if w[0] == 'Plugins']
    index = dialog.model.index(row, 0)
    user.click(dialog.listbox.viewport(), dialog.listbox.visualRect(index).center())
    page = dialog._widgets[row][1]
    qtbot.waitUntil(lambda: dialog.stack.currentWidget() is page)
    return dialog, page


def listed_plugins(page):
    """The Plugins page's items: (name, ticked)."""
    box = page._listbox
    return [(box.item(r).text(), box.item(r).checkState() == Qt.CheckState.Checked) for r in range(box.count())]


def plugin_item(page, name):
    [item] = page._listbox.findItems(name, Qt.MatchFlag.MatchExactly)
    return item


def click_check_box(user, page, name):
    """Clicks the plugin's check box: the style's check indicator rect."""
    listbox = page._listbox
    item = plugin_item(page, name)
    option = QStyleOptionViewItem()
    listbox.initViewItemOption(option)
    option.rect = listbox.visualItemRect(item)
    option.features |= QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
    check_box = listbox.style().subElementRect(QStyle.SubElement.SE_ItemViewItemCheckIndicator, option, listbox)
    user.click(listbox.viewport(), check_box.center())


def click_ok(user, qtbot, dialog):
    user.click(dialog.okbuttons.okButton)
    qtbot.waitUntil(lambda: not dialog.isVisible())
    user.activate()


def startup_errors(caplog, phase, level=logging.ERROR):
    """The messages logged at this level while MainWin was built: in
    'setup' when the mainwin fixture built it, in 'call' after a restart."""
    return [r.getMessage() for r in caplog.get_records(phase) if r.levelno == level]


def button(widget, text):
    """The button with this text in widget's own window, not in a dialog
    it opened earlier (closed dialogs stay its children)."""
    [found] = [b for b in widget.findChildren(QPushButton)
               if b.text() == text and b.window() is widget.window()]
    return found


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


def albums(window):
    """The Tag Sources window's album list, as shown."""
    model = window.listbox.model()
    return [model.index(row, 0, QModelIndex()).data() for row in range(model.rowCount(QModelIndex()))]


def click_album(user, window, album):
    [row] = [row for row, shown in enumerate(albums(window)) if f' - {album}' in shown]
    tree = window.listbox
    user.click(tree.viewport(), tree.visualRect(tree.model().index(row, 0, QModelIndex())).center())


def previews(mainwin):
    return [dict(audio.preview) for audio in mainwin._table.model().taginfo]


def in_file(path):
    return audioinfo.usertags(audioinfo.Tag(str(path)))


# Loading and the Plugins page.

INFO_KEYS = ['author', 'description', 'name', 'puddletag_version', 'version']

SYNTHETIC = 'synthetic_plugin'


@pytest.fixture
def unticked_plugin(clean_profile):
    """A synthetic tag source plugin in the user's plugin folder, written
    before mainwin builds the window."""
    write_plugin(SYNTHETIC, 'Synthetic Plugin', source_code('Plugin Source'),
                 description='A synthetic tag source plugin')


@pytest.fixture
def ticked_plugin(unticked_plugin):
    tick(SYNTHETIC)


@pytest.fixture
def incomplete_plugin(clean_profile, key):
    """A ticked plugin whose info lacks the key, in the user's plugin folder
    before mainwin builds the window. Synthetic: as if ticked before its
    info lost the key."""
    write_plugin('incomplete_plugin', 'Incomplete Plugin', source_code('Incomplete Source'), missing=(key,))
    tick('incomplete_plugin')


@pytest.fixture
def broken_and_good_plugins(clean_profile):
    write_plugin('broken_plugin', 'Broken Plugin', "raise RuntimeError('synthetic import failure')\n")
    write_plugin(SYNTHETIC, 'Synthetic Plugin', source_code('Plugin Source'))
    tick('broken_plugin', SYNTHETIC)


def test_plugin_that_isnt_ticked_isnt_loaded(unticked_plugin, mainwin, user, qtbot):
    # preferences.txt: "If you want to install one drop it into ... Enable
    # it, then restart." plugins.txt: "Plugins will be imported using
    # **modulename**". The plugin is synthetic, and nothing is ticked.
    dialog, page = plugins_page(user, qtbot, mainwin)
    assert ('Synthetic Plugin', False) in listed_plugins(page)
    assert not imported(SYNTHETIC)
    assert 'Plugin Source' not in listed_sources()
    click_ok(user, qtbot, dialog)


def test_unticking_a_plugin_unloads_it_after_a_restart(ticked_plugin, mainwin, user, qtbot, restart,
                                                       new_process):
    # preferences.txt: "Enable it, then restart." The Plugins page says
    # "Loading/unloading plugins requires a restart." The plugin is
    # synthetic.
    assert imported(SYNTHETIC)
    assert 'Plugin Source' in listed_sources()
    dialog, page = plugins_page(user, qtbot, mainwin)
    assert ('Synthetic Plugin', True) in listed_plugins(page)
    click_check_box(user, page, 'Synthetic Plugin')
    assert plugin_item(page, 'Synthetic Plugin').checkState() == Qt.CheckState.Unchecked
    click_ok(user, qtbot, dialog)
    assert PuddleConfig().get('plugins', 'to_load', None) == []

    new = start_again(restart, new_process)

    assert not imported(SYNTHETIC)
    assert 'Plugin Source' not in listed_sources()
    _, page = plugins_page(type(user)(qtbot, new), qtbot, new)
    assert ('Synthetic Plugin', False) in listed_plugins(page)


@pytest.mark.parametrize('key', INFO_KEYS)
def test_plugin_missing_an_info_key_is_left_out(key, incomplete_plugin, mainwin, user, qtbot):
    # plugins.txt: "keep in mind that all keys are case sensitive" and
    # "Your plugin will not be loaded unless all this information is
    # present." The plugin is synthetic.
    assert not imported('incomplete_plugin')
    assert 'Incomplete Source' not in listed_sources()
    dialog, page = plugins_page(user, qtbot, mainwin)
    # Found by folder: with name missing there's no name to look for.
    folders = [page._listbox.item(r).plugin['module'] for r in range(page._listbox.count())]
    assert 'incomplete_plugin' not in folders
    click_ok(user, qtbot, dialog)


def test_plugin_that_fails_to_import_is_logged_and_the_others_load(broken_and_good_plugins, mainwin, user,
                                                                   qtbot, caplog):
    # plugins.txt: "A plugin that can't be loaded is left out, and the
    # reason is written to puddletag's log." The docs don't say what the log
    # says; this is what puddletag does. The plugins are synthetic. Plugins
    # load in name order, so the broken one comes first.
    [message] = [m for m in startup_errors(caplog, 'setup') if 'plugin' in m]
    assert message.startswith('Failed to load plugin Broken Plugin')
    assert not imported('broken_plugin')
    assert imported(SYNTHETIC)
    assert 'Plugin Source' in listed_sources()


def test_plugins_page_shows_the_plugins_info(unticked_plugin, mainwin, user, qtbot):
    # plugins.txt: "**name**: The name of the plugin as it'll be displayed
    # to a puddletag user." and the descriptions of author, description and
    # version. The plugin is synthetic.
    dialog, page = plugins_page(user, qtbot, mainwin)
    rect = page._listbox.visualItemRect(plugin_item(page, 'Synthetic Plugin'))
    user.click(page._listbox.viewport(), rect.center())
    [info] = page.findChildren(InfoWidget)
    shown = info.text()
    for text in ('Synthetic Plugin', 'Synthetic Author', 'A synthetic tag source plugin', '1.0'):
        assert text in shown
    assert '2.5.0' not in shown
    assert ('Synthetic Plugin', False) in listed_plugins(page)
    click_ok(user, qtbot, dialog)


def test_tag_source_plugin_is_offered_in_a_mass_tagging_profile(ticked_plugin, mainwin, user, qtbot):
    # tut5.txt: "Clicking on the Add Tag Source ("+") button should bring
    # up this dialog", whose Source box is "The tag source to use." The
    # plugin is synthetic.
    user.click_menu('Mass Tagging')
    [window] = mainwin.findChildren(MassTagWindow)
    qtbot.waitUntil(window.isVisible)
    user.click(button(window, '&Configure Profiles'))
    profiles = opened(qtbot, MassTagEdit)
    user.click(profiles.buttonlist.addButton)
    editor = opened(qtbot, MTProfileEdit)
    user.activate(editor)
    user.click(editor.buttonlist.addButton)
    config = opened(qtbot, TSProfileEdit)
    listed = [config.source.itemText(n) for n in range(config.source.count())]
    user.click(button(config, 'Cancel'))
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is editor)
    user.click(button(editor, 'Cancel'))
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is profiles)
    user.click(button(profiles, 'Cancel'))
    assert 'Plugin Source' in listed


def test_tag_source_plugin_appears_in_the_source_list(unticked_plugin, mainwin, user, qtbot, restart,
                                                      new_process):
    # plugins.txt: "In order for a plugin to be registered the following
    # tree structure is required". The plugin is synthetic.
    dialog, page = plugins_page(user, qtbot, mainwin)
    click_check_box(user, page, 'Synthetic Plugin')
    assert plugin_item(page, 'Synthetic Plugin').checkState() == Qt.CheckState.Checked
    click_ok(user, qtbot, dialog)

    start_again(restart, new_process)

    assert 'Plugin Source' in listed_sources()


# Info files puddletag can't use as they are.

@pytest.fixture
def comma_in_description(clean_profile):
    """A plugin whose description holds a comma, in the user's plugin folder
    before mainwin builds the window."""
    write_plugin(SYNTHETIC, 'Synthetic Plugin', source_code('Plugin Source'),
                 description='Looks up albums, quickly')


def test_unreadable_info_is_logged_and_puddletag_starts(mainwin, user, qtbot, restart, new_process, caplog):
    # plugins.txt: "**info** is a INI file", "Your plugin will not be
    # loaded unless all this information is present." and "A plugin that
    # can't be loaded is left out, and the reason is written to puddletag's
    # log." The info file is synthetic.
    folder = write_plugin('unreadable_plugin', 'Unreadable Plugin', source_code('Unreadable Source'))
    (folder / 'info').write_text('[info]\nthis line is not ini\n')
    write_plugin(SYNTHETIC, 'Synthetic Plugin', source_code('Plugin Source'))
    tick('unreadable_plugin', SYNTHETIC)

    new = start_again(restart, new_process)

    assert 'Plugin Source' in listed_sources()
    assert not imported('unreadable_plugin')
    [message] = startup_errors(caplog, 'call', logging.WARNING)
    assert message.startswith("Plugin unreadable_plugin not loaded: its info file can't be read")
    dialog, page = plugins_page(type(user)(qtbot, new), qtbot, new)
    shown = [name for name, _ in listed_plugins(page)]
    assert 'Synthetic Plugin' in shown
    assert 'Unreadable Plugin' not in shown


def test_info_value_with_a_comma_is_shown_as_written(comma_in_description, mainwin, user, qtbot):
    # plugins.txt: "**description**: Add a short synopsis of what your
    # plugin does." The description is synthetic.
    dialog, page = plugins_page(user, qtbot, mainwin)
    listbox = page._listbox
    user.click(listbox.viewport(), listbox.visualItemRect(plugin_item(page, 'Synthetic Plugin')).center())

    [info] = page.findChildren(InfoWidget)
    assert 'Looks up albums, quickly' in info.text()


def test_plugin_named_with_a_comma_lets_puddletag_start(mainwin, user, qtbot, restart, new_process):
    # plugins.txt: "**name**: The name of the plugin as it'll be displayed
    # to a puddletag user." The plugin is synthetic.
    write_plugin('comma_plugin', 'Comma, Plugin', source_code('Comma Source'))
    tick('comma_plugin')

    new = start_again(restart, new_process)

    dialog, page = plugins_page(type(user)(qtbot, new), qtbot, new)
    assert ('Comma, Plugin', True) in listed_plugins(page)
    assert 'Comma Source' in listed_sources()


@pytest.mark.parametrize('key', INFO_KEYS)
def test_plugin_missing_an_info_key_is_logged(key, incomplete_plugin, mainwin, user, qtbot, caplog):
    # plugins.txt: "Your plugin will not be loaded unless all this
    # information is present." and "A plugin that can't be loaded is left
    # out, and the reason is written to puddletag's log." The plugin is
    # synthetic.
    assert startup_errors(caplog, 'setup', logging.WARNING) == [
        f"Plugin incomplete_plugin not loaded: its info file lacks {key}"]


# Tag sources that can't start.

RAISING_CODE = '''\
class Raising:
    group_by = ['album']
    name = 'Raising Source'

    def __init__(self):
        raise RuntimeError('synthetic constructor failure')


class Good:
    group_by = ['album']
    name = 'Good Source'

    def search(self, album, artists):
        return []


tagsources = [Raising, Good]
'''

NO_DEFAULT_CODE = '''\
from puddlestuff.constants import TEXT


class NoDefault:
    group_by = ['album']
    name = 'No Default Source'

    def __init__(self):
        self.preferences = [['API Key', TEXT]]

    def applyPrefs(self, args):
        self.prefs = args

    def search(self, album, artists):
        return []


tagsources = [NoDefault]
'''


@pytest.fixture
def no_default_plugin(clean_profile):
    """A ticked plugin whose source has a TEXT preference without a
    default, in the user's folder before mainwin builds the window."""
    write_plugin('no_default_plugin', 'No Default Plugin', NO_DEFAULT_CODE)
    tick('no_default_plugin')


@pytest.mark.xfail(strict=True, reason="a tag source whose constructor raises stops puddletag from starting")
def test_tag_source_that_fails_to_start_is_left_out(mainwin, user, qtbot, restart, new_process, caplog):
    # plugins.txt: "A tag source of a plugin that can't be started is left
    # out too, and the reason is shown in the **Tag Sources** window and
    # written to puddletag's log." The plugin is synthetic.
    write_plugin('raising_plugin', 'Raising Plugin', RAISING_CODE)
    tick('raising_plugin')

    start_again(restart, new_process)

    assert 'Good Source' in listed_sources()
    assert 'Raising Source' not in listed_sources()
    assert startup_errors(caplog, 'call') == ["Couldn't load tag source Raising Source"]
    assert tag_sources_window().label.text() == ("Couldn't load tag source Raising Source: "
                                                 "synthetic constructor failure")


@pytest.mark.xfail(strict=True, reason="a tag source whose saved preferences can't be applied is skipped silently")
def test_preferences_that_fail_to_apply_are_logged(no_default_plugin, mainwin, user, qtbot, caplog):
    # The docs are silent; this is what puddletag does. The plugin is
    # synthetic: a TEXT preference without the default that the example
    # plugin says is required.
    assert 'No Default Source' in listed_sources()
    assert startup_errors(caplog, 'setup') == ["Couldn't apply the preferences of tag source No Default Source"]
