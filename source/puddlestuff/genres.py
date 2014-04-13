# -*- coding: utf-8 -*-
from PyQt4.QtGui import *
from PyQt4.QtCore import *
import sys, resource, os, audioinfo
from puddleobjects import (ListButtons, OKCancel, HeaderSetting, ListBox,
    PuddleConfig, savewinsize, winsettings, encode_fn, decode_fn)

from puddlestuff.constants import CONFIGDIR

def load_genres(filepath=None):
    if not filepath:
        filepath = os.path.join(CONFIGDIR, 'genres')
    try:
        return [unicode(z.strip(), 'utf8') for z in
            open(filepath, 'r').readlines()]
    except (IOError, OSError):
        return audioinfo.GENRES[::]

def save_genres(genres, filepath=None):
    if not filepath:
        filepath = os.path.join(CONFIGDIR, 'genres')
    f = open(filepath, 'w')
    text = '\n'.join([z.encode('utf8') for z in genres])
    f.write(text)
    f.close()

class Genres(QWidget):
    def __init__(self, parent=None, status=None):
        QWidget.__init__(self, parent)
        if status is None:
            self._status = {}
            genres = load_genres()
        else:
            self._status = status
            genres = status['genres']

        self.listbox = ListBox()
        self._itemflags = Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled
        [self.listbox.addItem(self._createItem(z)) for z in genres]

        buttons = ListButtons()
        self.listbox.connectToListButtons(buttons)
        self.listbox.setAutoScroll(False)

        self.connect(buttons, SIGNAL('add'), self.add)
        self.connect(buttons, SIGNAL('edit'), self.edit)

        hbox = QHBoxLayout()
        hbox.addWidget(self.listbox,1)
        hbox.addLayout(buttons, 0)
        self.setLayout(hbox)

    def _createItem(self, text):
        item = QListWidgetItem(text)
        item.setFlags(self._itemflags)
        return item

    def add(self):
        self.listbox.setAutoScroll(True)
        item = self._createItem('')
        self.listbox.addItem(item)
        self.listbox.clearSelection()
        self.listbox.setCurrentItem(item)
        self.listbox.editItem(item)
        self.listbox.setAutoScroll(False)

    def edit(self):
        self.listbox.setAutoScroll(True)
        self.listbox.editItem(self.listbox.currentItem())
        self.listbox.setAutoScroll(False)

    def applySettings(self, control=None):
        item = self.listbox.item
        genres = [unicode(item(row).text()) for row in
            xrange(self.listbox.count())]
        self._status['genres'] = genres