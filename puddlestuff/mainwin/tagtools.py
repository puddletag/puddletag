import traceback
from functools import partial

from PyQt6.QtWidgets import QMessageBox
from mutagen import id3, apev2

from .. import audioinfo
from ..puddleobjects import progress
from ..translations import translate

id3_tag = audioinfo.id3.Tag
# AIFF, DSF and DSDIFF keep their ID3v2 tag in a chunk, which only their
# own delete finds.
id3_chunk_tags = tuple(tag for filetype, tag, name, ext in audioinfo.id3.filetypes if tag is not id3_tag)
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
    """Removes tag from f. Returns whether the table recorded an undo step."""
    undoable = False
    try:
        if tag.startswith('ID3') and isinstance(f, id3_tag):
            status['model'].deleteTag(audio=f, delete=False)
            undoable = True
            _delete[tag](f.filepath)
            f.link(f.filepath)
        elif tag in ('ID3', 'ID3v2') and isinstance(f, id3_chunk_tags):
            status['model'].deleteTag(audio=f, delete=True)
            undoable = True
            f.link(f.filepath)
        elif tag == 'APEv2' and getattr(f, 'apev2', False):
            status['model'].deleteTag(audio=f, delete=True)
            undoable = True
            f.link(f.filepath)
        else:
            _delete[tag](f.filepath)
    except:
        traceback.print_exc()
    return undoable


def remove_tag(tag, parent):
    if status['previewmode']:
        QMessageBox.information(parent, 'puddletag',
                                translate("Previews",
                                          'Disable Preview Mode first to enable tag deletion.'))
        return
    files = status['selectedfiles']
    rows = status['selectedrows']
    undoable = []

    def func():
        for row, f in zip(rows, files):
            try:
                undoable.append(_remove_tag(f, tag))
                yield None
            except (IOError, OSError) as e:
                filename = f[audioinfo.PATH]
                m = translate('Defaults',
                              "An error occured while writing to <b>{}</b>. ({})"
                              ).format(filename, e.strerror)
                if row == rows[-1]:
                    yield m, 1
                else:
                    yield m, len(rows)

    def fin():
        # progress runs only the first step with one file, so the loop
        # never ends there; and a step with no file in it would stop Undo.
        if any(undoable):
            status['model'].undolevel += 1

    s = progress(func, translate("Tag Tools",
                                 'Removing %s tag: ' % tag), len(files), fin)
    s(parent)


remove_apev2 = lambda parent=None: remove_tag('APEv2', parent)
remove_id3 = lambda parent=None: remove_tag('ID3', parent)
remove_id3v1 = lambda parent=None: remove_tag('ID3v1', parent)
remove_id3v2 = lambda parent=None: remove_tag('ID3v2', parent)


def set_status(stat):
    global status
    status = stat
