from functools import partial

from mutagen import MutagenError
from PyQt6.QtCore import QObject
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QMessageBox

from .. import connect_shortcut, status
from ... import audioinfo
from ...constants import FILESSELECTED
from ...puddleobjects import progress
from ... import puddletag
from ...translations import translate
from ...util import separator

obj = QObject()
id3_tag = audioinfo.id3.Tag


def _save(save):
    """Runs save, raising the OSError a mutagen error wraps."""
    try:
        save()
    except MutagenError as e:
        if e.args and isinstance(e.args[0], OSError):
            raise e.args[0] from e
        raise


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
                    _save(lambda: f.to_encoding(3))
                    f.link(f.filepath)
                yield None
            except (IOError, OSError) as e:
                filename = f[audioinfo.PATH]
                m = str(QApplication.translate('Defaults',
                                               "An error occurred while converting <b>{}</b>. ({})"
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
        for row, f in zip(rows, files):
            try:
                if isinstance(f, id3_tag):
                    _save(lambda: f.save(v1=1, v2=4))
                    f.link(f.filepath)
                yield None
            except (IOError, OSError) as e:
                filename = f[audioinfo.PATH]
                m = str(QApplication.translate('Defaults',
                                               "An error occurred while updating <b>{}</b>. ({})"
                                               ).format(filename, e.strerror))
                if row == rows[-1]:
                    yield m, 1
                else:
                    yield m, len(rows)

    s = progress(func, QApplication.translate("ID3 Plugin",
                                              'Updating '), len(files))
    s(parent)


def init(parent=None):
    action = QAction(translate('Menus', '&Update to ID3v2.4'), parent)
    connect_shortcut(action, FILESSELECTED)
    action.triggered.connect(partial(update_to_24, parent))

    convert = QAction(translate('Menus', '&Convert to UTF-8'), parent)
    connect_shortcut(convert, FILESSELECTED)
    convert.triggered.connect(partial(to_utf8, parent))

    puddletag.add_shortcuts('Ta&g Tools', [separator(), action, convert, separator()])
