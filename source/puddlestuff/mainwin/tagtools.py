# -*- coding: utf-8 -*-

from PyQt4.QtCore import SIGNAL, QObject
from PyQt4.QtGui import QAction
from functools import partial
import traceback
from mutagen import id3, apev2

all = ['remove_id3', 'remove_apev2']

_delete = {
    'APEv2':apev2.delete,
    'ID3v1': partial(id3.delete, v1=True, v2=False),
    'ID3v1': partial(id3.delete, v1=False, v2=True),
    'ID3': partial(id3.delete, v1=True, v2=True),
    }

status = {}

def _remove_tag(f, tag):
    try:
        _delete[tag](f.filepath)
    except:
        traceback.print_exc()
        return

def remove_tag(tag):
    files = status['selectedfiles']
    [_remove_tag(f, tag) for f in files]

remove_apev2 = lambda: remove_tag('APEv2')
remove_id3 = lambda: remove_tag('ID3')
remove_id3v1 = lambda: remove_tag('ID3v1')
remove_id3v2 = lambda: remove_tag('ID3v2')

def set_status(stat):
    global status
    status = stat