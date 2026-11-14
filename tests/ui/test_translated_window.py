"""puddletag shown in another language. The Russian translation is the
one puddletag ships; the others are synthetic translators standing in
for a .qm file, installed as the launcher installs the chosen language.
translate.txt: "A translation file will be created in
puddlestuff/translations/puddletag_your_locale.ts. Open this file in Qt
Linguist and translate to your heart's content." Synthetic files.
"""
import pytest
from PyQt6.QtCore import Qt, QTranslator
from PyQt6.QtWidgets import QApplication

from puddlestuff import audioinfo
from puddlestuff.puddleobjects import ProgressWin
from test_bundled_plugins import load, tick

pytestmark = pytest.mark.ui


class SyntheticTranslation(QTranslator):
    """A translation that knows only these {(context, source): text}."""

    def __init__(self, texts):
        super().__init__()
        self._texts = texts

    def translate(self, context, source, disambiguation=None, n=-1):
        return self._texts.get((context, source))


def progress_labels(mainwin):
    """The texts of the progress windows the main window has shown."""
    return [win.label.text() for win in mainwin.findChildren(ProgressWin)]


def menu_titles(window):
    return [action.text() for action in window.menuBar().actions() if action.menu()]


def commands(window):
    """The texts of the commands in every menu of the menu bar."""
    return {action.text() for menu in window.menuBar().actions() if menu.menu()
            for action in menu.menu().actions() if not action.isSeparator()}


@pytest.fixture
def russian():
    translator = QTranslator()
    assert translator.load('translations:puddletag_ru_RU.qm')
    QApplication.installTranslator(translator)
    yield
    QApplication.removeTranslator(translator)


def test_russian_loading_text_keeps_its_space(mainwin, russian, make_audio, tmp_path, qtbot):
    # #588: "There must be a space after translated word": the progress
    # window shows the Russian for "Loading " followed by the count.
    for name in ('01.mp3', '02.mp3', '03.mp3'):
        make_audio(name, tmp_path, title='Title')
    mainwin.openDir(str(tmp_path), False)
    qtbot.waitUntil(lambda: mainwin._table.model().rowCount() == 3)
    [label] = [text for text in progress_labels(mainwin) if text.startswith('Загрузка')]
    assert label.startswith('Загрузка ')
    assert [audio['title'] for audio in mainwin._table.model().taginfo] == [['Title']] * 3


# plugins.txt: "**Plugins->Dupe highlight**", "**Plugins->Add 2 seconds to
# modified time** (Ctrl+M)" name the commands.
PLUGIN_COMMANDS = {
    '&Convert to UTF-8': 'Synthetic convert to UTF-8',
    '&Update to ID3v2.4': 'Synthetic update to ID3v2.4',
    'Add 2 seconds to modified time': 'Synthetic add 2 seconds',
    'Dupe highlight': 'Synthetic dupe highlight',
    'Export tags': 'Synthetic export tags',
    'Save Extended': 'Synthetic save extended',
    'Show all fields': 'Synthetic show all fields',
}


@pytest.fixture
def plugins_in_another_language(clean_profile, monkeypatch):
    """Every bundled plugin ticked, and a translation of the Plugins menu
    and of their commands installed before the window is built. Name it
    before mainwin in a test's arguments."""
    tick(monkeypatch, 'dupe_fields', 'extended_tags', 'id3_tools', 'modified_time', 'save_tags',
         'view_all_fields')
    texts = {('Menus', source): text for source, text in PLUGIN_COMMANDS.items()}
    texts['Menus', '&Plugins'] = 'Synthetic plugins'
    translator = SyntheticTranslation(texts)
    QApplication.installTranslator(translator)
    yield
    QApplication.removeTranslator(translator)


@pytest.mark.xfail(strict=True, reason="the Plugins menu's title is never translated")
def test_plugins_menu_title_is_translated(plugins_in_another_language, mainwin):
    # translate.txt: "Open this file in Qt Linguist and translate to your
    # heart's content." Like the menu bar's other titles, the Plugins
    # menu's is translated (synthetic translation).
    assert 'Synthetic plugins' in menu_titles(mainwin)
    assert '&Plugins' not in menu_titles(mainwin)


@pytest.mark.xfail(strict=True, reason="the bundled plugins' command names are never translated")
def test_plugin_commands_are_translated(plugins_in_another_language, mainwin):
    # plugins.txt names the commands under the Plugins menu, e.g.
    # "**Plugins->Dupe highlight**"; like every other menu command, they
    # are translated (synthetic translation).
    assert set(PLUGIN_COMMANDS.values()) <= commands(mainwin)
    assert not set(PLUGIN_COMMANDS) & commands(mainwin)


@pytest.mark.xfail(strict=True, reason='the tag removal text is filled in before it is translated')
def test_tag_removal_progress_is_translated(mainwin, user, qtbot, make_audio, tmp_path):
    # menus.txt, Tag Tools: "Deleting 'official' tags can be undone"; the
    # progress window of a removal is shown in the chosen language
    # (synthetic translation).
    paths = [make_audio(f'0{n}.mp3', tmp_path / 'music', title='Title', artist='Artist')
             for n in range(1, 4)]
    load(mainwin, user, qtbot, tmp_path / 'music', 3)
    translator = SyntheticTranslation({('Tag Tools', 'Removing %s tag: '): 'Synthetic removing %s: '})
    QApplication.installTranslator(translator)
    try:
        user.click_menu('Remove All &ID3 Tags')
        qtbot.waitUntil(lambda: all(audioinfo.usertags(audioinfo.Tag(str(p))) == {} for p in paths))
        assert any(text.startswith('Synthetic removing ID3: ') for text in progress_labels(mainwin))
    finally:
        QApplication.removeTranslator(translator)


@pytest.mark.xfail(strict=True, reason='the Help menu has no Alt letter')
def test_help_menu_has_an_alt_letter(mainwin, user, qtbot):
    # Every other menu of the menu bar has an Alt letter; Help gets &Help,
    # so Alt+H opens it.
    [help] = [a for a in mainwin.menuBar().actions() if a.menu() and a.text() in ('Help', '&Help')]
    user.activate()
    user.press(Qt.Key.Key_H, Qt.KeyboardModifier.AltModifier)
    try:
        qtbot.waitUntil(help.menu().isVisible)
    finally:
        help.menu().hide()
