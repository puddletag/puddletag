# -*- coding: utf-8 -*-
import tempfile

from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import QFont, QFontMetrics, QPainter, QBrush
from PyQt5.QtSvg import QSvgGenerator
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ..audioinfo.util import commonimages
from ..constants import KEEP, BLANK
from ..constants import RIGHTDOCK, SELECTIONCHANGED
from ..puddleobjects import PicWidget


def svg_to_pic(data, desc):
    return {'data': data, 'size': len(data),
            'description': desc, 'imagetype': 3}


def get_font(rect, *text):
    font = QFont()
    metrics = QFontMetrics
    lengths = [(t, metrics(font).width(t)) for t in text]
    lowest = max(lengths, key=lambda x: x[1])
    size = 12
    while QFontMetrics(font).width(lowest[0]) < rect.width() - 30:
        font.setPointSize(size)
        size += 1
    return font


def create_svg(text, font, rect=None):
    if not rect:
        rect = QRect(0, 0, 200, 200)
    f = tempfile.NamedTemporaryFile()

    generator = QSvgGenerator()
    generator.setFileName(f.name)
    generator.setSize(rect.size())
    generator.setViewBox(rect);
    generator.setTitle("puddletag image")
    generator.setDescription("just to see")

    painter = QPainter()
    painter.begin(generator)
    painter.fillRect(rect, Qt.black)
    painter.setFont(font)
    painter.setPen(Qt.white)
    painter.setBrush(QBrush(Qt.white))
    painter.drawText(rect, Qt.AlignCenter, text)
    painter.end()

    svg = open(f.name).read()
    f.close()
    return svg


class ArtworkWidget(QWidget):
    def __init__(self, parent=None, status=None):
        QWidget.__init__(self, parent)
        self.receives = [(SELECTIONCHANGED, self.fill)]
        self.emits = []
        self.picwidget = PicWidget()
        vbox = QVBoxLayout()
        vbox.addWidget(self.picwidget)
        hbox = QHBoxLayout()
        hbox.addStrut(1)
        vbox.addLayout(hbox)
        self.setLayout(vbox)
        status['images'] = self.images
        self._audios = []
        self._status = status
        self._readOnly = None

    def fill(self, audios=None):
        if audios is None:
            audios = self._status['selectedfiles']
        if not audios:
            self.picwidget.setEnabled(False)
            self.picwidget.setImages(None)
            return
        if not self.isVisible():
            self._audios = audios
            return
        self.picwidget.currentFile = audios[0]
        self.picwidget.filePattern = self._status['cover_pattern']
        pics = list(self._readOnlyPics())
        self.picwidget.setEnabled(True)
        images = []
        imagetags = set()
        for audio in audios:
            imagetags = imagetags.union(audio.IMAGETAGS)
            if audio.IMAGETAGS:
                images.append(audio.images)
            else:
                images.append({})

        self.picwidget.lastfilename = audios[0].filepath
        images = commonimages(images)
        self.picwidget.setImageTags(imagetags)

        if images == 0:
            self.picwidget.setImages(pics, default=0)
            self.picwidget.context = 'Cover Varies'
        elif images is None:
            self.picwidget.setImages(pics, default=1)
        else:
            pics.extend(images)
            self.picwidget.setImages(pics, default=2)
        self.picwidget.readonly = [0, 1]

        if imagetags:
            self.setEnabled(True)
        else:
            self.setEnabled(False)

    def init(self):
        pics = self._readOnlyPics()
        self.picwidget.setImages(pics)
        self.picwidget.readonly = [0, 1]

    def _readOnlyPics(self):
        if not self._readOnly:
            font = get_font(QRect(0, 0, 200, 200), KEEP, BLANK)
            data = (create_svg(KEEP, font), create_svg(BLANK, font))
            self._readOnly = tuple([svg_to_pic(datum, desc) for datum, desc
                                    in zip(data, (KEEP, BLANK))])
        return self._readOnly

    def images(self):
        images = None
        if self.picwidget.currentImage == 1:  # <blank>
            images = []
        elif self.picwidget.currentImage > 1:  # <keep> is 0, so everything else.
            images = self.picwidget.images[2:]
        return images

    def showEvent(self, event):
        QWidget.showEvent(self, event)
        if self._audios:
            self.fill(self._audios)
            self._audios = []


control = ('Artwork', ArtworkWidget, RIGHTDOCK, False)
