"""The user's last steps, kept for the problem report.

Only what the user did is recorded, as text: the command run, the window
opened, how many files were loaded. Never tag values, typed text, or file
and folder names.
"""
import atexit
from collections import Counter, deque

from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

MAX_STEPS = 20

_steps = deque(maxlen=MAX_STEPS)


def record(text):
    _steps.append(text)


def recent():
    """The steps, oldest first."""
    return list(_steps)


def clear():
    _steps.clear()


def record_command(text, command):
    record(f'{text.replace("&", "")} ({command})')


def record_loaded(files):
    """Files loaded, given as (extension, folder) pairs."""
    if not files:
        return
    extensions = Counter(extension for extension, folder in files)
    folders = len({folder for extension, folder in files})
    if len(extensions) == 1:
        kinds = next(iter(extensions))
    else:
        kinds = ', '.join(f'{extension} {count}' for extension, count in sorted(extensions.items()))
    record(f'Loaded {len(files)} file{"" if len(files) == 1 else "s"} ({kinds}) '
           f'from {folders} folder{"" if folders == 1 else "s"}')


class _WindowWatcher(QObject):
    """Records each dialog window that is shown, except the progress window,
    messages and the problem report's own window."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Show and isinstance(obj, QDialog) and obj.isWindow():
            from .bugreport import ReviewWindow
            from .puddleobjects import ProgressWin
            if not isinstance(obj, (ProgressWin, QMessageBox, ReviewWindow)):
                record(f'Opened window: {obj.windowTitle()}')
        return False


_watcher = None


def watch_windows():
    """Starts recording the windows shown, once."""
    global _watcher
    app = QApplication.instance()
    if _watcher is None or _watcher.parent() is not app:
        _watcher = _WindowWatcher(app)
        app.installEventFilter(_watcher)
        # A filter still installed when Python exits crashes it.
        atexit.register(app.removeEventFilter, _watcher)
