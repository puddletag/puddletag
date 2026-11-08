"""An error nothing in puddletag catches, raised where a user's command
runs (a menu, the table, a background thread), as menus.txt's "When
something goes wrong" describes it: a message with the error and its
traceback, the error in the log, and puddletag still running. The errors
are synthetic: a puddletag function replaced by one that raises.
"""
import logging
import os
import re
import subprocess
import sys
import threading
import urllib.parse
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import QApplication, QMessageBox, QPushButton, QTextEdit

from puddlestuff import about, audioinfo, errorhook
from puddlestuff.bugreport import MAX_URL_LENGTH, ReviewWindow
from puddlestuff.mainwin.tagsources import TAGSOURCE_CONFIG
from puddlestuff.puddleobjects import ProgressWin, PuddleConfig
from puddlestuff.tagmodel import TagModel

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier

SUMMARY = 'ValueError: synthetic error'


def synthetic_error(*args, **kwargs):
    raise ValueError('synthetic error')


@pytest.fixture
def error_hook(monkeypatch):
    """The hook the launcher installs at start-up; the mainwin fixture
    doesn't run the launcher. pytest-qt's own hook, set before any
    fixture, comes back at teardown. A message left open is closed."""
    monkeypatch.setattr(sys, 'excepthook', sys.excepthook)
    monkeypatch.setattr(threading, 'excepthook', threading.excepthook)
    errorhook.install(QApplication.instance())
    yield
    for window in QApplication.topLevelWidgets():
        if isinstance(window, QMessageBox) and window.isVisible():
            window.close()


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


def shown_messages():
    return [w for w in QApplication.topLevelWidgets() if isinstance(w, QMessageBox) and w.isVisible()]


def error_message(qtbot):
    """The error message, once the event loop has opened it."""
    qtbot.waitUntil(lambda: len(shown_messages()) == 1)
    [box] = shown_messages()
    return box


def button(window, text):
    [found] = [b for b in window.findChildren(QPushButton) if b.isVisible() and b.text() == text]
    return found


def errors_logged(caplog):
    return [(r.exc_info[0], str(r.exc_info[1])) for r in caplog.records
            if r.levelno == logging.ERROR and r.exc_info]


def in_file(path):
    return audioinfo.usertags(audioinfo.Tag(str(path)))


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


REPO = Path(__file__).resolve().parents[2]

INFORMATIVE = ("puddletag ran into an error it didn't expect. It keeps running, but the command that "
               "failed may have stopped part way: check the files it was working on.")


def test_error_in_a_menu_command_shows_it_and_puddletag_keeps_running(error_hook, mainwin, qtbot, user, opened,
                                                                      monkeypatch, caplog):
    # menus.txt, Help, "When something goes wrong": "If puddletag runs into
    # an error it doesn't handle, it shows the error in a message instead of
    # closing, and writes it to its log (``~/.config/puddletag/puddletag.log``).
    # **Show Details...** shows the full traceback; **Report a problem**
    # opens the report above, with the error filled in. puddletag keeps
    # running, but the command that failed may have stopped part way: check
    # the files it was working on."
    monkeypatch.setattr(about, 'AboutPuddletag', synthetic_error)

    user.click_menu('About puddletag')

    message = error_message(qtbot)
    assert message.windowTitle() == 'puddletag'
    assert message.text() == SUMMARY
    assert message.informativeText() == INFORMATIVE
    assert sorted(b.text() for b in message.buttons()) == ['&Report a problem', 'Close', 'Show Details...']
    assert message.detailedText().startswith('Traceback (most recent call last):')
    assert 'show_about' in message.detailedText()
    assert message.detailedText().rstrip().endswith(SUMMARY)
    assert errors_logged(caplog) == [(ValueError, 'synthetic error')]

    user.click(button(message, 'Close'))
    qtbot.waitUntil(lambda: not shown_messages())
    user.activate()
    user.click_menu('Online &Documentation')
    assert opened == ['https://docs.puddletag.net/docs.html']


def test_show_details_shows_the_traceback(error_hook, mainwin, qtbot, user, monkeypatch):
    # menus.txt, Help, "When something goes wrong": "**Show Details...**
    # shows the full traceback".
    monkeypatch.setattr(about, 'AboutPuddletag', synthetic_error)
    user.click_menu('About puddletag')
    message = error_message(qtbot)

    user.click(button(message, 'Show Details...'))

    [details] = [e for e in message.findChildren(QTextEdit) if e.isVisible()]
    assert details.toPlainText() == message.detailedText()


def test_escape_closes_the_message(error_hook, mainwin, qtbot, user, monkeypatch):
    # menus.txt, Help, "When something goes wrong": "it shows the error in a
    # message instead of closing". Escape closes the message (a Qt message
    # box's escape button), puddletag stays.
    monkeypatch.setattr(about, 'AboutPuddletag', synthetic_error)
    user.click_menu('About puddletag')
    message = error_message(qtbot)
    user.activate(message)

    user.press(Key.Key_Escape)

    qtbot.waitUntil(lambda: not shown_messages())
    assert mainwin.isVisible()


def test_repeated_error_shows_one_message_and_counts_the_rest(error_hook, mainwin, make_audio, tmp_path, qtbot, user,
                                                              monkeypatch, caplog):
    # menus.txt, Help, "When something goes wrong": "If more errors happen
    # while the message is open, the message counts them instead of opening
    # another; an error that keeps happening, again and again within two
    # seconds, is only written to the log until it stops."
    path = make_audio('01.mp3', tmp_path / 'music', artist='Artist 1', title='Title 1')
    table = load(mainwin, qtbot, user, [path])
    real = TagModel.data

    def failing_data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            raise ValueError('synthetic error')
        return real(self, index, role)

    monkeypatch.setattr(TagModel, 'data', failing_data)
    counted = re.compile(r"(\d+) more errors happened while this message was open; they are in the log\.$")

    def counted_in_message():
        table.viewport().update()
        qtbot.wait(50)
        return len(shown_messages()) == 1 and bool(counted.search(shown_messages()[0].informativeText()))

    qtbot.waitUntil(counted_in_message)

    [message] = shown_messages()
    assert int(counted.search(message.informativeText()).group(1)) >= 1
    assert len(errors_logged(caplog)) >= 2
    logged = len(errors_logged(caplog))

    message.close()
    qtbot.waitUntil(lambda: not shown_messages())
    for _ in range(3):
        table.viewport().update()
        qtbot.wait(100)
    assert not shown_messages()
    assert len(errors_logged(caplog)) > logged

    monkeypatch.setattr(TagModel, 'data', real)
    qtbot.wait(50)


class Clock:
    """Stands in for the time module in errorhook."""

    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now


def test_error_that_comes_back_after_two_quiet_seconds_shows_the_message_again(error_hook, mainwin, qtbot, user,
                                                                               monkeypatch, caplog):
    # menus.txt, Help, "When something goes wrong": "If more errors happen
    # while the message is open, the message counts them instead of opening
    # another; an error that keeps happening, again and again within two
    # seconds, is only written to the log until it stops." Synthetic: Help >
    # About puddletag made to raise, and a clock the test moves.
    clock = Clock()
    monkeypatch.setattr(errorhook, 'time', clock)
    monkeypatch.setattr(about, 'AboutPuddletag', synthetic_error)
    user.click_menu('About puddletag')
    error_message(qtbot).close()
    qtbot.waitUntil(lambda: not shown_messages())

    clock.now += 3
    user.click_menu('About puddletag')
    error_message(qtbot).close()
    qtbot.waitUntil(lambda: not shown_messages())

    clock.now += 1
    logged = len(errors_logged(caplog))
    user.click_menu('About puddletag')
    qtbot.waitUntil(lambda: len(errors_logged(caplog)) > logged)
    qtbot.wait(100)
    assert not shown_messages()


def test_error_that_keeps_happening_leaves_one_step_in_the_report(error_hook, mainwin, make_audio, tmp_path, qtbot,
                                                                  user, monkeypatch):
    # menus.txt, Help, "When something goes wrong": "an error that keeps
    # happening, again and again within two seconds, is only written to the
    # log until it stops", and Help: "Report a problem" lists the last steps.
    # Synthetic: the table's repaint made to raise.
    path = make_audio('01.mp3', tmp_path / 'music', artist='Artist 1', title='Title 1')
    table = load(mainwin, qtbot, user, [path])
    real = TagModel.data

    def failing_data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            raise ValueError('synthetic error')
        return real(self, index, role)

    monkeypatch.setattr(TagModel, 'data', failing_data)
    table.viewport().update()
    error_message(qtbot).close()
    qtbot.waitUntil(lambda: not shown_messages())
    for _ in range(5):
        table.viewport().update()
        qtbot.wait(100)
    monkeypatch.setattr(TagModel, 'data', real)
    qtbot.wait(50)

    user.click_menu('&Report a problem')

    assert text_of(review_window(qtbot), 'Steps To Reproduce').count('Error: ' + SUMMARY) == 1


def test_error_in_a_plugins_thread_shows_it(error_hook, mainwin, qtbot):
    # menus.txt, Help, "When something goes wrong": "If puddletag runs into
    # an error it doesn't handle, it shows the error in a message". Synthetic:
    # a thread of the test's own, as a plugin may start.
    thread = threading.Thread(target=synthetic_error)
    thread.start()
    thread.join()

    assert error_message(qtbot).text() == SUMMARY


def test_ctrl_c_is_left_to_python(mainwin, qtbot, user, monkeypatch):
    # Synthetic: Ctrl+C in the terminal is not an error to report; it goes
    # to Python's own hook (which prints it) and puddletag quits with
    # status 130, as a program stopped by Ctrl+C does.
    passed_on = []
    exits = []
    monkeypatch.setattr(sys, 'excepthook', lambda *exc: passed_on.append(exc[0]))
    monkeypatch.setattr(threading, 'excepthook', threading.excepthook)
    monkeypatch.setattr(QApplication, 'exit', lambda code=0: exits.append(code))
    errorhook.install(QApplication.instance())

    def interrupted(*args):
        raise KeyboardInterrupt

    monkeypatch.setattr(about, 'AboutPuddletag', interrupted)
    user.click_menu('About puddletag')
    qtbot.wait(100)

    assert passed_on == [KeyboardInterrupt]
    assert exits == [130]
    assert not shown_messages()


# The error report, end to end

FORM = 'https://github.com/puddletag/puddletag/issues/new'


def review_window(qtbot):
    """The review window, once it's open."""
    windows = lambda: [w for w in QApplication.topLevelWidgets() if isinstance(w, ReviewWindow) and w.isVisible()]
    qtbot.waitUntil(lambda: len(windows()) == 1)
    return windows()[0]


def box(window, label):
    """The review window's box under this label (the form's labels)."""
    return window.field(label)


def text_of(window, label):
    widget = box(window, label)
    return widget.text() if label == 'Title' else widget.toPlainText()


def fields(url):
    """The form's fields in an issue address, by id."""
    parts = urllib.parse.urlsplit(url)
    assert f'{parts.scheme}://{parts.netloc}{parts.path}' == FORM
    return {name: value for name, [value] in urllib.parse.parse_qs(parts.query, strict_parsing=True).items()}


def frames(text):
    """The 'File ...' lines of a traceback, one per frame."""
    return [line for line in text.splitlines() if line.startswith('  File ')]


def raising(message):
    """A function that raises ValueError(message). The message is built by
    the test, not written in the raise line: a traceback quotes its source."""

    def raise_it(*args, **kwargs):
        raise ValueError(message)

    return raise_it


def report_from_message(qtbot, user):
    """Clicks Report a problem in the error message; returns the review window
    and the traceback the message showed."""
    message = error_message(qtbot)
    details = message.detailedText()
    user.click(button(message, '&Report a problem'))
    qtbot.waitUntil(lambda: not shown_messages())
    return review_window(qtbot), details


def test_report_button_shows_the_error_for_review_and_sends_it(error_hook, mainwin, qtbot, user, opened,
                                                               monkeypatch):
    # menus.txt, Help: "**Report a problem** opens the report above, with the
    # error filled in." and "Check and edit the text, then click **Open on
    # GitHub** to finish the issue in your browser". The form
    # (bug_report.yaml) has the fields Current Behavior and System.
    monkeypatch.setattr(about, 'AboutPuddletag', synthetic_error)
    user.click_menu('About puddletag')

    window, _ = report_from_message(qtbot, user)

    assert text_of(window, 'Title') == SUMMARY
    current = text_of(window, 'Current Behavior')
    assert current.startswith('puddletag showed this error:\n\n```\nTraceback (most recent call last):')
    assert current.endswith(SUMMARY + '\n```')
    steps = text_of(window, 'Steps To Reproduce')
    assert steps.endswith('Error: ' + SUMMARY)
    assert opened == []

    user.click(button(window, 'Open on GitHub'))

    [url] = opened
    sent = fields(url)
    assert sent['title'] == SUMMARY
    assert sent['current'] == current
    assert sent['reproduce'] == steps
    assert sent['system'] == text_of(window, 'Information about your system')
    assert sent['labels'] == 'bug'
    assert sent['template'] == 'bug_report.yaml'


@pytest.fixture
def tagsource_keys():
    """Synthetic keys in tagsources.conf, as the Discogs and AcoustID
    settings hold them; the file is removed afterwards."""
    config = PuddleConfig(TAGSOURCE_CONFIG)
    config.set('Discogs', 'API Key (Stored as plain text. Leave empty to send none.)', 'SynthDiscogsToken42')
    config.set('AcoustID', 'AcoustID Key', 'SynthAcoustKey7')
    yield
    os.remove(TAGSOURCE_CONFIG)


def test_report_leaves_out_personal_details(error_hook, mainwin, qtbot, user, opened, monkeypatch, tagsource_keys):
    # menus.txt, Help: "Before you see it, the report leaves out your home
    # folder (shown as ``~``), your user name, your computer's name, email
    # addresses and the keys you gave tag sources." Synthetic: a home
    # folder, user name, host name, email address and tag source keys
    # that nobody owns.
    monkeypatch.setenv('LOGNAME', 'synthuser')
    monkeypatch.setattr('socket.gethostname', lambda: 'synthhost.example.lan')
    home = os.path.expanduser('~')
    message = (f'{home}/Music/a.mp3 synthuser synthhost someone@example.com SynthDiscogsToken42 SynthAcoustKey7 '
               'https://api.example.org/x?q=abba&token=Synth123')
    monkeypatch.setattr(about, 'AboutPuddletag', raising(message))
    user.click_menu('About puddletag')

    window, _ = report_from_message(qtbot, user)

    last_line = ('ValueError: ~/Music/a.mp3 <user> <host> <email> <key> <key> '
                 'https://api.example.org/x?q=abba&token=<removed>')
    assert text_of(window, 'Current Behavior').endswith(last_line + '\n```')
    assert text_of(window, 'Title') == last_line[:100]

    user.click(button(window, 'Open on GitHub'))

    [url] = opened
    leaks = ['synthuser', 'synthhost', 'someone@', 'SynthDiscogsToken42', 'SynthAcoustKey7', 'Synth123', home]
    for label in ('Title', 'Current Behavior', 'Information about your system'):
        for leak in leaks:
            assert leak not in text_of(window, label)
    for value in fields(url).values():
        for leak in leaks:
            assert leak not in value


def test_long_traceback_is_trimmed_to_fit(error_hook, mainwin, qtbot, user, opened, monkeypatch):
    # menus.txt, Help: "Check and edit the text, then click **Open on
    # GitHub**". An issue address has a length limit (GitHub's docs: "a URL
    # that exceeds the server limit returns a 414 URI Too Long"), so the
    # middle of a long traceback is left out. Synthetic: a function that
    # calls itself through a second one 300 times, then raises.
    def ping(depth):
        if depth:
            return pong(depth - 1)
        raise ValueError('synthetic error')

    def pong(depth):
        if depth:
            return ping(depth - 1)
        raise ValueError('synthetic error')

    monkeypatch.setattr(about, 'AboutPuddletag', lambda *args: ping(300))
    user.click_menu('About puddletag')

    window, details = report_from_message(qtbot, user)

    current = text_of(window, 'Current Behavior')
    assert current.startswith('puddletag showed this error:\n\n```\nTraceback (most recent call last):')
    assert current.endswith(SUMMARY + '\n```')
    assert 'show_about' in frames(current)[0]
    [left_out] = re.findall(r'\[\.\.\. (\d+) frames left out \.\.\.\]', current)
    assert frames(current)[-3:] == frames(details)[-3:]
    assert len(frames(current)) + int(left_out) == len(frames(details))

    user.click(button(window, 'Open on GitHub'))

    [url] = opened
    assert len(url) <= MAX_URL_LENGTH
    assert fields(url)['current'] == current
    assert 'clipboard' not in fields(url)['current']


def test_puddletag_quits_cleanly(tmp_path):
    # menus.txt, File: "Exit (Ctrl+Q): Closes puddletag." Started through
    # its launcher script, in a process of its own, it must exit with 0
    # rather than crash while Python and Qt shut down.
    config = tmp_path / 'config'
    data = tmp_path / 'data'
    code = '\n'.join([
        'import runpy',
        'import sys',
        f'sys.path.insert(0, {str(REPO)!r})',
        'from PyQt6.QtCore import QTimer',
        'from PyQt6.QtGui import QAction',
        'from PyQt6.QtWidgets import QApplication',
        'real_exec = QApplication.exec',
        'def choose_exit():',
        '    [window] = [w for w in QApplication.topLevelWidgets() if type(w).__name__ == "MainWin"]',
        '    [action] = [a for a in window.findChildren(QAction) if a.text() == "&Exit"]',
        '    action.trigger()',
        'def exec_after_exit():',
        '    QTimer.singleShot(1000, choose_exit)',
        '    return real_exec()',
        'QApplication.exec = staticmethod(exec_after_exit)',
        f'sys.argv = [{str(REPO / "puddletag")!r}]',
        f'runpy.run_path({str(REPO / "puddletag")!r}, run_name="__main__")',
    ])
    env = {**os.environ, 'HOME': str(tmp_path), 'PYTHONPATH': str(REPO), 'QT_QPA_PLATFORM': 'offscreen',
           'XDG_CONFIG_HOME': str(config), 'XDG_DATA_HOME': str(data)}

    result = subprocess.run([sys.executable, '-c', code], env=env, cwd=tmp_path, timeout=60)

    assert result.returncode == 0
