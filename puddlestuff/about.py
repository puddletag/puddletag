# -*- coding: utf-8 -*-
import mutagen
from importlib import import_module
from platform import python_version
from PyQt5.QtCore import PYQT_VERSION_STR, QT_VERSION_STR, Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QScrollArea, QTabWidget, QVBoxLayout, QWidget

from . import version_string, changeset
from .puddleobjects import OKCancel
from .translations import translate

desc = translate("About", '''puddletag is an audio tag editor for GNU/Linux similar to the Windows program Mp3tag.

<br /><br />Features include: Batch editing of tags, renaming files using tags, retrieving tags from filenames, using Actions to automate repetitive tasks, importing your music library and loads of other awesome stuff. <br /><br />

Supported formats: id3v1, id3v2 (.mp3), AAC (.mp4, .m4a), VorbisComments (.ogg, .flac) and APEv2 (.ape) <br />< br />

Visit the puddletag website (<a href="http://puddletag.sourceforge.net">http://puddletag.sourceforge.net</a>) for help and updates.<br /><br />
&copy; 2008-2012 concentricpuddle (concentricpuddle@gmail.com) <br />
Licensed under GPLv3 (<a href="www.gnu.org/licenses/gpl-3.0.html">www.gnu.org/licenses/gpl-3.0.html</a>).
''')

thanks = translate("About", """<b>Evan Devetzis</b> for his many, many awesome ideas and putting up with more bugs than humanly possible.<br /><br />

First off, a big thanks to **Evan Devetzis** for working tirelessly in helping me make puddletag better by contributing many, many awesome ideas and for being a great bug hunter.

Thanks to <b>Raphaël Rochet</b>, <b>Fabian Bakkum</b>, <b>Alan Gomes</b> and others for contributing translations.

To the writers of the libraries puddletag depends on (without which I'll probably still be writing an id3 reader).<br /><br />

<b>Paul McGuire</b> for PyParsing.<br />
<b>Michael Urman</b> and <b>Joe Wreschnig</b> for Mutagen (It. Is. Awesome).<br />
<b>Phil Thomson</b> and everyone responsible for PyQt4.<br />
<b>Michael Foord</b> and <b>Nicola Larosa</b> for ConfigObj (seriously, they should replace ConfigParser with this).<br />
The <b>Oxygen team</b> for the Oxygen icons.

""")


def versions():
    def get_module_version(module_name):
        try:
            from importlib.metadata import version
            return version(module_name)
        except ModuleNotFoundError:
            pass

        try:
            module = import_module(module_name)
            return getattr(module, '__version__',
                translate("About", 'unknown version'))
        except ModuleNotFoundError:
            return translate("About", 'not installed')

    return {
        'Python': python_version(),
        'PyQt': PYQT_VERSION_STR,
        'Qt': QT_VERSION_STR,
        'Mutagen': mutagen.version_string,
        'PyParsing': get_module_version('pyparsing'),
        'ConfigObj': get_module_version('configobj'),
        'lxml': get_module_version('lxml'),
        'pyacoustid': get_module_version('pyacoustid'),
        'audioread': get_module_version('audioread'),
        'Levenshtein': get_module_version('Levenshtein'),
        'Chromaprint': get_module_version('chromaprint'),
    }


class ScrollLabel(QWidget):
    def __init__(self, text, alignment=Qt.AlignmentFlag.AlignCenter, parent=None):
        QWidget.__init__(self, parent)
        vbox = QVBoxLayout()
        self.setLayout(vbox)
        label = QLabel(text)

        label.setTextFormat(Qt.TextFormat.RichText)
        label.setAlignment(alignment)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)

        sa = QScrollArea()
        sa.setWidget(label)
        sa.setWidgetResizable(True)
        vbox.addWidget(sa)
        self.label = label


class AboutPuddletag(QDialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(translate("About", 'About puddletag'))
        icon = QLabel()
        icon.setPixmap(QPixmap(':/appicon.svg').scaled(48, 48))
        lib_versions = '<br />'.join(
            ['%s: %s' % (lib, version) for (lib, version) in versions().items()]
        )

        if changeset:
            version = translate("About", '<h2>puddletag %1</h2>Changeset %2')
            version = version.arg(version_string)
            version = version.arg(changeset)
        else:
            version = translate("About", '<h2>puddletag %1</h2>')
            version = version.arg(version_string)
        label = QLabel(version)

        tab = QTabWidget()
        tab.addTab(ScrollLabel(desc), translate('About', '&About'))
        tab.addTab(ScrollLabel(thanks, Qt.AlignmentFlag.AlignLeft),
                   translate('About', '&Thanks'))
        tab.addTab(ScrollLabel(lib_versions, Qt.AlignmentFlag.AlignLeft),
                   translate('About', '&Libraries'))

        vbox = QVBoxLayout()
        version_layout = QHBoxLayout()
        version_layout.addWidget(icon)
        version_layout.addWidget(label, 1)
        vbox.addLayout(version_layout)
        vbox.addWidget(tab, 1)
        ok = OKCancel()
        ok.cancelButton.setVisible(False)
        vbox.addLayout(ok)
        ok.ok.connect(self.close)
        self.setLayout(vbox)


if __name__ == '__main__':
    app = QApplication([])
    win = AboutPuddletag()
    win.show()
    app.exec_()
