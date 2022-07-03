from functools import partial

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QApplication, QMessageBox, QAction

from .. import connect_shortcut, status
from ... import audioinfo
from ...constants import FILESSELECTED
from ...puddleobjects import progress
from ...puddletag import add_shortcuts
from ...util import separator

obj = QObject()
id3_tag = audioinfo.id3.Tag


def to_utf8(parent=None):
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
                if isinstance(f, id3_tag):
                    f.to_encoding(3)
                    f.link(f.filepath)
                yield None
            except (IOError, OSError) as e:
                filename = f[audioinfo.PATH]
                m = str(QApplication.translate('Defaults',
                                               "An error occured while converting <b>{}</b>. ({})"
                                               ).format(filename, e.strerror))
                if row == rows[-1]:
                    yield m, 1
                else:
                    yield m, len(rows)

    s = progress(func, QApplication.translate("ID3 Plugin",
                                              'Converting '), len(files))
    s(parent)


def update_to_24(parent=None):
    if status['previewmode']:
        QMessageBox.information(parent, 'puddletag',
                                QApplication.translate("Previews",
                                                       'You need to disable preview mode first.'))
        return
    files = status['selectedfiles']
    rows = status['selectedrows']

    def func():
        for f in files:
            try:
                if isinstance(f, id3_tag):
                    f.save(v1=1)
                    f.link(f.filepath)
                yield None
            except (IOError, OSError) as e:
                filename = f[audioinfo.PATH]
                m = str(QApplication.translate('Defaults',
                                               "An error occured while updating <b>{}</b>. ({})"
                                               ).format(filename, e.strerror))
                if row == rows[-1]:
                    yield m, 1
                else:
                    yield m, len(rows)

    s = progress(func, QApplication.translate("ID3 Plugin",
                                              'Updating '), len(files))
    s(parent)


def init(parent=None):
    action = QAction('&Update to ID3v2.4', parent)
    connect_shortcut(action, FILESSELECTED)
    action.triggered.connect(partial(update_to_24, parent))

    convert = QAction('&Convert to UTF-8', parent)
    connect_shortcut(convert, FILESSELECTED)
    convert.triggered.connect(partial(to_utf8, parent))

    add_shortcuts('Ta&g Tools', [separator(), action, convert, separator()])
