"""The progress window a command shows while it works through several
files, and the warning or question it shows when a file fails, run on
synthetic commands: a generator that yields None for each file done and
(message, count) for a file that failed. Synthetic commands and widgets.
"""
import threading

import pytest
from PyQt6 import sip
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget

from puddlestuff.puddleobjects import ProgressWin, progress

pytestmark = pytest.mark.ui

LEFT = Qt.MouseButton.LeftButton
Ok = QMessageBox.StandardButton.Ok
Yes = QMessageBox.StandardButton.Yes


@pytest.fixture
def parent(qtbot):
    """The window a command's progress window and messages belong to."""
    widget = QWidget()
    qtbot.addWidget(widget)
    return widget


def windows(parent):
    return parent.findChildren(ProgressWin)


def cancel_button(win):
    [button] = [b for b in win.findChildren(QPushButton) if b.text() == 'Cancel']
    return button


def test_one_file_that_fails_gets_a_plain_warning(parent, dialogs):
    # Synthetic: a command on one file that fails.
    done = []

    def func():
        yield 'Failed <b>01.mp3</b>', 1

    dialogs.answer('QMessageBox.warning', Ok)
    progress(func, 'Writing ', 1, lambda: done.append(True))(parent)
    assert [(name, args[1:]) for name, args, kwargs in dialogs.calls] == [
        ('QMessageBox.warning', ('Error', 'Failed <b>01.mp3</b>'))]
    assert done == [True]
    assert windows(parent) == []


def test_finished_run_closes_the_window_and_finishes(parent, qtbot):
    # Synthetic: the finishing step runs only once the worker has run
    # through every file.
    done = []

    def func():
        yield None
        yield None

    progress(func, 'Working ', 2, lambda: done.append(True))(parent)
    [win] = windows(parent)
    assert win.isVisible()
    assert win.label.text() == 'Working 1 of 2...'
    qtbot.waitUntil(lambda: bool(done))
    assert done == [True]
    assert not win.isVisible()


def test_extra_arguments_reach_the_command(parent, qtbot):
    # Synthetic: the arguments after the parent go to the command with it.
    seen, done = [], []

    def func(*args):
        seen.append(args)
        yield None
        yield None

    progress(func, 'Working ', 2, lambda: done.append(True))(parent, 'a', 'b')
    qtbot.waitUntil(lambda: bool(done))
    assert seen == [(parent, 'a', 'b')]


def test_nothing_to_do(parent):
    # Synthetic: a command on no files does not run and shows nothing.
    steps, done = [], []

    def func():
        steps.append(1)
        yield None

    progress(func, 'Working ', 0, lambda: done.append(True))(parent)
    assert windows(parent) == []
    assert steps == []
    assert done == []


def test_cancel_stops_a_command_that_ignores_it(parent, qtbot):
    # Synthetic: a command that yields again after being closed; Cancel
    # still ends the run.
    started, go = threading.Event(), threading.Event()
    steps, cancelled, done = [], [], []

    def func():
        yield None
        started.set()
        go.wait(5)
        try:
            yield None
        except GeneratorExit:
            steps.append('closed')
            yield None  # a command that ignores the close
        steps.append('second file')

    progress(func, 'Working ', 3, lambda: done.append(True),
             lambda: cancelled.append(True))(parent)
    [win] = windows(parent)
    qtbot.waitUntil(started.is_set)
    qtbot.mouseClick(cancel_button(win), LEFT)
    go.set()
    qtbot.waitUntil(lambda: bool(done))
    assert cancelled
    assert steps == ['closed']
    assert done == [True]
    assert not win.isVisible()


def test_focus_owner_deleted_during_a_run(parent, qtbot):
    # Synthetic: the widget that had the focus when the command started is
    # gone by the time it ends.
    container = QWidget()
    layout = QVBoxLayout(container)
    edit = QLineEdit()
    layout.addWidget(edit)
    container.show()
    container.activateWindow()
    edit.setFocus()
    qtbot.waitUntil(lambda: QApplication.focusWidget() is edit)

    go = threading.Event()
    done = []

    def func():
        go.wait(5)
        yield None
        yield None

    progress(func, 'Working ', 2, lambda: done.append(True))(parent)
    sip.delete(container)
    go.set()
    qtbot.waitUntil(lambda: bool(done))


def test_busy_bar_with_a_message(parent, qtbot):
    # Synthetic: the window music libraries show while they load.
    win = ProgressWin(parent, 0, 'Loading library')
    win.show()
    assert not win.pbar.isTextVisible()
    assert win.label.text() == 'Loading library'
    assert win.label.isVisible()
    qtbot.waitUntil(lambda: win.value > 0)
    win.close()
    assert not win._timer.isActive()


def test_busy_bar_without_a_message(parent):
    # Synthetic: a busy bar with no message hides the label.
    win = ProgressWin(parent, 0, '')
    win.show()
    assert not win.label.isVisible()


def test_no_cancel_button(parent):
    # Synthetic: a window asked not to show Cancel has none visible.
    win = ProgressWin(parent, 5, 'x', showcancel=False)
    win.show()
    assert not cancel_button(win).isVisible()


def test_last_file_that_fails_gets_a_plain_warning(parent, qtbot, dialogs):
    # Synthetic. menus.txt, Undo: "If a file can't be written, puddletag
    # says so as it does for any write and goes on with the other files",
    # and Undo shows a plain warning for the last file.
    done = []

    def func():
        yield None
        yield 'Failed <b>02.mp3</b>', 1

    dialogs.answer('QMessageBox.warning', Ok)
    progress(func, 'Writing ', 2, lambda: done.append(True))(parent)
    qtbot.waitUntil(lambda: bool(done))
    assert [(name, args[1:]) for name, args, kwargs in dialogs.calls] == [
        ('QMessageBox.warning', ('Error', 'Failed <b>02.mp3</b>'))]


def test_a_file_before_the_last_that_fails_asks_whether_to_continue(parent, qtbot, dialogs):
    # Synthetic: a file that fails with another still to do asks whether to
    # go on.
    done = []

    def func():
        yield 'Failed <b>01.mp3</b>', 2
        yield None

    dialogs.answer('QMessageBox.exec', Yes)
    progress(func, 'Writing ', 2, lambda: done.append(True))(parent)
    qtbot.waitUntil(lambda: bool(done))
    [(name, args, kwargs)] = dialogs.calls
    assert name == 'QMessageBox.exec'
    assert args[0].text() == 'Failed <b>01.mp3</b><br /> Do you want to continue?'
