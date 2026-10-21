import os

import pytest
from PyQt6.QtWidgets import QCheckBox

from puddlestuff.puddlesettings import SettingsDialog

pytestmark = pytest.mark.ui


def test_mainwin_builds_with_all_docks(mainwin):
    from puddlestuff.puddletag import status
    docks = {'Actions', 'Artwork', 'Filesystem', 'Filter', 'Functions', 'Logs',
             'Mass Tagging', 'Stored Tags', 'Tag Panel', 'Tag Sources'}
    assert docks <= set(status['dialogs'])


def test_open_dir_loads_files_and_tags(mainwin, make_audio, tmp_path, qtbot):
    music = tmp_path / 'music'
    make_audio('01.flac', music, artist='Artist One', title='First')
    make_audio('02.mp3', music, artist='Artist Two', title='Second')

    mainwin.openDir(str(music), False)
    model = mainwin._table.model()
    qtbot.waitUntil(lambda: model.rowCount() == 2)

    loaded = {os.path.basename(audio.filepath): (audio['artist'], audio['title'])
              for audio in model.taginfo}
    assert loaded == {'01.flac': (['Artist One'], ['First']),
                      '02.mp3': (['Artist Two'], ['Second'])}


def test_open_dir_with_non_ascii_folder_names(mainwin, make_audio, tmp_path, qtbot, user):
    # menus.txt: "Imports a folder into puddletag. All files with
    # supported/valid tags are read. Reading subfolders is turned off by
    # default (use the Preferences dialog to enable)." preferences.txt:
    # "Subfolders: If checked, Subfolders of directories selected for
    # import will be checked for supported files". #398 reports folders
    # with a Λ aren't searched. Synthetic names.
    music = tmp_path / 'Λ folder'
    make_audio('01.mp3', music, artist='Artist One', title='First')
    make_audio('02 Λ.mp3', tmp_path / 'Λ' / 'sub', artist='Artist Two', title='Second')

    user.click_menu('&Preferences')
    qtbot.waitUntil(lambda: any(w.isVisible() for w in mainwin.findChildren(SettingsDialog)))
    [window] = [w for w in mainwin.findChildren(SettingsDialog) if w.isVisible()]
    user.activate(window)
    [box] = [c for c in window.findChildren(QCheckBox) if c.text() == 'Su&bfolders']
    if not box.isChecked():
        user.click(box)
    assert box.isChecked()
    user.click(window.okbuttons.okButton)
    qtbot.waitUntil(lambda: not window.isVisible())
    user.activate()

    mainwin.openDir(str(music), False)
    model = mainwin._table.model()
    qtbot.waitUntil(lambda: model.rowCount() == 1)
    assert [audio.filepath for audio in model.taginfo] == [str(music / '01.mp3')]

    mainwin.openDir(str(tmp_path / 'Λ'), False)
    qtbot.waitUntil(lambda: model.rowCount() == 1 and model.taginfo[0]['title'] == ['Second'])
    assert [audio.filepath for audio in model.taginfo] == [str(tmp_path / 'Λ' / 'sub' / '02 Λ.mp3')]
