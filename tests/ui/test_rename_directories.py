"""Rename Directories (the Convert menu, menus.txt), run from the main window
on the selected files: "Renames the selected files' directories based on the
pattern in Pattern Combo. It's also a shortcut for Tag->Dir." Synthetic
files; their tags are function.txt's examples.
"""
import pytest

from puddlestuff.mainwin import funcs
from puddlestuff.mainwin.patterncombo import PatternCombo

pytestmark = pytest.mark.ui


def test_rename_directories(mainwin, make_audio, tmp_path, qtbot):
    # tut2.txt: "if the Pattern Combo contained, %artist% - %album%, it would
    # behave the same way as file renaming (except on the directory)". Two
    # of the three files share a folder, which is renamed once.
    music = tmp_path / 'music'
    for folder, name, artist, album in [('other', '03.mp3', 'Before The Fame', 'The Vinyl LP'),
                                        ('unsorted', '01.mp3', 'Relatively Unknown', 'Fans like it'),
                                        ('unsorted', '02.mp3', 'Relatively Unknown', 'Fans like it')]:
        make_audio(name, music / folder, artist=artist, album=album, title=name)
    mainwin.openDir(str(music), False)
    model = mainwin._table.model()
    qtbot.waitUntil(lambda: model.rowCount() == 3)
    mainwin._table.selectAll()
    qtbot.waitUntil(lambda: len(mainwin._table.selectedRows) == 3)
    mainwin.findChild(PatternCombo).setEditText('%artist% - %album%')
    funcs.rename_dirs(mainwin)
    expected = [str(music / path) for path in ['Before The Fame - The Vinyl LP/03.mp3',
                                               'Relatively Unknown - Fans like it/01.mp3',
                                               'Relatively Unknown - Fans like it/02.mp3']]
    qtbot.waitUntil(lambda: sorted(audio.filepath for audio in model.taginfo) == expected)
    assert sorted(str(path) for path in music.rglob('*.mp3')) == expected
