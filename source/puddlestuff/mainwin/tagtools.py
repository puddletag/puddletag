# -*- coding: utf-8 -*-

from PyQt4.QtCore import SIGNAL, QObject
from PyQt4.QtGui import QAction
from functools import partial
from puddlestuff.audioinfo import apev2, id3
import traceback

all = ['add_id3', 'add_apev2', 'remove_id3', 'remove_apev2']

filetypes = {'APEv2': apev2.filetype[1], 'ID3': id3.filetype[1]}

status = {}
obj = QObject

def _add_tag(f, filetype):
    if filetype in f._filetypes:
        return
    audio = filetypes[filetype](f.filepath)
    f.add_tag(filetype, audio)

def add_tag(tag):
    files = status['selectedfiles']
    [_add_tag(f, tag) for f in files]

add_id3 = lambda: add_tag('ID3')
add_apev2 = lambda: add_tag('APEv2')

def _remove_tag(f, tag):
    try:
        f.delete(tag)
    except:
        traceback.print_exc()
        return

def remove_tag(tag):
    files = status['selectedfiles']
    [_remove_tag(f, tag) for f in files]

def set_status(stat):
    global status
    status = stat

remove_apev2 = lambda: remove_tag('APEv2')
remove_id3 = lambda: remove_tag('ID3')