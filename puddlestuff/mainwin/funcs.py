import json
import os
import pickle
from collections import OrderedDict

from PyQt5.QtCore import QByteArray, QMimeData, pyqtSignal, QObject
from PyQt5.QtWidgets import QApplication

from .. import actiondlg
from .. import findfunc
from .. import helperwin
from ..puddleobjects import (PuddleConfig, PuddleDock)

from ..audioinfo import PATH, DIRPATH, FILETAGS, tag_to_json, encode_fn, decode_fn
from .. import musiclib, about as about
from ..util import split_by_tag, translate, to_string
from .. import functions
from .tagtools import *
from ..constants import HOMEDIR

path = os.path

status = {}

_TAGS_MIME_TYPE = 'application/x.puddletag.tags'


def applyaction(files=None, funcs=None):
    if files is None:
        files = status['selectedfiles']
    try:
        if isinstance(funcs[0], findfunc.Macro):
            r = findfunc.apply_macros
        else:
            r = findfunc.apply_actions
    except IndexError:
        return
    state = {'__total_files': str(len(files))}
    state['__files'] = files

    def func():
        for i, f in enumerate(files):
            yield r(funcs, f, state)

    emit('writeaction', func(), None, state)


def applyquickaction(files, funcs):
    if isinstance(funcs[0], findfunc.Macro):
        qa = findfunc.apply_macros
    else:
        qa = findfunc.apply_actions

    selected = status['selectedtags']
    state = {'__total_files': str(len(selected))}
    t = (qa(funcs, f, state, list(s.keys())) for f, s in zip(files, selected))
    emit('writeselected', t)


def auto_numbering(parent=None):
    """Shows the autonumbering wizard and sets the tracks
        numbers should be filled in"""
    tags = status['selectedfiles']
    numtracks = len(tags)

    win = helperwin.AutonumberDialog(parent, 1, numtracks, False)
    win.setModal(True)
    win.newtracks.connect(partial(number_tracks, tags, parent))
    win.show()


def clipboard_to_tag(parent=None):
    win = helperwin.ImportTextFile(parent, clipboard=True)
    win.setModal(True)
    win.patterncombo.addItems(status['patterns'])

    cparser = PuddleConfig()
    last_dir = cparser.get('importwindow', 'lastdir', HOMEDIR)
    win.lastDir = last_dir
    last_pattern = cparser.get('importwindow', 'lastpattern', '')
    if last_pattern:
        win.patterncombo.setEditText(last_pattern)

    def fin_edit(taglist, pattern):
        cparser.set('importwindow', 'lastdir', win.lastDir)
        cparser.set('importwindow', 'lastpattern', pattern)
        emit('writeselected', taglist)

    win.Newtags.connect(fin_edit)

    win.show()


def connect_status(actions):
    connect = lambda a: getattr(obj, a.status).connect(a.setStatusTip)
    actions = [x for x in actions if x.status]
    list(map(connect, actions))


def _setClipboardTags(tags):
    """ Save the given list of tags in the clipboard, both as json and binary. """
    mime = QMimeData()

    binaryData = pickle.dumps(tags)
    mime.setData(_TAGS_MIME_TYPE, binaryData)

    # This is only to support pasting outside of puddletag
    jsonData = json.dumps(list(map(tag_to_json, tags)))
    mime.setText(jsonData)

    QApplication.clipboard().setMimeData(mime)


def copy():
    """ Save the selected tags to the clipboard. """
    selected = status['selectedtags']
    _setClipboardTags(selected)


def copy_whole():
    """ Save all tags of the selected files to the clipboard. """
    tags = []
    mime = QMimeData()

    def usertags(f, images=True):
        ret = f.usertags
        if images and hasattr(f, 'images') and f.images:
            ret.update({'__image': f.images})
        return ret

    tags = [usertags(f) for f in status['selectedfiles']]

    data = json.dumps(list(map(tag_to_json, tags)))

    to_copy = check_copy_data(data)
    if to_copy == 2:
        tags = [usertags(f, False) for f in status['selectedfiles']]
    elif to_copy == 1:
        return

    _setClipboardTags(tags)


def cut():
    """ Copy the selected tags in the clipboard, and set them blank. """
    selected = status['selectedtags']
    _setClipboardTags(selected)

    emit('writeselected', (dict([(z, "") for z in s if z not in FILETAGS])
                           for s in selected))


def check_copy_data(data):
    """ If the given JSON data is bigger than 5MiB, show a dialog.
        Returns 0 if the user wants to copy all, 1 if not, and 2 if
        all except the images."""
    if len(data) > 5 * 1024 * 1024:
        msgbox = QMessageBox()
        msgbox.setText(translate("Messages",
                                 "That's a large amount of data to copy.\n"
                                 "It may cause your system to lock up.\n\n"
                                 "Do you want to go ahead?"))

        msgbox.setIcon(QMessageBox.Question)
        yesBtn = msgbox.addButton(translate("Defaults", "&Yes"),
                                  QMessageBox.YesRole)
        noBtn = msgbox.addButton(translate("Defaults", "No"),
                                 QMessageBox.NoRole)
        msgbox.setDefaultButton(noBtn)
        msgbox.setEscapeButton(noBtn)
        noImgBtn = msgbox.addButton(translate("Messages", "Copy without images."),
                                    QMessageBox.ApplyRole)

        msgbox.exec_()

        if msgbox.clickedButton() is yesBtn:
            return 0
        if msgbox.clickedButton() is noBtn:
            return 1
        elif msgbox.clickedButton() is noImgBtn:
            return 2
    else:
        return 0


def display_tag(tag):
    """Used to display tags in the status bar in a human parseable format."""
    if not tag:
        return "<b>Error: Pattern does not match filename.</b>"
    s = "%s: <b>%s</b>, "
    tostr = lambda i: i if isinstance(i, str) else i[0]
    return "".join([s % (z, tostr(v)) for z, v in tag.items()])[:-2]


def extended_tags(parent=None):
    rows = status['selectedrows']
    win = helperwin.ExTags(files=status['selectedfiles'], parent=parent)
    win.setModal(True)
    win.rowChanged.connect(status['table'].selectRow)
    win.loadSettings()
    x = lambda val: emit('onetomany', val)
    win.extendedtags.connect(x)
    win.show()


def filename_to_tag():
    tags = status['selectedfiles']
    pattern = status['patterntext']

    x = [findfunc.filenametotag(pattern, tag[PATH], True)
         for tag in tags]
    emit('writeselected', x)


def format(parent=None, preview=None):
    """Formats the selected tags."""
    files = status['selectedfiles']
    pattern = status['patterntext']
    selected = status['selectedtags']

    ret = []
    tf = findfunc.tagtofilename

    state = {'__total_files': str(len(files))}
    for i, (audio, s) in enumerate(zip(files, selected)):
        state['__counter'] = str(i + 1)
        val = tf(pattern, audio, state=state)
        ret.append(dict([(tag, val) for tag in s]))
    emit('writeselected', ret)


def in_lib(state, parent=None):
    if state:
        if not status['library']:
            QMessageBox.critical(parent, translate("MusicLib", 'No libraries found'),
                                 translate("MusicLib", "Load a lib first."))
            return False
        files = status['allfiles']
        lib = status['library']
        libartists = status['library'].artists
        to_highlight = []
        for artist, tracks in split_by_tag(files, 'artist', None).items():
            if artist in libartists:
                libtracks = lib.get_tracks('artist', artist)
                titles = [track['title'][0].lower()
                          if 'title' in track else '' for track in libtracks]
                for track in tracks:
                    if track.get('title', [''])[0].lower() in titles:
                        to_highlight.append(track)
        emit('highlight', to_highlight)
        return True
    else:
        emit('highlight', [])
        return False


def load_musiclib(parent=None):
    try:
        m = musiclib.LibChooseDialog(parent)
    except musiclib.MusicLibError:
        QMessageBox.critical(parent, translate("MusicLib", 'No libraries found'),
                             translate("MusicLib", "No supported music libraries were found. Most likely "
                                                   "the required dependencies aren't installed. Visit the "
                                                   "puddletag website, <a href='http://puddletag.sourceforge.net'>"
                                                   "puddletag.sourceforge.net</a> for more details."))
        return
    m.setModal(True)
    m.adddock.connect(emit_received('adddock'))
    m.show()


def _pad(trknum, total, padlen):
    if total is not None:
        text = str(trknum).zfill(padlen) + "/" + str(total).zfill(padlen)
    else:
        text = str(trknum).zfill(padlen)
    return text


def number_tracks(tags, parent, offset, numtracks, restartdirs, padlength, split_field='__dirpath', output_field='track', by_group=False):
    """Numbers the selected tracks sequentially in the range
    between the indexes.
    The first item of indices is the starting track.
    The second item of indices is the number of tracks."""

    if not split_field:
        QMessageBox.critical(parent, translate("Autonumbering Wizard", 'Field empty...'),
                             translate("Autonumbering Wizard",
                                       "The field specified to use as a directory splitter was invalid. "
                                       "Please check your values."))
        return

    if not output_field:
        QMessageBox.critical(parent, translate("Autonumbering Wizard", 'Field empty...'),
                             translate("Autonumbering Wizard",
                                       "The output field specified was invalid. "
                                       "Please check your values."))
        return

    if restartdirs:  # Restart dir numbering
        folders = OrderedDict()
        for tag_index, tag in enumerate(tags):
            key = findfunc.parsefunc(split_field, tag)
            if not isinstance(key, str):
                key = tag.stringtags().get(split_field)

            if key in folders:
                folders[key].append(tag_index)
            else:
                folders[key] = [tag_index]
    else:
        folders = {'fol': [i for i, t in enumerate(tags)]}

    taglist = {}
    for group_num, tags in enumerate(folders.values()):
        if numtracks == -2:
            total = len(tags)
        elif numtracks == -1:
            total = None
        elif numtracks >= 0:
            total = numtracks
        for trknum, index in enumerate(tags):
            if by_group:
                trknum = group_num + offset
            else:
                trknum += offset

            text = _pad(trknum, total, padlength)
            taglist[index] = {output_field: text}

    taglist = [v for k, v in sorted(list(taglist.items()), key=lambda x: x[0])]

    emit('writeselected', taglist)


def _getClipboardTags():
    """ Returns the list of tags from the clipboard (if any) """
    if not QApplication.clipboard().mimeData().hasFormat(_TAGS_MIME_TYPE):
        return None
    binaryData = QApplication.clipboard().mimeData().data(_TAGS_MIME_TYPE).data()
    tags = pickle.loads(binaryData)
    return tags


def paste():
    """ Write tags from the clipboard to the selected files. """
    rows = status['selectedrows']
    if not rows:
        return
    clip = _getClipboardTags()
    if not clip:
        return
    tags = []
    while len(tags) < len(rows):
        tags.extend(clip)
    tags.extend(clip)
    emit('writeselected', tags)


def paste_onto():
    """ Write the tag values from the clipboard into the selected tags. """
    clip = _getClipboardTags()
    if not clip:
        return
    selected = status['selectedtags']
    tags = []
    while len(tags) < len(selected):
        tags.extend(clip)
    emit('writeselected', (dict(list(zip(s, list(cliptag.values()))))
                           for s, cliptag in zip(selected, tags)))


def rename_dirs(parent=None):
    """Changes the directory of the currently selected files, to
    one as per the pattern in self.patterncombo."""
    selectedfiles = status['selectedfiles']
    audio, selected = status['firstselection']
    pattern = status['patterntext']
    if not pattern:
        return

    func = findfunc.Function('tag_dir')
    func.args = [pattern]
    func.tag = ['sthaoeusnthaoeusnthaosnethu']

    run_func(selectedfiles, func)


def run_action(parent=None, quickaction=False):
    files = status['selectedfiles']
    if files:
        example = files[0]
    else:
        example = {}

    if quickaction:
        tags = status['selectedtags'][0]
        win = actiondlg.ActionWindow(parent, example, list(tags.keys()))
    else:
        win = actiondlg.ActionWindow(parent, example)
    win.setModal(True)

    if quickaction:
        func = partial(applyquickaction, files)
        win.donewithmyshit.connect(func)
    else:
        func = partial(applyaction, files)
        win.donewithmyshit.connect(func)
    action_tool = PuddleDock._controls['Actions']
    win.actionOrderChanged.connect(action_tool.updateOrder)
    if not quickaction:
        win.checkedChanged.connect(action_tool.updateChecked)
    win.show()


def run_function(parent=None, prevfunc=None):
    selectedfiles = status['selectedfiles']

    if not prevfunc:
        prevfunc = status['prevfunc']

    example = selectedfiles[0]
    try:
        selected_file = status['selectedtags'][0]
        selected_fields = list(selected_file.keys())
        text = selected_file[selected_fields[0]]
    except IndexError:
        text = example.get('title')

    if prevfunc:
        f = actiondlg.CreateFunction(prevfunc=prevfunc, parent=parent,
                                     selected_fields=selected_fields, example=example, text=text)
    else:
        f = actiondlg.CreateFunction(parent=parent,
                                     selected_fields=selected_fields, example=example, text=text)

    f.valschanged.connect(partial(run_func, selectedfiles))
    f.setModal(True)
    f.show()


def run_func(selectedfiles, func):
    status['prevfunc'] = func
    selectedtags = status['selectedtags']

    function = func.runFunction
    state = {'__total_files': str(len(selectedtags))}

    def tagiter():
        for i, (selected, f) in enumerate(zip(selectedtags, selectedfiles)):
            state['__counter'] = str(i + 1)
            fields = findfunc.parse_field_list(func.tag, f, list(selected.keys()))
            rowtags = f.tags
            ret = {}
            for field in fields:
                val = function(rowtags.get(field, ''), rowtags, state, r_tags=f)
                if val is not None:
                    if hasattr(val, 'items'):
                        ret.update(val)
                    else:
                        ret[field] = val
            yield ret

    emit('writeselected', tagiter())


run_quick_action = lambda parent=None: run_action(parent, True)


def search_replace(parent=None):
    selectedfiles = status['selectedfiles']
    audio, selected = status['firstselection']

    try:
        text = to_string(list(selected.values())[0])
    except IndexError:
        text = translate('Defaults', '')

    func = findfunc.Function('replace')
    func.args = [text, text, False, False]
    func.tag = ['__selected']

    dialog = actiondlg.CreateFunction(prevfunc=func, parent=parent,
                                      selected_fields=list(selected.keys()), example=audio, text=text)

    dialog.valschanged.connect(partial(run_func, selectedfiles))
    dialog.setModal(True)
    dialog.controls[0].combo.setFocus()
    dialog.show()


def show_about(parent=None):
    win = about.AboutPuddletag(parent)
    win.setModal(True)
    win.exec_()


def tag_to_file():
    pattern = status['patterntext']
    files = status['selectedfiles']

    tf = functions.move
    state = {'__total_files': str(len(files))}

    def rename():
        for i, f in enumerate(files):
            state['__counter'] = str(i + 1)
            yield tf(f, pattern, f, state=state)

    emit('writeselected', rename())


def text_file_to_tag(parent=None):
    dirpath = status['selectedfiles'][0].dirpath

    win = helperwin.ImportTextFile(parent)
    cparser = PuddleConfig()
    last_dir = cparser.get('importwindow', 'lastdir', HOMEDIR)
    if win.openFile(dirpath=last_dir):
        win.close()
        return
    win.setModal(True)
    win.patterncombo.addItems(status['patterns'])

    last_pattern = cparser.get('importwindow', 'lastpattern', '')
    if last_pattern:
        win.patterncombo.setEditText(last_pattern)

    def fin_edit(taglist, pattern):
        cparser.set('importwindow', 'lastdir', win.lastDir)
        cparser.set('importwindow', 'lastpattern', pattern)
        emit('writeselected', taglist)

    win.Newtags.connect(fin_edit)
    win.show()


def update_status(enable=True):
    files = status['selectedfiles']
    pattern = status['patterntext']
    tf = lambda *args, **kwargs: encode_fn(findfunc.tagtofilename(*args, **kwargs))
    if not files:
        return
    tag = files[0]

    state = {'__counter': '1', '__total_files': str(len(files))}

    x = findfunc.filenametotag(pattern, tag[PATH], True)
    emit('ftstatus', display_tag(x))

    bold_error = translate("Status Bar", "<b>%s</b>")

    try:
        newfilename = functions.move(tag, pattern, tag, state=state.copy())
        if newfilename:
            newfilename = newfilename['__path']
            emit('tfstatus', translate("Status Bar",
                                       "New Filename: <b>%1</b>").arg(
                decode_fn(newfilename)))
        else:
            emit('tfstatus', '<b>No change</b>')
    except findfunc.ParseError as e:
        emit('tfstatus', bold_error % e.message)

    try:
        newfolder = functions.tag_dir(tag.tags, pattern, tag, state)
        if newfolder:
            newfolder = newfolder['__dirpath']
            dirstatus = translate("Dir Renaming",
                                  "Rename: <b>%1</b> to: <i>%2</i>")
            dirstatus = dirstatus.arg(tag[DIRPATH]).arg(decode_fn(newfolder))
            emit('renamedirstatus', dirstatus)
    except findfunc.ParseError as e:
        emit('renamedirstatus', bold_error % e.message)

    selected = status['selectedtags']
    if not selected:
        emit('formatstatus', display_tag(''))
    else:
        selected = selected[0]
    try:
        val = tf(pattern, tag, state=state.copy())
        newtag = dict([(key, val) for key in selected])
        emit('formatstatus', display_tag(newtag))
    except findfunc.ParseError as e:
        emit('formatstatus', bold_error % e.message)


class _SignalObject(QObject):
    writeselected = pyqtSignal(object, name='writeselected')
    ftstatus = pyqtSignal(str, name='ftstatus')
    tfstatus = pyqtSignal(str, name='tfstatus')
    renamedirstatus = pyqtSignal(str, name='renamedirstatus')
    formatstatus = pyqtSignal(str, name='formatstatus')
    renamedirs = pyqtSignal(list, name='renamedirs')
    onetomany = pyqtSignal(dict, name='onetomany')
    renameselected = pyqtSignal(name='renameselected')
    adddock = pyqtSignal(str, 'QDialog', int, name='adddock')
    highlight = pyqtSignal(list, name='highlight')
    writeaction = pyqtSignal([object, object, dict], name='writeaction')


obj = _SignalObject()
obj.emits = ['writeselected', 'ftstatus', 'tfstatus', 'renamedirstatus',
             'formatstatus', 'renamedirs', 'onetomany', 'renameselected',
             'adddock', 'highlight', 'writeaction']
obj.receives = [('filesselected', update_status),
                ('patternchanged', update_status)]


def emit_received(signal):
    def emit(*args):
        getattr(obj, signal).emit(*args)

    return emit


def emit(sig, *args):
    getattr(obj, sig).emit(*args)
