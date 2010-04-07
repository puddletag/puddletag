# -*- coding: utf8 -*-
import sys, os, unittest, time, pdb, shutil
from os import path
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import cPickle as pickle
import mutagen, pyparsing, puddlestuff
from puddlestuff.puddleobjects import OKCancel


desc  = '''puddletag is a tag editor for Linux loosely based on the Windows program Mp3tag.

<br /><br />Features include: Batch editing of tags, renaming files using tags, retrieving tags from filenames, using Actions to automate repetitive tasks, importing your music library and other awesome stuff. <br /><br />

Supported formats: id3v1, id3v2 (.mp3), AAC (.mp4, .m4a), VorbisComments (.ogg, .flac) and APEv2 (.ape) <br />< br />

Visit the puddletag website (<a href="http://puddletag.sourceforge.net">http://puddletag.sourceforge.net</a>) for help and updates.<br /><br />
&copy; 2010 concentricpuddle (concentricpuddle@gmail.com) <br />
Licensed under GPLv2 (<a href="www.gnu.org/licenses/gpl-2.0.html">www.gnu.org/licenses/gpl-2.0.html</a>).
'''

thanks = """<b>Evan Devetzis</b> for contributing many, many ideas for putting up with more bugs than any user's expected to and being a helluva tester. <br /> <br />
The authors of the libraries puddletag depends on:< br />
<b>Paul McGuire</b> for PyParsing and for being helpful when I needed it.<br />
<b>Michael Urman</b> and <b>Joe Wreschnig</b> for Mutagen (without it, puddletag woulda been a whole lot buggier).<br />
<b>Phil Thomson</b>, <b>Trolltech</b> and everyone responsible for PyQt4 and...<br />
<b>Michael Foord</b> and Nicola Larosa</b>, the creators of ConfigObj."""


class ScrollLabel(QWidget):
    def __init__(self, text, alignment = Qt.AlignCenter, parent=None):
        QWidget.__init__(self, parent)
        vbox = QVBoxLayout()
        self.setLayout(vbox)
        label = QLabel(text)

        label.setTextFormat(Qt.RichText)
        label.setAlignment(alignment)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextBrowserInteraction)

        sa = QScrollArea()
        sa.setWidget(label)
        sa.setWidgetResizable(True)
        vbox.addWidget(sa)
        self.label = label


class AboutPuddletag(QDialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle('About puddletag')
        lib_versions = ', '.join(['<b>PyQt  %s' % PYQT_VERSION_STR,
                                     'Mutagen %s' % mutagen.version_string,
                                     'Pyparsing %s</b>' %pyparsing.__version__])
        label = QLabel('<h2>puddletag %s</h2> %s' % (puddlestuff.version_string, lib_versions))

        tab = QTabWidget()
        tab.addTab(ScrollLabel(desc), '&About')
        tab.addTab(ScrollLabel(thanks, Qt.AlignLeft), '&Thanks')

        vbox = QVBoxLayout()
        vbox.addWidget(label)
        vbox.addWidget(tab, 1)
        ok = OKCancel()
        ok.cancel.setVisible(False)
        vbox.addLayout(ok)
        self.connect(ok, SIGNAL('ok'), self.close)
        self.setLayout(vbox)

if __name__ == '__main__':
    app = QApplication([])
    win = AboutPuddletag()
    win.show()
    app.exec_()
