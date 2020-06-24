# -*- coding: utf-8 -*-
import os
import pickle
import traceback

import mutagen
from PyQt5.QtWidgets import QAction, QFileDialog
from puddlestuff.plugins import status

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
    selectedFile = QFileDialog.getSaveFileName(None, "Save tags", last_fn['fn'], "*.*")
    fn = selectedFile[0]
    if fn:
        save_tags(f.filepath for f in status['all_tags'])
        last_fn['fn'] = os.path.dirname(fn)


def init(parent=None):
    state = {}

    def sep():
        k = QAction(parent)
        k.setSeparator(True)
        return k

    action = QAction('Export tags', parent)
    action.toggled.connect(export_tags)
    add_shortcuts('&Plugins', [sep(), action, sep()])
