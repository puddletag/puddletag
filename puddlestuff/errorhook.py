"""Shows an error nothing in puddletag caught, in a message, instead of
letting PyQt6 abort the process (it does when sys.excepthook is Python's
default).

The launcher calls install() once. Every error is logged. The message opens
from the event loop, never inside the code that failed (a paint, a model's
data(), a worker thread), and one at a time: errors that happen while it's
open are counted in it, and an error that keeps happening, again and again
within two seconds, is only logged until it stops.
"""
import logging
import re
import sys
import threading
import time
import traceback

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox

from . import steps
from .translations import translate

hook = None

# An error that comes back sooner than this after its last time is only logged.
REPEAT_SECONDS = 2


def _where(details):
    """The file and line of the traceback's last frame."""
    frames = re.findall(r'File "(.*)", line (\d+)', details)
    return frames[-1] if frames else None


def _parent():
    for window in QApplication.topLevelWidgets():
        if isinstance(window, QMainWindow) and window.isVisible():
            return window


def _message(summary, details, parent):
    message = QMessageBox(QMessageBox.Icon.Critical, 'puddletag', summary, parent=parent)
    message.setWindowModality(Qt.WindowModality.ApplicationModal)
    message.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    message.setInformativeText(translate(
        'Errors', "puddletag ran into an error it didn't expect. It keeps running, but the command "
                  "that failed may have stopped part way: check the files it was working on."))
    message.setDetailedText(details)
    report = message.addButton(translate('Menus', '&Report a problem'), QMessageBox.ButtonRole.ActionRole)
    close = message.addButton(QMessageBox.StandardButton.Close)
    message.setDefaultButton(close)
    message.setEscapeButton(close)

    def send():
        from . import bugreport
        message.close()
        bugreport.report_error(parent, summary, details)

    report.clicked.connect(send)
    return message


def report_startup_error(exc_type, exc_value, exc_tb):
    """Logs an error that stopped puddletag from starting and shows it,
    waiting for the user to close the message."""
    logging.getLogger(__name__).error('Unhandled error', exc_info=(exc_type, exc_value, exc_tb))
    summary = ''.join(traceback.format_exception_only(exc_type, exc_value)).strip()
    details = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    _message(summary, details, None).exec()


class ErrorHook(QObject):
    caught = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self._previous = sys.excepthook
        self._previous_thread = threading.excepthook
        self._quitting = False
        self._base = ''
        self._message = None
        self._more = 0
        self._last = {}
        # Queued, whichever thread the error is in: the message never opens
        # inside the code that failed, and a worker's error crosses safely.
        self.caught.connect(self._show, Qt.ConnectionType.QueuedConnection)

    def quitting(self):
        self._quitting = True

    def excepthook(self, exc_type, exc_value, exc_tb):
        self._handle(exc_type, exc_value, exc_tb, lambda: self._previous(exc_type, exc_value, exc_tb))

    def threadhook(self, args):
        if args.exc_type is SystemExit:
            return
        self._handle(args.exc_type, args.exc_value, args.exc_traceback,
                     lambda: self._previous_thread(args))

    def _handle(self, exc_type, exc_value, exc_tb, previous):
        if issubclass(exc_type, KeyboardInterrupt):
            previous()
            QApplication.exit(130)
            return
        try:
            logging.getLogger(__name__).error('Unhandled error', exc_info=(exc_type, exc_value, exc_tb))
            summary = ''.join(traceback.format_exception_only(exc_type, exc_value)).strip()
            details = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
            if not self._quitting:
                self.caught.emit(summary, details)
        except Exception:
            sys.__excepthook__(exc_type, exc_value, exc_tb)

    def _show(self, summary, details):
        key = (summary, _where(details))
        now = time.monotonic()
        last = self._last.get(key)
        self._last[key] = now
        if self._message is not None:
            self._more += 1
            self._message.setInformativeText(self._base + '\n\n' + translate(
                'Errors', '{} more errors happened while this message was open; '
                          'they are in the log.').format(self._more))
            return
        if last is not None and now - last < REPEAT_SECONDS:
            return
        steps.record(f'Error: {summary}')
        self._more = 0
        message = _message(summary, details, _parent())
        self._base = message.informativeText()
        self._message = message
        message.finished.connect(self._closed)
        message.show()

    def _closed(self, *args):
        self._message = None


def install(app):
    """Sets the hooks, keeping the previous ones, and returns the hook."""
    global hook
    hook = ErrorHook()
    sys.excepthook = hook.excepthook
    threading.excepthook = hook.threadhook
    app.aboutToQuit.connect(hook.quitting)
    return hook
