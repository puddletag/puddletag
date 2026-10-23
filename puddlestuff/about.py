# -*- coding: utf-8 -*-
import mutagen
from importlib import import_module
from platform import python_version
from PyQt6.QtCore import PYQT_VERSION_STR, Qt, QUrl, qVersion
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QScrollArea, QTabWidget, QVBoxLayout, QWidget

from . import version_string, changeset
from .puddleobjects import OKCancel
from .translations import translate

desc = translate("About", '''puddletag is an audio tag editor for GNU/Linux similar to the Windows program Mp3tag.

<br /><br />Features include: Batch editing of tags, renaming files using tags, retrieving tags from filenames, using Actions to automate repetitive tasks, importing your music library and loads of other awesome stuff. <br /><br />

Supported formats: ID3v1, ID3v2 (mp3, and in AIFF, DSF and DSDIFF files), MP4 (mp4, m4a, etc.), VorbisComments (ogg, opus, flac), APEv2 (Musepack mpc, Monkey's Audio ape, WavPack wv) and Windows Media (wma). <br /><br />

Visit the puddletag website (<a href="https://docs.puddletag.net">https://docs.puddletag.net</a>) for help and updates.<br /><br />
&copy; 2008-2012 concentricpuddle (concentricpuddle@gmail.com) <br />
Licensed under GPLv3 (<a href="http://www.gnu.org/licenses/gpl-3.0.html">http://www.gnu.org/licenses/gpl-3.0.html</a>).
''')

thanks = translate("About", """<b>Thank yous</b><br /><br />

First off, a big thanks to <b>Evan Devetzis</b> for working tirelessly in helping me make puddletag better by contributing many, many awesome ideas and for being a great bug hunter.<br /><br />

To the writers of the libraries puddletag depends on (without which I'll probably still be writing an id3 reader).<br /><br />

<b>Paul McGuire</b> for PyParsing and for being extraordinarily helpful.<br />
<b>Michael Urman</b> and <b>Joe Wreschnig</b> for Mutagen (It. Is. Awesome).<br />
<b>Nokia, Phil Thomson</b> and all parties responsible for PyQt4.<br />
<b>Michael Foord</b> and <b>Nicola Larosa</b> for ConfigObj (seriously, they should replace ConfigParser with this).<br />
The <b>Oxygen team</b> for the Oxygen icons.<br /><br />

And for those who've contributed, the people whose code I stole, those who helped me out on discussion boards and to open-source creators, <b>Thanks a bunch</b>.<br /><br />

<b>Translators</b><br /><br />

Thank you to the translators below for their contributions.<br /><br />

Dutch (Nederlands) by <b>Fabian Bakkum</b>.<br />
French by <b>Raphaël Rochet</b>.<br />
German by <b>Ralf Sarholz</b>.<br />
Portuguese (Brazilian) by <b>Alan Gomes</b>.<br />
Russian by <b>Viktor Yu. Kovalskiy</b>.<br />
Czech by <b>Pavel Fric</b>.<br />
Spanish by <b>José Vidal</b><br />
Swedish by <b>Åke Engelbrektson</b>
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
        'Qt': qVersion(),
        'Mutagen': mutagen.version_string,
        'PyParsing': get_module_version('pyparsing'),
        'ConfigObj': get_module_version('configobj'),
        'Unidecode': get_module_version('unidecode'),
        'lxml': get_module_version('lxml'),
        'pyacoustid': get_module_version('pyacoustid'),
        'Levenshtein': get_module_version('Levenshtein'),
        'Send2Trash': get_module_version('send2trash'),
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
        label.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))

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
        icon.setPixmap(QPixmap('icons:appicon.svg').scaled(48, 48))
        lib_versions = '<br />'.join(
            ['%s: %s' % (lib, version) for (lib, version) in versions().items()]
        )

        if changeset:
            version = translate('About',
                                "<h2>puddletag {}</h2>Changeset {}"
                                ).format(version_string, changeset)
        else:
            version = translate('About',
                                "<h2>puddletag {}</h2>"
                                ).format(version_string)
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
    app.exec()
