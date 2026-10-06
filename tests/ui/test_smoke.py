import os

import pytest

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


def test_open_dir_dialog_loads_mp3_folder(mainwin, make_audio, tmp_path, qtbot, dialogs):
    from PyQt6.QtCore import QDir
    from PyQt6.QtWidgets import QFileDialog

    folder = tmp_path / 'MP3'
    make_audio('01.mp3', folder, artist='Artist', title='Track')
    dialogs.answer('QFileDialog.getExistingDirectory', str(folder))
    start = mainwin._lastdir[0] if mainwin._lastdir else QDir.homePath()

    mainwin.openDir()
    model = mainwin._table.model()
    qtbot.waitUntil(lambda: model.rowCount() == 1)

    assert len(dialogs.calls) == 1
    _name, args, kwargs = dialogs.calls[0]
    options = args[3] if len(args) > 3 else kwargs.get('options', QFileDialog.Option.ShowDirsOnly)
    assert options == QFileDialog.Option.ShowDirsOnly
    directory = args[2]
    assert directory == start
    assert os.path.basename(os.path.normpath(directory)) != 'Downloads'


def test_open_dir_cancel_leaves_table_empty(mainwin, dialogs):
    dialogs.answer('QFileDialog.getExistingDirectory', '')
    mainwin.openDir()
    assert mainwin._table.model().rowCount() == 0


def test_append_dir_uses_platform_folder_dialog(mainwin, dialogs):
    from PyQt6.QtWidgets import QFileDialog

    dialogs.answer('QFileDialog.getExistingDirectory', '')
    mainwin.appendDir()
    _name, args, kwargs = dialogs.calls[0]
    options = args[3] if len(args) > 3 else kwargs.get('options', QFileDialog.Option.ShowDirsOnly)
    assert options == QFileDialog.Option.ShowDirsOnly
