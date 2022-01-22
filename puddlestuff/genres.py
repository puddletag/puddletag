# -*- coding: utf-8 -*-
import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHBoxLayout, QListWidgetItem, QWidget

from . import audioinfo
from .constants import CONFIGDIR
from .puddleobjects import (ListButtons, ListBox)


def load_genres(filepath=None):
    if not filepath:
        filepath = os.path.join(CONFIGDIR, 'genres')
    try:
        return [x.strip() for x in open(filepath, 'r').readlines() if x.strip()]
    except (IOError, OSError):
        return audioinfo.GENRES[::]


def save_genres(genres, filepath=None):
    if not filepath:
        filepath = os.path.join(CONFIGDIR, 'genres')
    f = open(filepath, 'w')
    f.write('\n'.join(genres))
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

        buttons.add.connect(self.add)
        buttons.edit.connect(self.edit)

        hbox = QHBoxLayout()
        hbox.addWidget(self.listbox, 1)
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
        genres = [str(item(row).text()) for row in
                  range(self.listbox.count())]
        self._status['genres'] = genres
