import traceback
from functools import partial

from PyQt5.QtWidgets import QMessageBox
from mutagen import id3, apev2

from .. import audioinfo
from ..puddleobjects import progress
from ..translations import translate

id3_tag = audioinfo.id3.Tag
ape_tag = audioinfo.apev2.Tag

all = ['remove_id3', 'remove_apev2']

_delete = {
    'APEv2': apev2.delete,
    'ID3v1': partial(id3.delete, delete_v1=True, delete_v2=False),
    'ID3v2': partial(id3.delete, delete_v1=False, delete_v2=True),
    'ID3': partial(id3.delete, delete_v1=True, delete_v2=True),
}

status = {}


def _remove_tag(f, tag):
    try:
        if tag.startswith('ID3') and isinstance(f, id3_tag):
            status['model'].deleteTag(audio=f, delete=False)
            _delete[tag](f.filepath)
            f.link(f.filepath)
        elif hasattr(f, 'apev2') and f.apev2:
            status['model'].deleteTag(audio=f, delete=True)
            f.link(f.filepath)
        else:
            _delete[tag](f.filepath)
    except:
        traceback.print_exc()
        return


def remove_tag(tag, parent):
    if status['previewmode']:
        QMessageBox.information(parent, 'puddletag',
                                translate("Previews",
                                          'Disable Preview Mode first to enable tag deletion.'))
        return
    files = status['selectedfiles']
    rows = status['selectedrows']

    def func():
        for row, f in zip(rows, files):
            try:
                _remove_tag(f, tag)
                yield None
            except (IOError, OSError) as e:
                filename = f[audioinfo.PATH]
                m = translate("Defaults",
                              'An error occured while writing to <b>%1</b>. (%2)')
                m = m.arg(filename).arg(e.strerror)
                if row == rows[-1]:
                    yield m, 1
                else:
                    yield m, len(rows)
        status['model'].undolevel += 1

    s = progress(func, translate("Tag Tools",
                                 'Removing %s tag: ' % tag), len(files))
    s(parent)


remove_apev2 = lambda parent=None: remove_tag('APEv2', parent)
remove_id3 = lambda parent=None: remove_tag('ID3', parent)
remove_id3v1 = lambda parent=None: remove_tag('ID3v1', parent)
remove_id3v2 = lambda parent=None: remove_tag('ID3v2', parent)


def set_status(stat):
    global status
    status = stat
