# -*- coding: utf-8 -*-

from PyQt4.QtCore import SIGNAL, QObject
from PyQt4.QtGui import QAction, QMessageBox
from functools import partial
import traceback
from mutagen import id3, apev2
import puddlestuff.audioinfo as audioinfo
from puddlestuff.puddleobjects import progress

id3_tag = audioinfo.id3.Tag
ape_tag = audioinfo.apev2.Tag

all = ['remove_id3', 'remove_apev2']

_delete = {
    'APEv2':apev2.delete,
    #'ID3v1': partial(id3.delete, v1=True, v2=False),
    #'ID3v2': partial(id3.delete, v1=False, v2=True),
    'ID3': partial(id3.delete),
    }

status = {}

def _remove_tag(f, tag):
    if tag == 'APEv2' and isinstance(f, ape_tag):
        return
    elif tag == 'ID3' and isinstance(f, id3_tag):
        return
    try:
        _delete[tag](f.filepath)
    except:
        traceback.print_exc()
        return

def remove_tag(tag, parent):
    if status['previewmode']:
        QMessageBox.information(parent, 'puddletag',
            QApplication.translate("Previews", 'Disable Preview Mode first to enable tag deletion.'))
        return
    files = status['selectedfiles']

    def func():
        for f in files:
            try:
                _remove_tag(f, tag)
            except (IOError, OSError), e:
                filename = f[audioinfo.PATH]
                m = unicode(QApplication.translate("Defaults",
                    'An error occured while writing to <b>%1</b>. (%2)').arg(filename).arg(e.strerror))
                if row == rows[-1]:
                    yield m, 1
                else:
                    yield m, len(rows)

    s = progress(func, QApplication.translate("Tag Tools", 'Removing %s tag: ') % tag, len(files))
    s(parent)

remove_apev2 = lambda parent=None: remove_tag('APEv2', parent)
remove_id3 = lambda parent=None: remove_tag('ID3', parent)
#remove_id3v1 = lambda: remove_tag('ID3v1')
#remove_id3v2 = lambda: remove_tag('ID3v2')

def set_status(stat):
    global status
    status = stat