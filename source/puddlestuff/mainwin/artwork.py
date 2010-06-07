# -*- coding: utf-8 -*-
import sys, os
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from puddlestuff.constants import LEFTDOCK, SELECTIONCHANGED
from puddlestuff.puddleobjects import PicWidget
from puddlestuff.audioinfo.util import commonimages

class ArtworkWidget(QWidget):
    def __init__(self, parent=None, status = None):
        QWidget.__init__(self, parent)
        self.receives = [(SELECTIONCHANGED, self.fill)]
        self.emits = []
        self.picwidget = PicWidget()
        vbox = QVBoxLayout()
        vbox.addWidget(self.picwidget)
        self.setLayout(vbox)
        status['images'] = self.images
        self._audios = []
        self._status = status

    def fill(self):
        audios = self._status['selectedfiles']
        self.picwidget.setImages(None)
        self.init()
        if not audios:
            self.picwidget.setEnabled(False)
            return
        if not self.isVisible():
            self._audios = audios
            return
        self.picwidget.setEnabled(True)
        images = []
        imagetags = set()
        for audio in audios:
            imagetags = imagetags.union(audio.IMAGETAGS)
            if '__image' in audio.preview:
                value = audio.preview['__image']
            else:
                value = audio['__image'] if audio['__image'] else {}
            if audio.IMAGETAGS:
                images.append(value)
            else:
                images.append({})

        self.picwidget.lastfilename = audios[0].filepath
        images = commonimages(images)
        if images == 0:
            self.picwidget.setImageTags(imagetags)
            self.picwidget.currentImage = 0
            self.picwidget.context = 'Cover Varies'
        elif images is None:
            self.picwidget.currentImage = 1
        else:
            self.picwidget.setImageTags(imagetags)
            self.picwidget.images.extend(images)
            self.picwidget.currentImage = 2

    def init(self):
        pics = self.picwidget.loadPics(':/keep.png', ':/blank.png')
        self.picwidget.setImages(pics)
        self.picwidget.readonly = [0,1]
    
    def images(self):
        images = None
        if self.picwidget.currentImage == 1: #<blank>
            images = []
        elif self.picwidget.currentImage > 1: #<keep> is 0, so everything else.
            images = self.picwidget.images[2:]
        return images

    def showEvent(self, event):
        QWidget.showEvent(self, event)
        if self._audios:
            self.fill(self._audios)
            self._audios = []

control = ('Artwork', ArtworkWidget, LEFTDOCK, False)