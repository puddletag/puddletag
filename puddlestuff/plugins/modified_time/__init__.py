import os

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QMessageBox

from .. import status
from ... import audioinfo
from ...puddleobjects import progress
from ... import puddletag


def init(parent=None):
    action = QAction('Add 2 seconds to modified time', parent)
    action.triggered.connect(lambda: add_seconds(parent))
    action.setShortcut('Ctrl+M')

    def sep():
        k = QAction(parent)
        k.setSeparator(True)
        return k

    puddletag.add_shortcuts('&Plugins', [sep(), action, sep()])


def add_seconds(parent=None):
    if status['previewmode']:
        QMessageBox.information(parent, 'puddletag',
                                QApplication.translate("Previews",
                                                       'You need to disable preview mode first.'))
        return

    files = status['selectedfiles']
    rows = status['selectedrows']

    def func():
        for row, f in zip(rows, files):
            try:
                stat = os.stat(f.filepath)
                os.utime(f.filepath, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))
            except (IOError, OSError) as e:
                filename = f[audioinfo.PATH]
                m = str(QApplication.translate('Defaults',
                                               "An error occured while setting the modification time of <b>{}</b>. ({})"
                                               ).format(filename, e.strerror))
                if row == rows[-1]:
                    yield m, 1
                else:
                    yield m, len(rows)

    s = progress(func, QApplication.translate("Adding 2 seconds to mod times...",
                                              'Setting modification time '), len(files))
    s(parent)
