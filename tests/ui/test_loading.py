"""Opening a folder reads its files several at a time. menus.txt, Open
Folder: "All files with supported/valid tags are read." news.txt: "The
initial reading of a directory can be canceled now", and "Clicking Cancel
while loading or saving now actually works as expected and instantly."

Synthetic files; a share that stops answering is a read that waits.
"""
import os
import shutil
import threading

import pytest
from PyQt6.QtWidgets import QApplication, QPushButton

from puddlestuff import tagmodel
from puddlestuff.puddleobjects import ProgressWin

pytestmark = pytest.mark.ui

FILES = 40  # more than are read at once


def test_open_dir_lists_every_file_and_skips_a_broken_one(mainwin, make_audio, tmp_path, qtbot):
    music = tmp_path / 'music'
    for i in range(FILES):
        make_audio(f'{i:02d}.flac', music, title=f'Song {i:02d}')
    (music / 'broken.flac').write_text('not a FLAC file')

    mainwin.openDir(str(music), False)
    model = mainwin._table.model()
    qtbot.waitUntil(lambda: model.rowCount() > 0)

    assert {os.path.basename(audio.filepath): audio['title'] for audio in model.taginfo} == \
        {f'{i:02d}.flac': [f'Song {i:02d}'] for i in range(FILES)}


def test_cancel_lists_the_files_read_and_reads_no_more(mainwin, make_audio, tmp_path, qtbot, user,
                                                       monkeypatch):
    music = tmp_path / 'music'
    first = make_audio('00.flac', music, title='Song')
    for i in range(1, FILES):
        shutil.copy(first, music / f'{i:02d}.flac')

    started, read, lock, answer = [], [], threading.Lock(), threading.Event()
    gettag = tagmodel.gettag

    def read_from_share(filename):
        with lock:
            started.append(filename)
            waits = len(started) > 3
        if waits:
            answer.wait(30)
        tag = gettag(filename)
        with lock:
            read.append(filename)
        return tag

    monkeypatch.setattr(tagmodel, 'gettag', read_from_share)
    try:
        mainwin.openDir(str(music), False)
        qtbot.waitUntil(lambda: len(read) == 3)
        [window] = [w for w in QApplication.topLevelWidgets() if isinstance(w, ProgressWin) and w.isVisible()]
        [cancel] = [b for b in window.findChildren(QPushButton) if b.text() == 'Cancel']
        user.click(cancel)

        model = mainwin._table.model()
        qtbot.waitUntil(lambda: model.rowCount() == 3)  # while the other reads still wait
        assert not window.isVisible()
        assert sorted(audio.filepath for audio in model.taginfo) == sorted(read)
        waiting = len(started)
    finally:
        answer.set()

    qtbot.waitUntil(lambda: len(read) == len(started))
    assert (len(started), model.rowCount()) == (waiting, 3)
    assert waiting < FILES
