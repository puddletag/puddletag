"""The Help menu, used as a user uses it: Online Documentation, GitHub
project and Report a problem hand their address to the desktop's
browser (caught before it gets there), and About puddletag and About Qt
open their windows, which OK closes. No files are loaded.
"""
import importlib.metadata
import platform
import re
import sys
import urllib.parse
from pathlib import Path

import pytest
from PyQt6.QtCore import PYQT_VERSION_STR, Qt, QTimer, QUrl, qVersion
from PyQt6.QtGui import QTextDocument
from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QPushButton, QTabWidget

from puddlestuff import changeset, version_string
from puddlestuff.about import AboutPuddletag

pytestmark = pytest.mark.ui

Key = Qt.Key

REPO = Path(__file__).resolve().parents[2]

# The real QDialog.exec, saved before the dialog guard stands in for it:
# test modules are imported before any test runs.
REAL_EXEC = QDialog.exec


@pytest.fixture
def opened(monkeypatch):
    """The addresses handed to the desktop to open in the browser, caught
    there. The network guard can't see them: Qt hands them to the desktop
    itself, not through Python's sockets."""
    urls = []

    def open_url(url):
        urls.append(url.toString(QUrl.ComponentFormattingOption.FullyEncoded))
        return True

    monkeypatch.setattr('puddlestuff.puddletag.QDesktopServices.openUrl', open_url)
    return urls


def exec_for_real(monkeypatch):
    """About puddletag is a window to read, not a question: it runs for
    real, so the test sees it open and closes it with OK as a user does.
    (The dialog guard otherwise stands in for QDialog.exec.)"""
    monkeypatch.setattr(QDialog, 'exec', lambda self: REAL_EXEC(self))


def while_open(user, look):
    """Handles the modal window the next click opens, from inside the
    event loop it runs (the click returns only once it's closed): what
    look(window) returns goes in the returned list, then OK closes the
    window, as a user clicks it. Polls for 2 seconds. look should only
    read: the window is closed whatever happens, so a failing test doesn't
    hang."""
    shown = []

    def pick(tries=200):
        window = QApplication.activeModalWidget()
        if window is None:
            if tries:
                QTimer.singleShot(10, lambda: pick(tries - 1))
            return
        try:
            shown.append(look(window))
        finally:
            buttons = [b for b in window.findChildren(QPushButton) if b.isVisible() and b.text() == 'OK']
            if buttons:
                user.click(buttons[0])
            else:
                window.reject()

    QTimer.singleShot(0, pick)
    return shown


def plain(html):
    """Rich text as the window shows it, without its markup."""
    document = QTextDocument()
    document.setHtml(html)
    return document.toPlainText()


def about_puddletag(window):
    """What the About puddletag window shows: its title, its heading's
    words, and each tab's name and text, in tab order."""
    tabs = window.findChild(QTabWidget)
    [heading] = [label for label in window.findChildren(QLabel)
                 if label.text() and not tabs.isAncestorOf(label)]
    return {'heading': plain(heading.text()).split(),
            'modal': QApplication.activeModalWidget() is window,
            'tabs': {tabs.tabText(i): plain(tabs.widget(i).findChild(QLabel).text())
                     for i in range(tabs.count())},
            'title': window.windowTitle(),
            'visible': window.isVisible()}


def libraries():
    """Python, PyQt and Qt, then each library requirements.in names, with
    the version installed, by lower-case name."""
    names = [re.split(r'[\s!;<=>\[~]', line, maxsplit=1)[0]
             for line in (REPO / 'requirements.in').read_text().splitlines()
             if line.strip() and not line.startswith('#')]
    return {'pyqt': PYQT_VERSION_STR, 'python': platform.python_version(), 'qt': qVersion(),
            **{name.lower(): importlib.metadata.version(name) for name in names if name != 'PyQt6'}}


def by_name(lines):
    """'Name: value' lines as a dict by lower-case name."""
    return {name.lower(): value for name, value in (line.split(': ', 1) for line in lines)}


def test_online_documentation_opens_the_docs(mainwin, qtbot, user, opened):
    # index.txt: "But check out the :doc:`documentation <docs>` first." The
    # docs page (docs.txt) is built to docs.html on docs.puddletag.net
    # (docs/CNAME).
    user.click_menu('Online &Documentation')

    assert opened == ['https://docs.puddletag.net/docs.html']


def test_github_project_opens_the_project_page(mainwin, qtbot, user, opened):
    # index.txt: "Report any bugs or feedback on the issue tracker hosted at
    # Github <https://github.com/puddletag/puddletag/issues>" (the project
    # is its parent page).
    user.click_menu('&GitHub project')

    assert opened == ['https://github.com/puddletag/puddletag']


def test_report_a_problem_opens_a_filled_in_bug_report(mainwin, qtbot, user, opened, monkeypatch):
    # index.txt: "Report any bugs or feedback on the issue tracker hosted at
    # Github <https://github.com/puddletag/puddletag/issues>."
    # bug_report.yaml's system field: "This section is automatically filled
    # when using the "Report a problem" function in the "Help" menu of the
    # application." (Puddletag, OS, Display Server, Desktop Environment,
    # Python, PyQt).
    # Synthetic: a desktop the test names, so the line doesn't depend on the
    # machine.
    monkeypatch.setenv('XDG_CURRENT_DESKTOP', 'GNOME')

    user.click_menu('&Report a problem')

    [url] = opened
    parts = urllib.parse.urlsplit(url)
    assert (parts.scheme, parts.netloc, parts.path) == ('https', 'github.com', '/puddletag/puddletag/issues/new')
    query = urllib.parse.parse_qs(parts.query, strict_parsing=True)
    assert sorted(query) == ['labels', 'system', 'template']
    assert query['labels'] == ['bug']
    [template] = query['template']
    assert '- id: system' in (REPO / '.github' / 'ISSUE_TEMPLATE' / template).read_text()
    [system] = query['system']
    lines = system.splitlines()
    release = version_string + (f' ({changeset})' if changeset else '')
    assert lines[:6] == [f'Puddletag: {release}',
                         f'OS: {platform.freedesktop_os_release()["PRETTY_NAME"]}',
                         'Display Server: offscreen',  # the tests' platform (tests/conftest.py)
                         'Desktop Environment: GNOME',
                         f'Python: {platform.python_version()}',
                         f'PyQt: {PYQT_VERSION_STR}']
    others = libraries()
    del others['pyqt'], others['python']
    assert by_name(lines[6:]) == others


def test_about_puddletag_shows_the_version_and_ok_closes_it(mainwin, qtbot, user, monkeypatch):
    # about.txt: "About puddletag" heading. The docs are silent on the
    # window itself.
    exec_for_real(monkeypatch)
    shown = while_open(user, about_puddletag)
    user.click_menu('About puddletag')

    [window] = shown
    assert window['title'] == 'About puddletag'
    assert window['heading'] == ['puddletag', version_string] + (['Changeset', changeset] if changeset else [])
    assert list(window['tabs']) == ['&About', '&Thanks', '&Libraries']  # tab order
    assert window['modal'] and window['visible']
    assert QApplication.activeModalWidget() is None
    assert not any(w.isVisible() for w in mainwin.findChildren(AboutPuddletag))


def test_about_puddletag_lists_the_libraries(mainwin, qtbot, user, monkeypatch):
    # The docs are silent: the Libraries tab lists Python, PyQt, Qt and
    # every library requirements.in names, as the problem report does.
    exec_for_real(monkeypatch)
    shown = while_open(user, about_puddletag)
    user.click_menu('About puddletag')

    [window] = shown
    assert by_name(window['tabs']['&Libraries'].splitlines()) == libraries()


def test_about_puddletag_says_when_a_library_is_not_installed(mainwin, qtbot, user, monkeypatch):
    # The docs are silent. requirements.in lists pyacoustid under "extra /
    # tag sources", so it is optional. Synthetic: pyacoustid hidden.
    expected = libraries()
    expected['pyacoustid'] = 'not installed'
    installed = importlib.metadata.version

    def version(name):
        if name == 'pyacoustid':
            raise importlib.metadata.PackageNotFoundError(name)
        return installed(name)

    monkeypatch.setattr(importlib.metadata, 'version', version)
    monkeypatch.setitem(sys.modules, 'pyacoustid', None)  # import fails too
    exec_for_real(monkeypatch)
    shown = while_open(user, about_puddletag)
    user.click_menu('About puddletag')

    [window] = shown
    assert by_name(window['tabs']['&Libraries'].splitlines()) == expected


def test_about_qt_shows_the_qt_version_and_ok_closes_it(mainwin, qtbot, user):
    # The docs are silent: Qt's own box, which says which Qt runs.
    shown = while_open(user, lambda box: {'modal': QApplication.activeModalWidget() is box,
                                          'text': box.text(), 'title': box.windowTitle()})
    user.click_menu('About Qt')

    [box] = shown
    assert box['title'] == 'About Qt'
    assert f'This program uses Qt version {qVersion()}.' in box['text']
    assert box['modal']
    assert QApplication.activeModalWidget() is None


@pytest.mark.xfail(strict=True, reason="The About tab's formats, website and license address are older than the docs")
def test_about_tab_matches_the_docs(mainwin, qtbot, user, monkeypatch):
    # index.txt: "Supported formats: ID3v1, ID3v2 (mp3, and in AIFF, DSF
    # and DSDIFF files), MP4 (mp4, m4a, etc.), VorbisComments (ogg, opus,
    # flac), APEv2 (Musepack mpc, Monkey's Audio ape, WavPack wv) and
    # Windows Media (wma)." and "puddletag is licensed under the GPLv3,
    # which you can find in its entirety at
    # http://www.gnu.org/licenses/gpl-3.0.html." The site the docs are
    # built to is docs.puddletag.net (docs/CNAME).
    exec_for_real(monkeypatch)
    shown = while_open(user, about_puddletag)
    user.click_menu('About puddletag')

    [window] = shown
    text = window['tabs']['&About']
    assert ("Supported formats: ID3v1, ID3v2 (mp3, and in AIFF, DSF and DSDIFF files), MP4 (mp4, m4a, "
            "etc.), VorbisComments (ogg, opus, flac), APEv2 (Musepack mpc, Monkey's Audio ape, "
            "WavPack wv) and Windows Media (wma).") in text
    assert 'https://docs.puddletag.net' in text
    assert 'sourceforge' not in text
    assert 'http://www.gnu.org/licenses/gpl-3.0.html' in text


@pytest.mark.xfail(strict=True, reason='Links in the About window open nothing')
def test_about_tab_link_opens_in_the_browser(mainwin, qtbot, user, monkeypatch, opened):
    # The About tab says "Visit the puddletag website (<address>)": the
    # address is shown as a link, so following it opens it.
    exec_for_real(monkeypatch)

    def follow_first_link(window):
        label = window.findChild(QTabWidget).widget(0).findChild(QLabel)
        user.activate(window)
        label.setFocus()
        qtbot.waitUntil(label.hasFocus)
        user.press(Key.Key_Tab)
        link = label.selectedText()
        user.press(Key.Key_Return)
        return link

    shown = while_open(user, follow_first_link)
    user.click_menu('About puddletag')

    [link] = shown
    assert opened == [link]


@pytest.mark.xfail(strict=True, reason='The Thanks tab differs from about.txt and shows Markdown asterisks')
def test_thanks_tab_matches_the_docs(mainwin, qtbot, user, monkeypatch):
    # about.txt's "Thank yous" and "Translators" sections, as the page
    # shows them: in the page's order, bold without the asterisks.
    about_txt = [
        'First off, a big thanks to Evan Devetzis for working tirelessly in helping me make puddletag '
        'better by contributing many, many awesome ideas and for being a great bug hunter.',
        "To the writers of the libraries puddletag depends on (without which I'll probably still be "
        'writing an id3 reader).',
        'Paul McGuire for PyParsing and for being extraordinarily helpful.',
        'Michael Urman and Joe Wreschnig for Mutagen (It. Is. Awesome).',
        'Nokia, Phil Thomson and all parties responsible for PyQt4.',
        'Michael Foord and Nicola Larosa for ConfigObj (seriously, they should replace ConfigParser with this).',
        'The Oxygen team for the Oxygen icons.',
        "And for those who've contributed, the people whose code I stole, those who helped me out on "
        'discussion boards and to open-source creators, Thanks a bunch.',
        'Thank you to the translators below for their contributions.',
        'Dutch (Nederlands) by Fabian Bakkum.',
        'French by Raphaël Rochet.',
        'German by Ralf Sarholz.',
        'Portuguese (Brazilian) by Alan Gomes.',
        'Russian by Viktor Yu. Kovalskiy.',
        'Czech by Pavel Fric.',
        'Spanish by José Vidal',
        'Swedish by Åke Engelbrektson',
    ]
    exec_for_real(monkeypatch)
    shown = while_open(user, about_puddletag)
    user.click_menu('About puddletag')

    [window] = shown
    text = window['tabs']['&Thanks']
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    # The tab may also show the two section headings as lines of their own.
    assert [line for line in lines if line in about_txt] == about_txt
    assert text.count('Evan Devetzis') == 1
    assert '**' not in text
