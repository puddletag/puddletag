# -*- coding: utf-8 -*-
import mutagen, os, cPickle as pickle, sys, traceback

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from puddlestuff.plugins import status, add_shortcuts

last_fn = {'fn': '~'}

def save_tags(files, fn):
    tags = []
    for f in files:
        try:
            tags.append(mutagen.File(f))
        except:
            traceback.print_exc()
            pass
    output = open(fn, 'wb')
    pickle.dump(tags, output)
    output.close()

def export_tags():
    fn = QFileDialog.getSaveFileName(None, "Save tags", last_fn['fn'], "*.*")
    if fn:
        save_tags((f.filepath for f in status['selectedfiles']), fn)
        last_fn['fn'] = os.path.dirname(str(fn.toLocal8Bit()))

def init(parent=None):

    def sep():
        k = QAction(parent)
        k.setSeparator(True)
        return k

    action = QAction('Export tags', parent)
    action.triggered.connect(export_tags)
    add_shortcuts('&Plugins', [sep(), action, sep()])
