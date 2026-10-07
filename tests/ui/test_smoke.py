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
