import os
import time
from unittest.mock import patch

import pytest
from PyQt6.QtWidgets import QApplication

from puddlestuff.puddleobjects import ProgressWin


def test_parallel_loading_loads_files_in_order(mainwin, make_audio, tmp_path, qtbot):
    music = tmp_path / 'music'
    for i in range(12):
        fname = f'{i:02d}.flac'
        make_audio(fname, music, artist='Test Artist', title=f'Track {i:02d}')

    mainwin.openDir(str(music), False)
    model = mainwin._table.model()
    qtbot.waitUntil(lambda: model.rowCount() == 12, timeout=10000)

    loaded_titles = [audio['title'][0] for audio in model.taginfo]
    expected_titles = [f'Track {i:02d}' for i in range(12)]
    assert loaded_titles == expected_titles


def test_parallel_loading_cancel_stops_reads(mainwin, make_audio, tmp_path, qtbot):
    from puddlestuff import tagmodel

    music = tmp_path / 'music_cancel'
    num_files = 80
    for i in range(num_files):
        make_audio(f'{i:02d}.flac', music, artist='Artist', title=f'Song {i:02d}')

    original_gettag = tagmodel.gettag
    call_count = 0

    def slow_gettag(filepath):
        nonlocal call_count
        call_count += 1
        time.sleep(0.08)
        return original_gettag(filepath)

    with patch('puddlestuff.tagmodel.gettag', side_effect=slow_gettag):
        # Trigger openDir
        mainwin.openDir(str(music), False)

        # Wait for ProgressWin to show up
        def find_progress_win():
            for w in QApplication.topLevelWidgets():
                if isinstance(w, ProgressWin) and w.isVisible():
                    return w
            return None

        qtbot.waitUntil(lambda: find_progress_win() is not None, timeout=5000)
        pwin = find_progress_win()

        # Let initial batch start, then cancel
        time.sleep(0.04)
        pwin.cancel()

        # Wait until progress window closes
        qtbot.waitUntil(lambda: not pwin.isVisible(), timeout=5000)

        # Allow worker threads a moment to settle
        time.sleep(0.2)
        count_after_cancel = call_count

        # Verify that reads were dropped and didn't read all 80 files
        assert count_after_cancel < num_files, (
            f"Expected cancel to stop reads, but {count_after_cancel}/{num_files} reads ran"
        )

        # Ensure no further reads occur after cancel
        time.sleep(0.2)
        assert call_count == count_after_cancel, "Threads continued reading after cancel"


def test_parallel_loading_handles_error(mainwin, make_audio, tmp_path, qtbot):
    from puddlestuff import tagmodel

    music = tmp_path / 'music_err'
    for i in range(6):
        make_audio(f'{i:02d}.flac', music, artist='Artist', title=f'Song {i:02d}')

    original_gettag = tagmodel.gettag

    def faulty_gettag(filepath):
        if '02.flac' in filepath:
            raise ValueError('Corrupt file header')
        return original_gettag(filepath)

    with patch('puddlestuff.tagmodel.gettag', side_effect=faulty_gettag):
        mainwin.openDir(str(music), False)
        model = mainwin._table.model()
        qtbot.waitUntil(lambda: model.rowCount() == 5, timeout=10000)

        loaded_titles = [audio['title'][0] for audio in model.taginfo]
        assert 'Song 02' not in loaded_titles
        assert len(loaded_titles) == 5
