import csv
import os
import sys
from os.path import abspath, dirname, normpath
from os.path import join as path_join

from PyQt6.QtWidgets import QFileDialog, QApplication

from . import audioinfo
from .audioinfo.util import lnglength, encode_fn
from .findfunc import tagtofilename


def relpath(target, base):
    try:
        return os.path.relpath(target, base)
    except ValueError:  # another drive, on Windows
        return target


def readm3u(path):
    # From http://forums.fedoraforum.org/showthread.php?p=1224109
    folder = dirname(abspath(path))

    def resolve(entry):
        if os.sep == '/':
            # Playlists written on Windows separate folders with \
            entry = entry.replace('\\', '/')
        return normpath(path_join(folder, entry))

    # List of mp3files
    mp3Files = []

    with open(path, 'r', encoding='utf-8-sig') as fileHandle:
        for line in fileHandle:
            line = line.rstrip('\r\n')
            if not line.strip() or line.startswith('#'):
                # Skip blanks and comments
                continue
            # A name is read as written; one no file has is read as csv quoting
            entry = resolve(line)
            if not os.path.exists(entry):
                quoted = resolve(','.join(next(csv.reader([line]))))
                if os.path.exists(quoted):
                    entry = quoted
            mp3Files.append(entry)

    return mp3Files


def exportm3u(tags, tofile, format=None, reldir=False, winsep=False):
    header = ['#EXTM3U']

    if reldir:
        reldir = os.path.dirname(os.path.abspath(tofile))
        filenames = [relpath(f.filepath, reldir) for f in tags]
    else:
        filenames = [f.filepath for f in tags]

    if winsep:
        filenames = [f.replace('/', '\\') for f in filenames]

    if format is None:
        text = '\n'.join(header + filenames)
    else:
        text = header
        extinfo = ('#EXTINF: %s, %s' % (str(lnglength(f.length)),
                                        encode_fn(tagtofilename(format, f, False))) for f in tags)
        [text.extend([z, y]) for z, y in zip(extinfo, filenames)]
        text = '\n'.join(text)

    with open(tofile, 'w', encoding='utf-8') as playlist:
        playlist.write(text)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    filedlg = QFileDialog()
    filedlg.setFileMode(QFileDialog.FileMode.Directory)
    filedlg.setOption(QFileDialog.Option.ShowDirsOnly)
    filename = str(filedlg.getExistingDirectory(None,
                                                'Open Folder'))
    tags = []
    for z in os.listdir(filename):
        try:
            tag = audioinfo.Tag(os.path.join(filename, z))
            if tag:
                tags.append(tag)
        except Exception as e:
            str(e)
    folder = str(filedlg.getSaveFileName(None,
                                         'Save File'))
    exportm3u(tags, folder)
