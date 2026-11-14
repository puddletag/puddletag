"""Report a problem (menus.txt, Help): the report puddletag fills in, shown
for review before it goes to GitHub's issue form
(.github/ISSUE_TEMPLATE/bug_report.yaml), as a user opens, edits, copies
and sends it. The browser is caught before it gets the address.
"""
import platform
import sys
import types
import urllib.parse

import pytest
from PyQt6.QtCore import PYQT_VERSION_STR, Qt, QUrl
from PyQt6.QtWidgets import QApplication, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton

from puddlestuff import changeset, version_string
from puddlestuff.bugreport import MAX_URL_LENGTH, STEPS_HEADER, ReviewWindow, drop_oldest_step, trim_traceback

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier

FORM = 'https://github.com/puddletag/puddletag/issues/new'


@pytest.fixture
def opened(monkeypatch):
    """The addresses handed to the desktop to open in the browser, caught
    there (as in test_help_menu.py)."""
    urls = []

    def open_url(url):
        urls.append(url.toString(QUrl.ComponentFormattingOption.FullyEncoded))
        return True

    monkeypatch.setattr('puddlestuff.puddletag.QDesktopServices.openUrl', open_url)
    return urls


def review_window(qtbot):
    """The review window, once it's open."""
    windows = lambda: [w for w in QApplication.topLevelWidgets() if isinstance(w, ReviewWindow) and w.isVisible()]
    qtbot.waitUntil(lambda: len(windows()) == 1)
    return windows()[0]


def box(window, label):
    """The review window's box under this label (the form's labels)."""
    return window.field(label)


def button(window, text):
    [found] = [b for b in window.findChildren(QPushButton) if b.isVisible() and b.text() == text]
    return found


def fields(url):
    """The form's fields in an issue address, by id."""
    parts = urllib.parse.urlsplit(url)
    assert f'{parts.scheme}://{parts.netloc}{parts.path}' == FORM
    return {name: value for name, [value] in urllib.parse.parse_qs(parts.query, strict_parsing=True).items()}


def open_review(mainwin, qtbot, user):
    """Help > Report a problem, with the review window active."""
    user.click_menu('&Report a problem')
    window = review_window(qtbot)
    user.activate(window)
    return window


def test_report_a_problem_shows_the_report_for_review(mainwin, qtbot, user, opened):
    # menus.txt, Help: "Opens a bug report for puddletag's issue tracker on
    # GitHub, filled in with your system ... Check and edit the text, then
    # click Open on GitHub to finish the issue in your browser ... Nothing
    # is sent until you submit the issue on GitHub."
    user.click_menu('&Report a problem')
    window = review_window(qtbot)

    release = version_string + (f' ({changeset})' if changeset else '')
    assert window.windowTitle() == 'Report a problem'
    assert box(window, 'Title').text() == ''
    assert box(window, 'Current Behavior').toPlainText() == ''
    assert box(window, 'Information about your system').toPlainText().splitlines()[0] == f'Puddletag: {release}'
    assert opened == []

    user.click(button(window, 'Open on GitHub'))

    [url] = opened
    assert sorted(fields(url)) == ['labels', 'system', 'template']
    assert not window.isVisible()


def test_text_typed_in_the_review_goes_to_github(mainwin, qtbot, user, opened):
    # menus.txt, Help: "Check and edit the text, then click Open on GitHub
    # to finish the issue in your browser."
    window = open_review(mainwin, qtbot, user)

    user.click(box(window, 'Current Behavior'))
    user.type('Synthetic: the table stays empty')
    user.click(button(window, 'Open on GitHub'))

    [url] = opened
    assert fields(url)['current'] == 'Synthetic: the table stays empty'


@pytest.mark.parametrize('close', ['click Cancel', 'press Escape'])
def test_cancel_sends_nothing(mainwin, qtbot, user, opened, close):
    # menus.txt, Help: "Nothing is sent until you submit the issue on
    # GitHub." Synthetic: a user who looks at the report and thinks better
    # of it.
    window = open_review(mainwin, qtbot, user)

    if close == 'click Cancel':
        user.click(button(window, 'Cancel'))
    else:
        user.press(Key.Key_Escape)

    assert opened == []
    assert not window.isVisible()


def test_copy_puts_the_report_on_the_clipboard(mainwin, qtbot, user, opened):
    # menus.txt, Help: "Copy puts the text on the clipboard."
    window = open_review(mainwin, qtbot, user)

    user.click(box(window, 'Current Behavior'))
    user.type('Synthetic text')
    user.click(button(window, '&Copy'))

    system = box(window, 'Information about your system').toPlainText()
    assert QApplication.clipboard().text() == ('### Current Behavior\n\nSynthetic text\n\n'
                                               '### Information about your system\n\n' + system)
    assert window.isVisible()
    assert opened == []


def test_report_too_long_for_the_address_goes_through_the_clipboard(mainwin, qtbot, user, opened, dialogs):
    # Synthetic: a user pastes a long text. GitHub documents no length for
    # the address (a longer one returns 414 URI Too Long); the limit is the
    # 7500 characters VS Code's issue reporter uses.
    window = open_review(mainwin, qtbot, user)
    QApplication.clipboard().setText('x' * 8000)

    user.click(box(window, 'Current Behavior'))
    user.press(Key.Key_V, Ctrl)
    dialogs.answer('QMessageBox.information', QMessageBox.StandardButton.Ok)
    user.click(button(window, 'Open on GitHub'))

    [url] = opened
    assert len(url) <= MAX_URL_LENGTH
    assert fields(url)['current'] == ('The report was too long for the address, so puddletag put it on the '
                                      'clipboard: paste it here.')
    assert 'x' * 8000 in QApplication.clipboard().text()
    [(name, args, _)] = dialogs.calls
    assert (name, args[1:]) == ('QMessageBox.information',
                                ('puddletag', 'The report is too long to send in the address, so puddletag put '
                                              'it on the clipboard: paste it into the issue.'))


def load(mainwin, qtbot, user, paths):
    """Opens the files' folder, with the window active and the File-View
    focused."""
    mainwin.openDir(str(paths[0].parent), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == len(paths))
    user.activate()
    table.setFocus()
    return table


def select(user, rows):
    """Clicks the first row's Title cell and Shift-clicks the last row's."""
    user.click_cell(user.cell(rows[0], 'title'))
    if len(rows) > 1:
        user.click_cell(user.cell(rows[-1], 'title'), Shift)


def steps_text(window):
    return box(window, 'Steps To Reproduce').toPlainText()


def test_report_lists_the_steps_that_led_there(mainwin, make_audio, tmp_path, qtbot, user, opened):
    # menus.txt, Help: "filled in with ... the last steps you took in
    # puddletag: the last 20 commands you ran, windows you opened and
    # folders you loaded". Synthetic: load two files, remove their tags
    # with Edit > Remove Tag (Ctrl+R), then report. The report says what
    # the user did, in order; selecting rows with the mouse isn't a command.
    music = tmp_path / 'music'
    paths = [make_audio(f'0{i}.mp3', music, artist=f'Artist {i}', title=f'Title {i}') for i in (1, 2)]
    load(mainwin, qtbot, user, paths)
    select(user, [0, 1])
    user.press(Key.Key_R, Ctrl)
    user.activate()

    window = open_review(mainwin, qtbot, user)

    expected = ('puddletag recorded these steps, oldest first:\n'
                '1. Loaded 2 files (mp3) from 1 folder\n'
                '2. Remove Tag (removeTags)')
    assert steps_text(window) == expected
    user.click(button(window, 'Open on GitHub'))
    [url] = opened
    assert fields(url)['reproduce'] == expected


def test_steps_keep_the_last_twenty(mainwin, make_audio, tmp_path, qtbot, user):
    # menus.txt, Help: "the last 20 commands you ran". Synthetic: 21 steps
    # (the load, then Select All 20 times); the report keeps the last 20,
    # so the load is gone.
    music = tmp_path / 'music'
    paths = [make_audio('01.mp3', music, artist='Artist 1', title='Title 1')]
    load(mainwin, qtbot, user, paths)
    for _ in range(20):
        user.press(Key.Key_A, Ctrl)

    window = open_review(mainwin, qtbot, user)

    assert steps_text(window).splitlines() == (
        ['puddletag recorded these steps, oldest first:']
        + [f'{n}. Select All (selectAll)' for n in range(1, 21)])


def test_steps_leave_out_tags_and_names(mainwin, make_audio, tmp_path, qtbot, user):
    # menus.txt, Help: "folders you loaded (how many files, not their names
    # or tags)". Synthetic: a private folder, file name and title; the
    # report says how many files were loaded, never their names or tags.
    music = tmp_path / 'Synthetic Private Folder'
    paths = [make_audio('Synthetic Name.mp3', music, artist='Artist 1', title='Title 1')]
    table = load(mainwin, qtbot, user, paths)
    index = user.cell(0, 'title')
    user.double_click_cell(index)
    table.indexWidget(index).selectAll()
    user.type('Synthetic Secret Title')
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: table.model().data(index) == 'Synthetic Secret Title')
    user.activate()

    window = open_review(mainwin, qtbot, user)

    steps = steps_text(window)
    for private in ('Synthetic Private Folder', 'Synthetic Name', 'Synthetic Secret Title'):
        assert private not in steps
    assert steps.splitlines()[1] == '1. Loaded 1 file (mp3) from 1 folder'


def test_a_window_opened_is_a_step(mainwin, qtbot, user):
    # menus.txt, Help: "windows you opened". Synthetic: the Preferences
    # window opened and closed, then the report.
    window = user.open_preferences()
    user.close_preferences(window, 'Cancel')

    review = open_review(mainwin, qtbot, user)

    assert steps_text(review).splitlines()[1:] == ['1. Preferences (openPrefs)', '2. Opened window: puddletag settings']


def system_lines(mainwin, qtbot, user):
    """Help > Report a problem: the system field's lines by name, then
    Cancel."""
    window = open_review(mainwin, qtbot, user)
    lines = box(window, 'Information about your system').toPlainText().splitlines()
    user.click(button(window, 'Cancel'))
    return dict(line.split(': ', 1) for line in lines)


@pytest.mark.parametrize('release, shown', [
    ({'NAME': 'Synth Linux', 'VERSION': '9 (Sandy)'}, 'Synth Linux 9 (Sandy)'),
    ({'ID': 'synth', 'VERSION_ID': '9'}, 'synth 9'),
    ({'ID': 'synth', 'VERSION_CODENAME': 'sandy'}, 'synth sandy'),
    ({}, 'Linux'),
])
def test_os_line_without_a_pretty_name(mainwin, qtbot, user, monkeypatch, release, shown):
    # menus.txt, Help: "filled in with your system (puddletag's version, your
    # OS, display server and desktop, ...)"; bug_report.yaml's example is
    # "OS: Ubuntu 20.04". Synthetic: os-release files without PRETTY_NAME.
    with monkeypatch.context() as m:
        m.setitem(sys.modules, 'distro', None)
        m.setattr(platform, 'system', lambda: 'Linux')
        m.setattr(platform, 'freedesktop_os_release', lambda: release)
        lines = system_lines(mainwin, qtbot, user)

    assert lines['OS'] == shown


def test_os_line_from_the_distro_package(mainwin, qtbot, user, monkeypatch):
    # menus.txt, Help: "filled in with your system (puddletag's version, your
    # OS, display server and desktop, ...)"; bug_report.yaml's example is
    # "OS: Ubuntu 20.04". Synthetic: a fake distro package.
    distro = types.SimpleNamespace(name=lambda pretty=False: 'Synth Linux 9 (Sandy)' if pretty else 'Synth Linux')
    with monkeypatch.context() as m:
        m.setitem(sys.modules, 'distro', distro)
        m.setattr(platform, 'system', lambda: 'Linux')
        lines = system_lines(mainwin, qtbot, user)

    assert lines['OS'] == 'Synth Linux 9 (Sandy)'


@pytest.mark.parametrize('system, shown', [
    ('Darwin', 'macOS 15.1'),
    ('FreeBSD', 'FreeBSD 14.1-RELEASE FreeBSD 14.1-RELEASE GENERIC'),
    ('Windows', 'Windows 11'),
])
def test_os_line_on_other_systems(mainwin, qtbot, user, monkeypatch, system, shown):
    # menus.txt, Help: "filled in with your system (puddletag's version, your
    # OS, display server and desktop, ...)"; bug_report.yaml's example is
    # "OS: Ubuntu 20.04". Synthetic: the platform module reports another
    # system.
    with monkeypatch.context() as m:
        m.setattr(platform, 'system', lambda: system)
        m.setattr(platform, 'win32_ver', lambda: ('11', '10.0.26100', 'SP0', 'Multiprocessor Free'))
        m.setattr(platform, 'mac_ver', lambda: ('15.1', ('', '', ''), 'arm64'))
        m.setattr(platform, 'release', lambda: '14.1-RELEASE')
        m.setattr(platform, 'version', lambda: 'FreeBSD 14.1-RELEASE GENERIC')
        lines = system_lines(mainwin, qtbot, user)

    assert lines['OS'] == shown


@pytest.mark.parametrize('name, env, shown', [
    ('', {}, 'unknown'),
    ('wayland', {}, 'wayland'),
    ('xcb', {}, 'x11'),
    ('xcb', {'WAYLAND_DISPLAY': 'wayland-0'}, 'xwayland'),
    ('xcb', {'XDG_SESSION_TYPE': 'wayland'}, 'xwayland'),
])
def test_display_server_line(mainwin, qtbot, user, monkeypatch, name, env, shown):
    # menus.txt, Help: "filled in with your system (puddletag's version, your
    # OS, display server and desktop, ...)"; bug_report.yaml's example is
    # "Display Server: x11". Synthetic: Qt's platform name and the session's
    # environment.
    with monkeypatch.context() as m:
        m.delenv('WAYLAND_DISPLAY', raising=False)
        m.delenv('XDG_SESSION_TYPE', raising=False)
        for variable, value in env.items():
            m.setenv(variable, value)
        m.setattr(QApplication, 'platformName', lambda *args: name)
        lines = system_lines(mainwin, qtbot, user)

    assert lines['Display Server'] == shown


def test_dropping_the_oldest_step_renumbers_the_rest():
    # menus.txt, Help: "the last 20 commands you ran, windows you opened and
    # folders you loaded". Synthetic steps; the docs are silent on how a
    # report too long for the address is shortened.
    assert drop_oldest_step(f'{STEPS_HEADER}\n1. a\n2. b\n3. c') == f'{STEPS_HEADER}\n1. b\n2. c'
    assert drop_oldest_step(f'{STEPS_HEADER}\n1. a') == ''


def test_text_that_isnt_a_traceback_is_left_whole():
    # Synthetic: the docs are silent on how a long error is shortened; text
    # without a traceback has nothing to trim.
    assert trim_traceback('ValueError: synthetic error\n', 1) == 'ValueError: synthetic error\n'


def test_os_line_without_os_release(mainwin, qtbot, user, monkeypatch):
    # menus.txt, Help: "filled in with your system (puddletag's version, your
    # OS, display server and desktop, ...)"; bug_report.yaml's example is
    # "OS: Ubuntu 20.04". Synthetic: a Linux system with no os-release file.
    def no_os_release():
        raise OSError('synthetic')

    with monkeypatch.context() as m:
        m.setitem(sys.modules, 'distro', None)
        m.setattr(platform, 'system', lambda: 'Linux')
        m.setattr(platform, 'freedesktop_os_release', no_os_release)
        m.setattr(platform, 'release', lambda: '6.1.0-synth')
        m.setattr(platform, 'version', lambda: '#1 SMP synthetic')
        lines = system_lines(mainwin, qtbot, user)

    assert lines['OS'] == 'Linux 6.1.0-synth #1 SMP synthetic'
