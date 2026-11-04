"""The Mass Tagging window (tut5.txt), run as a user runs it: Windows →
Mass Tagging, a profile made in Configure Profiles, the files selected,
Search, then Write Previews. Two synthetic tag sources stand in for the
web ones, so nothing goes to the network. Synthetic files and albums.
"""
import json
import os
import threading
from pathlib import Path

import pytest
from PyQt6.QtCore import QPoint, QThread, Qt
from PyQt6.QtWidgets import QApplication, QMessageBox, QPushButton, QTextEdit

from puddlestuff import audioinfo
from puddlestuff.constants import CONFIGDIR
from puddlestuff.masstag.dialogs import MassTagEdit, MassTagWindow, MTProfileEdit, TSProfileEdit
from puddlestuff.tagsources import RetrievalError, discogs

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
Yes = QMessageBox.StandardButton.Yes


class SyntheticSource:
    """A tag source written as tagsources.txt's example plugin writes one:
    a name, group_by, search() and retrieve(). It answers from the albums a
    test gives it, never from the web. Synthetic albums."""
    name = 'Synthetic Source'
    group_by = ['album', 'artist']

    def search(self, album, artists):
        cls = type(self)
        cls.searches.append((album, sorted(artists)))
        if album in cls.search_errors:
            raise cls.search_errors[album]
        return [(dict(info), [dict(t) for t in tracks] if cls.tracks_in_search else [])
                for info, tracks in cls.albums]

    def retrieve(self, info):
        cls = type(self)
        cls.retrieved.append(info['album'])
        if info['album'] in cls.retrieve_errors:
            raise cls.retrieve_errors[info['album']]
        [tracks] = [tracks for album, tracks in cls.albums if album['album'] == info['album']]
        return info, [dict(t) for t in tracks]


class SecondSource(SyntheticSource):
    name = 'Second Source'


@pytest.fixture(autouse=True)
def sources(clean_profile):
    """Adds the synthetic sources to the list puddletag builds its tag
    sources from, as a plugin's are added. Autouse, so it runs before
    mainwin builds the window."""
    from puddlestuff import tagsources
    for cls in (SecondSource, SyntheticSource):
        cls.albums = []  # (album info, tracks) pairs, as search() returns them
        cls.retrieve_errors = {}  # album name: the exception retrieve() raises
        cls.retrieved = []
        cls.search_errors = {}  # searched album name: the exception search() raises
        cls.searches = []
        cls.tracks_in_search = False
    tagsources.tagsources.extend([SecondSource, SyntheticSource])
    yield
    tagsources.tagsources.remove(SecondSource)
    tagsources.tagsources.remove(SyntheticSource)


def tracks(count=3, **fields):
    """Synthetic tracks titled 'Song 1', 'Song 2', ... numbered 1, 2, ...,
    each with these fields."""
    return [dict(fields, title=f'Song {n}', track=str(n)) for n in range(1, count + 1)]


def album_files(make_audio, folder, count=3, **tags):
    """Synthetic MP3s 01.mp3, 02.mp3, ... in folder, titled 'Song 1', ...
    and numbered 1, 2, ..., each with these tags."""
    return [make_audio(f'0{n}.mp3', folder, title=f'Song {n}', tracknumber=str(n), **tags)
            for n in range(1, count + 1)]


def load(mainwin, qtbot, folder, count):
    mainwin.openDir(str(folder), False)
    qtbot.waitUntil(lambda: mainwin._table.model().rowCount() == count)


def in_file(path):
    return audioinfo.usertags(audioinfo.Tag(str(path)))


def previews(mainwin):
    """Each file's preview, by path."""
    return {audio.filepath: dict(audio.preview) for audio in mainwin._table.model().taginfo}


def shown(user, path, field):
    """The cell's text for this file and field, and how it's shown: bold,
    italic or plain."""
    model = user.table.model()
    [row] = [n for n, audio in enumerate(model.taginfo) if audio.filepath == str(path)]
    index = user.cell(row, field)
    font = model.data(index, Qt.ItemDataRole.FontRole)
    return model.data(index), 'bold' if font.bold() else 'italic' if font.italic() else 'plain'


def button(widget, text):
    """The button with this text in widget's own window, not in a dialog
    it opened earlier (closed dialogs stay its children)."""
    [found] = [b for b in widget.findChildren(QPushButton)
               if b.text() == text and b.window() is widget.window()]
    return found


def opened(qtbot, kind):
    qtbot.waitUntil(lambda: isinstance(QApplication.activeModalWidget(), kind))
    return QApplication.activeModalWidget()


def pick(user, qtbot, combo, text):
    row = combo.findText(text, Qt.MatchFlag.MatchFixedString)
    assert row != -1, text
    user.click(combo)
    view = combo.view()
    qtbot.waitUntil(view.isVisible)
    # A second click inside the double-click interval is read as one.
    qtbot.wait(QApplication.doubleClickInterval() + 100)
    index = combo.model().index(row, 0)
    view.scrollTo(index)
    user.click(view.viewport(), view.visualRect(index).center())
    qtbot.waitUntil(lambda: not view.isVisible())
    assert combo.currentIndex() == row


def replace_text(user, box, text):
    """Clicks into a text or number box, selects what's there and types
    text."""
    user.click(box)
    user.press(Key.Key_A, Ctrl)
    user.type(text)


def open_mass_tagging(user, mainwin, qtbot):
    """Windows → Mass Tagging (menus.txt: "See the Masstagging Tutorial")."""
    user.click_menu('Mass Tagging')
    [window] = mainwin.findChildren(MassTagWindow)
    qtbot.waitUntil(window.isVisible)
    return window


def create_profile(user, qtbot, window, name, sources, album=None, brute_force=False,
                   match=None, pattern=None, track=None, update_empty=False):
    """tut5.txt's steps: Configure Profiles, Add Profile ("+"), the
    profile's name, Add Tag Source ("+") for each source with its options,
    the profile's options, then OK in each dialog. sources: one dict per
    tag source in polling order, with 'source' (its name) and optionally
    'fields', 'if_no_results' and 'replace'. An option left None keeps the
    dialog's default; brute_force and update_empty check their box."""
    user.click(button(window, '&Configure Profiles'))
    profiles = opened(qtbot, MassTagEdit)
    count = profiles.listbox.count()
    user.click(profiles.buttonlist.addButton)
    editor = opened(qtbot, MTProfileEdit)
    user.activate(editor)
    replace_text(user, editor._name, name)
    for source in sources:
        user.click(editor.buttonlist.addButton)
        config = opened(qtbot, TSProfileEdit)
        user.activate(config)
        pick(user, qtbot, config.source, source['source'])
        if 'fields' in source:
            replace_text(user, config.fields, source['fields'])
        if 'if_no_results' in source:
            pick(user, qtbot, config.no_match, source['if_no_results'])
        if 'replace' in source:
            replace_text(user, config.replace_fields, source['replace'])
        user.click(button(config, 'OK'))
        qtbot.waitUntil(lambda: QApplication.activeModalWidget() is editor)
        user.activate(editor)
    for box, text in ((editor.albumBound, album), (editor.matchFields, match),
                      (editor.pattern, pattern), (editor.trackBound, track)):
        if text is not None:
            replace_text(user, box, str(text))
    for box, ticked in ((editor.jfdi, brute_force), (editor.existing, update_empty)):
        if ticked:
            # On the label: the box is wider than its text, and a click on
            # its centre lands past a short label's end.
            user.click(box, QPoint(30, box.height() // 2))
    user.click(button(editor, 'OK'))
    qtbot.waitUntil(lambda: profiles.listbox.count() == count + 1)
    user.click(button(profiles, 'OK'))
    qtbot.waitUntil(lambda: window.profileCombo.findText(name) != -1)


def search(user, qtbot, mainwin, window):
    """Selects every file and clicks Search, then waits until the run ends:
    its log's last line. Returns the log."""
    user.activate()
    mainwin._table.setFocus()
    user.press(Key.Key_A, Ctrl)
    user.click(button(window, '&Search'))
    [log] = window.findChildren(QTextEdit)
    qtbot.waitUntil(lambda: 'Lookups completed.' in log.toPlainText(), timeout=10000)
    return log.toPlainText()


ALBUM_A = {'album': 'Album A', 'artist': 'Artist A'}


def load_album_a(make_audio, mainwin, qtbot, tmp_path):
    """Three synthetic files of Album A, loaded."""
    files = album_files(make_audio, tmp_path / 'music' / 'Artist A - Album A', **ALBUM_A)
    load(mainwin, qtbot, tmp_path / 'music', 3)
    return files


def synthetic_album(make_audio, mainwin, qtbot, tmp_path):
    """The files of Album A, loaded, and the source that knows the album."""
    files = load_album_a(make_audio, mainwin, qtbot, tmp_path)
    SyntheticSource.albums = [(ALBUM_A, tracks(genre='Synth'))]
    return files


def run_album(user, qtbot, mainwin, make_audio, tmp_path, **profile):
    """The files of Album A loaded, and a profile made with these options
    for the Synthetic Source. Returns the window and the files."""
    files = load_album_a(make_audio, mainwin, qtbot, tmp_path)
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic', [{'source': 'Synthetic Source'}], **profile)
    return window, files


@pytest.fixture
def album(mainwin, make_audio, tmp_path, qtbot, user):
    """The files of Album A, loaded, and the Mass Tagging window."""
    files = load_album_a(make_audio, mainwin, qtbot, tmp_path)
    return files, open_mass_tagging(user, mainwin, qtbot)


def run_two_sources(user, qtbot, mainwin, window, second):
    """A profile polling Synthetic Source, then Second Source with these
    options, selected and searched."""
    create_profile(user, qtbot, window, 'Synthetic',
                   [{'source': 'Synthetic Source'}, dict(second, source='Second Source')])
    pick(user, qtbot, window.profileCombo, 'Synthetic')
    search(user, qtbot, mainwin, window)


def no_previews(mainwin):
    assert not mainwin._table.model().previewMode
    assert all(preview == {} for preview in previews(mainwin).values())


def write_previews(user, window):
    user.activate()
    user.click(button(window, '&Write Previews'))


def click_item(user, listbox, row):
    """Selects the profile or source listed in this row."""
    user.click(listbox.viewport(), listbox.visualItemRect(listbox.item(row)).center())


# "Masstagging: See the Masstagging Tutorial" (menus.txt:347-349) and
# "Click Configure Profiles on the Masstagging window" (tut5:38).

def test_windows_menu_opens_mass_tagging(mainwin, user, qtbot):
    window = open_mass_tagging(user, mainwin, qtbot)
    assert window.isVisible()
    assert button(window, '&Configure Profiles')
    assert button(window, '&Search')


# "Click Configure Profiles… add a new profile by clicking on the Add
# Profile ("+") button" (tut5:38-44), "Name: The name of the profile."
# (tut5:50-58), "Clicking on the Add Tag Source ("+") button" (tut5:112),
# "Source: The tag source to use." (tut5:152-154).

def test_configure_profiles_adds_a_profile(mainwin, user, qtbot):
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic', [{'source': 'Synthetic Source'}])
    assert window.profileCombo.currentText() == 'Synthetic'
    user.click(button(window, '&Configure Profiles'))
    profiles = opened(qtbot, MassTagEdit)
    assert profiles.listbox.item(0).text() == 'Synthetic'
    user.click(button(profiles, 'Cancel'))


# "Select a profile… Select files. Click on start. Wait until it's done."
# (tut5:25-28), "When done and if matches were found, the metadata will be
# applied to the files and puddletag will be in Preview Mode" (tut5:20).
# Synthetic files and album.

def test_search_previews_the_matching_album(mainwin, make_audio, user, qtbot, tmp_path):
    files = synthetic_album(make_audio, mainwin, qtbot, tmp_path)
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic', [{'source': 'Synthetic Source'}])
    pick(user, qtbot, window.profileCombo, 'Synthetic')
    search(user, qtbot, mainwin, window)
    assert mainwin._table.model().previewMode
    for f in files:
        assert shown(user, f, 'genre') == ('Synth', 'bold')
        assert previews(mainwin)[str(f)]['genre'] == ['Synth']
        assert 'genre' not in in_file(f)


# "Make modifications. Write changes." (tut5:29-30); the window's button
# for it is Write Previews. Synthetic files and album.

def test_write_previews_writes_the_retrieved_tags(mainwin, make_audio, user, qtbot, tmp_path):
    files = synthetic_album(make_audio, mainwin, qtbot, tmp_path)
    titles = [in_file(f)['title'] for f in files]
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic', [{'source': 'Synthetic Source'}])
    pick(user, qtbot, window.profileCombo, 'Synthetic')
    search(user, qtbot, mainwin, window)
    model = mainwin._table.model()
    [row] = [n for n, audio in enumerate(model.taginfo) if audio.filepath == str(files[0])]
    user.double_click_cell(user.cell(row, 'genre'))
    QApplication.focusWidget().selectAll()
    user.type('Edited')
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: shown(user, files[0], 'genre')[0] == 'Edited')
    write_previews(user, window)
    qtbot.waitUntil(lambda: [in_file(f).get('genre') for f in files]
                    == [['Edited'], ['Synth'], ['Synth']])
    assert not model.previewMode
    assert [in_file(f)['title'] for f in files] == titles


# "puddletag will take the files you selected, separate them into
# directories and sequentially process each directory." (tut5:9), "if the
# album field differs between each files in a directory, they'll be split
# again" (tut5:14). Synthetic files and albums.

def test_files_are_split_by_folder_and_album(mainwin, make_audio, user, qtbot, tmp_path):
    music = tmp_path / 'music'
    one = [make_audio(f'0{n}.mp3', music / 'One', artist='Artist A', album='Album A',
                      title=f'Song {n}', tracknumber=str(n)) for n in (1, 2)]
    third = make_audio('03.mp3', music / 'One', artist='Artist C', album='Album C',
                       title='Song 1', tracknumber='1')
    two = [make_audio(f'0{n}.mp3', music / 'Two', artist='Artist B', album='Album B',
                      title=f'Song {n}', tracknumber=str(n)) for n in (1, 2)]
    files = one + [third] + two
    before = [in_file(f) for f in files]
    load(mainwin, qtbot, music, 5)
    SyntheticSource.albums = [
        ({'album': 'Album A', 'artist': 'Artist A'}, tracks(2, artist='Artist A', genre='GA')),
        ({'album': 'Album B', 'artist': 'Artist B'}, tracks(2, artist='Artist B', genre='GB')),
        ({'album': 'Album C', 'artist': 'Artist C'}, tracks(1, artist='Artist C', genre='GC')),
    ]
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic', [{'source': 'Synthetic Source'}])
    search(user, qtbot, mainwin, window)
    assert sorted(SyntheticSource.searches) == [
        ('Album A', ['Artist A']), ('Album B', ['Artist B']), ('Album C', ['Artist C'])]
    genres = {str(f): [genre] for f, genre in zip(files, ('GA', 'GA', 'GC', 'GB', 'GB'))}
    assert {path: p['genre'] for path, p in previews(mainwin).items()} == genres
    assert [in_file(f) for f in files] == before


# "A File->Tag operation will be applied to each file. Any fields that
# aren't present in the file will be filled using those results." (tut5:15),
# "All these changes are kept in memory and nothing is written to the file."
# (tut5:76). Synthetic files and album.

def test_filename_pattern_fills_fields_missing_from_the_files(mainwin, make_audio, user, qtbot,
                                                              tmp_path):
    folder = tmp_path / 'music' / 'Artist A - Album A'
    files = [make_audio(f'0{n} - Song {n}.mp3', folder) for n in (1, 2, 3)]
    load(mainwin, qtbot, tmp_path / 'music', 3)
    SyntheticSource.albums = [({'album': 'Album A', 'artist': 'Artist A'}, tracks(genre='Synth'))]
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic', [{'source': 'Synthetic Source'}])
    search(user, qtbot, mainwin, window)
    assert SyntheticSource.searches == [('Album A', ['Artist A'])]
    for n, f in enumerate(files, 1):
        preview = previews(mainwin)[str(f)]
        assert preview['title'] == [f'Song {n}']
        assert preview['genre'] == ['Synth']
        assert in_file(f) == {}


def test_album_below_the_album_percentage_is_not_matched(
        mainwin, make_audio, tmp_path, qtbot, user):
    # tut5:80-82: "Minimum percentage required for album matches. An album
    # will be considered a match if the percentage by which the album name
    # and artist differ for the album is less than what's specified here."
    # Synthetic files and albums; the source's search returns no tracks.
    SyntheticSource.albums = [({'album': 'Xxxxx Yyyy', 'artist': 'Zzz Qqq'}, tracks(genre='Synth'))]
    window, files = run_album(user, qtbot, mainwin, make_audio, tmp_path)
    search(user, qtbot, mainwin, window)
    no_previews(mainwin)
    assert SyntheticSource.retrieved == []
    assert [in_file(p).get('genre') for p in files] == [None] * 3


def test_tracks_are_matched_by_the_match_fields(mainwin, make_audio, tmp_path, qtbot, user):
    # tut5:85-91: "For a matching album, each retrieved track will be
    # checked against the files... each field will be compared... and the
    # field with the lowest match percentage will be used". tut5:93-95: "If
    # a track has a Match Percentage higher or equal to this... that track
    # will be considered a match." Synthetic files and albums, the tracks
    # listed in reverse.
    SyntheticSource.albums = [({'album': 'Album A', 'artist': 'Artist A'}, [
        {'genre': 'G3', 'title': 'Song 3', 'track': '3'},
        {'genre': 'G2', 'title': 'Song 2', 'track': '2'},
        {'genre': 'G1', 'title': 'Song 1', 'track': '1'}])]
    window, files = run_album(user, qtbot, mainwin, make_audio, tmp_path)
    search(user, qtbot, mainwin, window)
    shown_previews = previews(mainwin)
    assert [shown_previews[str(p)]['genre'] for p in files] == [['G1'], ['G2'], ['G3']]


def test_track_below_the_track_percentage_is_left_alone(
        mainwin, make_audio, tmp_path, qtbot, user):
    # tut5:93-95: "If a track has a Match Percentage higher or equal to
    # this... that track will be considered a match." Synthetic files and
    # albums; the retrieved titles differ from the files'.
    SyntheticSource.albums = [({'album': 'Album A', 'artist': 'Artist A'},
                               [dict(t, title=f'Other {t["track"]}') for t in tracks(genre='Synth')])]
    window, files = run_album(user, qtbot, mainwin, make_audio, tmp_path)
    search(user, qtbot, mainwin, window)
    no_previews(mainwin)


def test_brute_force_pairs_unmatched_files_by_track(mainwin, make_audio, tmp_path, qtbot, user):
    # tut5:99-101, under "Tag Sources": "Check to enable brute force
    # matching. If no matches were found for some files, then the files
    # will be sorted by track... Each retrieved track will then be paired
    # with a file (in order)". Synthetic files and albums.
    SyntheticSource.albums = [({'album': 'Album A', 'artist': 'Artist A'},
                               [dict(t, title=f'Other {4 - int(t["track"])}')
                                for t in tracks(genre='Synth')])]
    window, files = run_album(user, qtbot, mainwin, make_audio, tmp_path, brute_force=True)
    search(user, qtbot, mainwin, window)
    shown_previews = previews(mainwin)
    assert [shown_previews[str(p)]['title'] for p in files] == [['Other 3'], ['Other 2'], ['Other 1']]


def test_update_empty_fields_only(mainwin, make_audio, tmp_path, qtbot, user):
    # tut5:103-105, under "Brute force unmatched files.": "If checked, only
    # fields that don't already have values will be updated with retrieved
    # data." Synthetic files and albums; the files have no genre.
    SyntheticSource.albums = [({'album': 'Album A', 'artist': 'Artist A'},
                               [dict(t, title=f'New {t["track"]}') for t in tracks(genre='Synth')])]
    window, files = run_album(user, qtbot, mainwin, make_audio, tmp_path,
                              brute_force=True, update_empty=True)
    search(user, qtbot, mainwin, window)
    for preview in previews(mainwin).values():
        assert preview['genre'] == ['Synth']
        assert 'title' not in preview
    write_previews(user, window)
    qtbot.waitUntil(lambda: all(in_file(p).get('genre') == ['Synth'] for p in files))
    assert [in_file(p)['title'] for p in files] == [['Song 1'], ['Song 2'], ['Song 3']]


def test_best_matching_album_is_retrieved(mainwin, make_audio, tmp_path, qtbot, user):
    # tut5:17: "checked for a matching album within the bounds specified."
    # Synthetic files and albums; both names pass the album percentage.
    SyntheticSource.albums = [
        ({'album': 'Album A (Deluxe)', 'artist': 'Artist A'}, tracks(genre='Deluxe')),
        ({'album': 'Album A', 'artist': 'Artist A'}, tracks(genre='Plain'))]
    window, files = run_album(user, qtbot, mainwin, make_audio, tmp_path)
    search(user, qtbot, mainwin, window)
    assert SyntheticSource.retrieved == ['Album A']
    shown_previews = previews(mainwin)
    assert [shown_previews[str(p)]['genre'] for p in files] == [['Plain']] * 3


def test_track_at_exactly_the_track_percentage_matches(
        mainwin, make_audio, tmp_path, qtbot, user):
    # tut5:95: "If a track has a Match Percentage higher or equal to
    # this... that track will be considered a match." Synthetic files and
    # albums; the titles are identical, so the score is exactly 100.
    SyntheticSource.albums = [({'album': 'Album A', 'artist': 'Artist A'}, tracks(genre='Synth'))]
    window, files = run_album(user, qtbot, mainwin, make_audio, tmp_path, track=100)
    search(user, qtbot, mainwin, window)
    shown_previews = previews(mainwin)
    assert [shown_previews[str(p)].get('genre') for p in files] == [['Synth']] * 3


def test_album_with_as_many_tracks_as_files_matches_whatever_its_name(
        mainwin, make_audio, tmp_path, qtbot, user):
    # tut5:84: "A search result that already has as many tracks as the files
    # you selected is also considered a match, whatever its album name and
    # artist." Synthetic files and albums. Brute force is ticked so the
    # tracks are paired with the files whatever their titles.
    SyntheticSource.tracks_in_search = True
    SyntheticSource.albums = [({'album': 'Xxxxx Yyyy', 'artist': 'Zzz Qqq'}, tracks(genre='Wrong'))]
    window, files = run_album(user, qtbot, mainwin, make_audio, tmp_path, brute_force=True)
    search(user, qtbot, mainwin, window)
    assert SyntheticSource.retrieved == ['Xxxxx Yyyy']
    shown_previews = previews(mainwin)
    assert [shown_previews[str(p)]['album'] for p in files] == [['Xxxxx Yyyy']] * 3
    assert [shown_previews[str(p)]['genre'] for p in files] == [['Wrong']] * 3


# "Fields from different tag sources will be combined into multiple values
# where they differ." (tut5.txt) "The tag source polled last takes
# precedence… Since Discogs was polled last it's values will be listed
# first". Synthetic files and albums.

def test_values_from_both_sources_are_combined_last_polled_first(
        mainwin, user, album, qtbot):
    files, window = album
    SyntheticSource.albums = [(ALBUM_A, tracks(genre='Dance'))]
    SecondSource.albums = [(ALBUM_A, tracks(genre='Kwaito'))]
    run_two_sources(user, qtbot, mainwin, window, {})
    for n, f in enumerate(files, 1):
        assert previews(mainwin)[str(f)]['genre'] == ['Kwaito', 'Dance']
        assert previews(mainwin)[str(f)]['title'] == [f'Song {n}']
    write_previews(user, window)
    qtbot.waitUntil(lambda: all(in_file(f).get('genre') == ['Kwaito', 'Dance'] for f in files))


# "A comma-separated list of fields that takes precedence. Any listed here
# will replace any previous results retrieved." (tut5.txt) Synthetic files
# and albums.

def test_fields_to_replace_take_precedence(mainwin, user, album, qtbot):
    files, window = album
    SyntheticSource.albums = [(ALBUM_A, tracks(genre='Dance'))]
    SecondSource.albums = [(ALBUM_A, tracks(genre='Kwaito'))]
    run_two_sources(user, qtbot, mainwin, window, {'replace': 'genre'})
    for f in files:
        assert shown(user, f, 'genre') == ('Kwaito', 'bold')
    write_previews(user, window)
    qtbot.waitUntil(lambda: all(in_file(f).get('genre') == ['Kwaito'] for f in files))


# "Fields: The list of fields to retrieve from the tag source." (tut5.txt)
# Brute force pairs the tracks, which cut to genre can't match on artist
# and title. Synthetic files and albums.

def test_fields_limit_what_is_retrieved(mainwin, user, album, qtbot):
    files, window = album
    SyntheticSource.albums = [(ALBUM_A, tracks(genre='Synth'))]
    create_profile(user, qtbot, window, 'Synthetic',
                   [{'source': 'Synthetic Source', 'fields': 'genre'}], brute_force=True)
    pick(user, qtbot, window.profileCombo, 'Synthetic')
    search(user, qtbot, mainwin, window)
    for f in files:
        preview = previews(mainwin)[str(f)]
        assert preview['genre'] == ['Synth']
        assert not {'album', 'artist', 'title'} & preview.keys()


# "If no matching album was found for this tag source, you can choose to
# either Continue with the other tag sources in the list or Stop the lookup
# and use any previously retrieved results." (tut5.txt) Synthetic files and
# albums.

def test_stop_ends_the_lookup_when_a_source_finds_nothing(mainwin, user, album, qtbot):
    files, window = album
    SecondSource.albums = [(ALBUM_A, tracks(genre='Two'))]
    create_profile(user, qtbot, window, 'Synthetic',
                   [{'source': 'Synthetic Source', 'if_no_results': 'Stop'},
                    {'source': 'Second Source'}])
    pick(user, qtbot, window.profileCombo, 'Synthetic')
    search(user, qtbot, mainwin, window)
    assert SecondSource.searches == []
    no_previews(mainwin)


# "If a match wasn't found for one Tag Source, but for another the Tag
# Source will be polled again using the data retrieved from the matching
# source." (tut5.txt) Synthetic files and albums; 'AA' is a synthetic
# abbreviation.

def test_source_without_a_match_is_polled_again_with_the_found_data(
        mainwin, user, make_audio, tmp_path, qtbot):
    files = album_files(make_audio, tmp_path / 'music' / 'AA - Album A',
                        artist='AA', album='Album A')
    load(mainwin, qtbot, tmp_path / 'music', 3)
    SyntheticSource.albums = [({'album': 'Album A', 'artist': 'Artist Alpha'},
                               tracks(genre='One'))]
    SecondSource.albums = [({'album': 'Album A', 'artist': 'AA'},
                            tracks(artist='Artist Alpha'))]
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic',
                   [{'source': 'Synthetic Source'}, {'source': 'Second Source'}], match='title')
    pick(user, qtbot, window.profileCombo, 'Synthetic')
    search(user, qtbot, mainwin, window)
    assert SyntheticSource.searches == [('Album A', ['AA']), ('Album A', ['Artist Alpha'])]
    for f in files:
        assert previews(mainwin)[str(f)]['artist'] == ['Artist Alpha']
        assert previews(mainwin)[str(f)]['genre'] == ['One']


def test_retrieval_error_while_searching_is_logged(mainwin, make_audio, tmp_path, qtbot, user):
    # tagsources.txt's example plugin: "Raise puddlestuff.tagsources.RetrievalError
    # if an error occurs." Synthetic files and album.
    album_files(make_audio, tmp_path / 'music' / 'Artist A - Album A',
                artist='Artist A', album='Album A')
    load(mainwin, qtbot, tmp_path / 'music', 3)
    SyntheticSource.albums = [({'album': 'Album A', 'artist': 'Artist A'}, tracks(genre='Synth'))]
    SyntheticSource.search_errors = {'Album A': RetrievalError('synthetic search failure')}
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic', [{'source': 'Synthetic Source'}])

    log = search(user, qtbot, mainwin, window)

    assert 'An error occurred during the search: synthetic search failure' in log
    assert 'No valid matches were found for the album.' in log
    no_previews(mainwin)


def test_retrieval_error_while_retrieving_is_logged(mainwin, make_audio, tmp_path, qtbot, user):
    # tagsources.txt's example plugin: "Raise puddlestuff.tagsources.RetrievalError
    # if an error occurs." Synthetic files and album.
    album_files(make_audio, tmp_path / 'music' / 'Artist A - Album A',
                artist='Artist A', album='Album A')
    load(mainwin, qtbot, tmp_path / 'music', 3)
    SyntheticSource.albums = [({'album': 'Album A', 'artist': 'Artist A'}, tracks(genre='Synth'))]
    SyntheticSource.retrieve_errors = {'Album A': RetrievalError('synthetic retrieval failure')}
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic', [{'source': 'Synthetic Source'}])

    log = search(user, qtbot, mainwin, window)

    assert 'An error occurred during album retrieval: synthetic retrieval failure' in log
    assert 'No matches found for tag source Synthetic Source' in log
    no_previews(mainwin)


def test_other_source_error_is_logged_and_the_run_goes_on(mainwin, make_audio, tmp_path, qtbot,
                                                          user):
    # tut5:9: "sequentially process each directory." The Introduction calls it
    # "unattended batch mode": one album's failure mustn't stop the rest.
    # Synthetic files and albums.
    one = album_files(make_audio, tmp_path / 'music' / 'One', artist='Artist A', album='Album A')
    two = album_files(make_audio, tmp_path / 'music' / 'Two', artist='Artist B', album='Album B')
    load(mainwin, qtbot, tmp_path / 'music', 6)
    SyntheticSource.search_errors = {'Album A': ValueError('synthetic failure')}
    SyntheticSource.albums = [
        ({'album': 'Album A', 'artist': 'Artist A'}, tracks(artist='Artist A', genre='GA')),
        ({'album': 'Album B', 'artist': 'Artist B'}, tracks(artist='Artist B', genre='GB')),
    ]
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic', [{'source': 'Synthetic Source'}])

    log = search(user, qtbot, mainwin, window)

    assert 'synthetic failure' in log
    assert button(window, '&Search')
    shown_previews = previews(mainwin)
    assert [shown_previews[str(f)].get('genre') for f in two] == [['GB']] * 3
    assert [shown_previews[str(f)] for f in one] == [{}] * 3


def test_fields_the_source_lacks_are_left_alone(mainwin, make_audio, tmp_path, qtbot, user):
    # tut5:118: "Fields: The list of fields to retrieve from the tag source."
    # tut5:20: "the metadata will be applied to the files". Synthetic files and
    # album, whose tracks carry no track or disc number.
    files = album_files(make_audio, tmp_path / 'music' / 'Artist A - Album A',
                        artist='Artist A', album='Album A', discnumber='1')
    load(mainwin, qtbot, tmp_path / 'music', 3)
    SyntheticSource.albums = [({'album': 'Album A', 'artist': 'Artist A'},
                               [{'genre': 'Synth', 'title': f'Song {n}'} for n in (1, 2, 3)])]
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic', [{'source': 'Synthetic Source'}])

    search(user, qtbot, mainwin, window)
    for preview in previews(mainwin).values():
        assert 'track' not in preview
        assert 'discnumber' not in preview
    write_previews(user, window)
    qtbot.waitUntil(lambda: all(in_file(f).get('genre') == ['Synth'] for f in files))

    user.activate()
    for n, f in enumerate(files, 1):
        assert in_file(f)['track'] == [str(n)]
        assert in_file(f)['discnumber'] == ['1']


def test_profile_is_kept_after_a_restart(mainwin, user, qtbot, restart):
    # Synthetic expectation (tut5.txt gives none on persistence): a saved
    # profile comes back as it was saved. tut5:36: "The best way to explain
    # this I think is by creating a new Profile."
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Kept',
                   [{'source': 'Synthetic Source', 'fields': 'genre', 'if_no_results': 'Stop',
                     'replace': 'genre'}],
                   album=60, brute_force=True, match='title', pattern='%album%/%track% - %title%',
                   track=90, update_empty=True)
    assert os.path.exists(os.path.join(CONFIGDIR, 'masstagging', 'Kept.mtp'))

    new = restart()
    user2 = type(user)(qtbot, new)
    [window2] = new.findChildren(MassTagWindow)
    assert window2.profileCombo.findText('Kept') != -1
    qtbot.waitUntil(window2.isVisible)
    user2.click(button(window2, '&Configure Profiles'))
    profiles = opened(qtbot, MassTagEdit)
    click_item(user2, profiles.listbox, 0)
    user2.click(profiles.buttonlist.editButton)
    editor = opened(qtbot, MTProfileEdit)
    assert editor.pattern.text() == '%album%/%track% - %title%'
    assert editor.albumBound.value() == 60
    assert editor.trackBound.value() == 90
    assert editor.matchFields.text() == 'title'
    assert editor.jfdi.isChecked()
    assert editor.existing.isChecked()
    click_item(user2, editor.listbox, 0)
    user2.click(editor.buttonlist.editButton)
    config = opened(qtbot, TSProfileEdit)
    assert config.no_match.currentText() == 'Stop'
    assert config.fields.text() == 'genre'
    assert config.replace_fields.text() == 'genre'


def test_profile_editor_defaults(mainwin, user, qtbot):
    # Synthetic expectation: tut5:46-50 lists the inputs but not their
    # defaults.
    window = open_mass_tagging(user, mainwin, qtbot)
    user.click(button(window, '&Configure Profiles'))
    profiles = opened(qtbot, MassTagEdit)
    user.click(profiles.buttonlist.addButton)
    editor = opened(qtbot, MTProfileEdit)
    assert editor._name.text() == 'Masstagging Profile'
    assert editor.pattern.text() == '%artist% - %album%/%track% - %title%'
    assert editor.albumBound.value() == 70
    assert editor.matchFields.text() == 'artist, title'
    assert editor.trackBound.value() == 80
    assert not editor.jfdi.isChecked()
    assert not editor.existing.isChecked()
    user.click(button(editor, 'Cancel'))
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is profiles)
    user.click(button(profiles, 'Cancel'))


def test_profile_source_fields_tooltip_says_comma_separated(mainwin, user, qtbot):
    # tut5.txt, Fields: "The list of fields to retrieve from the tag source."
    # tagsources.txt: "Enter a list of comma-separated fields to write here".
    window = open_mass_tagging(user, mainwin, qtbot)
    user.click(button(window, '&Configure Profiles'))
    profiles = opened(qtbot, MassTagEdit)
    user.click(profiles.buttonlist.addButton)
    editor = opened(qtbot, MTProfileEdit)
    user.click(editor.buttonlist.addButton)
    config = opened(qtbot, TSProfileEdit)

    assert config.fields.toolTip().startswith('<p>Enter a comma-separated list of fields to retrieve.')

    user.click(button(config, 'Cancel'))
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is editor)
    user.click(button(editor, 'Cancel'))
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is profiles)
    user.click(button(profiles, 'Cancel'))


def test_search_without_a_profile_asks_for_one(mainwin, make_audio, user, qtbot, tmp_path):
    # tut5:25: "Select a profile from the Masstagging Window." Synthetic
    # files and album; no profile exists, so the window asks for one.
    synthetic_album(make_audio, mainwin, qtbot, tmp_path)
    window = open_mass_tagging(user, mainwin, qtbot)
    user.activate()
    mainwin._table.setFocus()
    user.press(Key.Key_A, Ctrl)
    user.click(button(window, '&Search'))
    [log] = window.findChildren(QTextEdit)
    qtbot.waitUntil(lambda: 'Please choose a tagging profile.' in log.toPlainText())
    no_previews(mainwin)
    assert SyntheticSource.searches == []


def test_clear_preview_discards_the_previews(mainwin, make_audio, user, qtbot, tmp_path, dialogs):
    # tagsources.txt, Clear preview: "Clear preview does as it says and
    # exits preview mode." Synthetic files and album.
    files = synthetic_album(make_audio, mainwin, qtbot, tmp_path)
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic', [{'source': 'Synthetic Source'}])
    search(user, qtbot, mainwin, window)
    assert mainwin._table.model().previewMode
    dialogs.answer('QMessageBox.question', Yes)
    user.click(button(window, 'Clear &Preview'))
    qtbot.waitUntil(lambda: not mainwin._table.model().previewMode)
    assert all(not preview for preview in previews(mainwin).values())
    for f in files:
        # A field the file lacks has no text at all in the model.
        assert shown(user, f, 'genre') == (None, 'plain')
        assert 'genre' not in in_file(f)


# The tag sources a profile can poll.

def test_profile_editor_offers_the_built_in_sources(mainwin, user, qtbot):
    # tut5.txt: "Clicking on the Add Tag Source ("+") button should bring
    # up this dialog", whose Source box lists tagsources.txt's sources:
    # Discogs, FreeDB, MusicBrainz and AcoustID (only where fpcalc is
    # installed). The two other sources are synthetic.
    window = open_mass_tagging(user, mainwin, qtbot)
    user.click(button(window, '&Configure Profiles'))
    profiles = opened(qtbot, MassTagEdit)
    user.click(profiles.buttonlist.addButton)
    editor = opened(qtbot, MTProfileEdit)
    user.activate(editor)
    user.click(editor.buttonlist.addButton)
    config = opened(qtbot, TSProfileEdit)
    listed = {config.source.itemText(n) for n in range(config.source.count())}
    user.click(button(config, 'Cancel'))
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is editor)
    user.click(button(editor, 'Cancel'))
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is profiles)
    user.click(button(profiles, 'Cancel'))
    assert listed - {'AcoustID'} == {'Discogs.com', 'FreeDB', 'MusicBrainz', 'Second Source', 'Synthetic Source'}


def test_profile_skips_a_tag_source_that_is_gone(mainwin, make_audio, user, qtbot, tmp_path,
                                                 restart, dialogs):
    # Synthetic expectation (tut5.txt is silent on a profile whose tag source
    # is gone; it only says "Source: The tag source to use." (tut5:152-154)):
    # puddletag was updated to a version without one of the profile's sources,
    # so the lookup skips that source, says so in the log and still polls the
    # others. Synthetic files and album.
    from puddlestuff import tagsources
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Old',
                   [{'source': 'Second Source'}, {'source': 'Synthetic Source'}])
    tagsources.tagsources.remove(SecondSource)
    try:
        new = restart()
        user2 = type(user)(qtbot, new)
        files = synthetic_album(make_audio, new, qtbot, tmp_path)
        [window2] = new.findChildren(MassTagWindow)
        qtbot.waitUntil(window2.isVisible)
        pick(user2, qtbot, window2.profileCombo, 'Old')
        log = search(user2, qtbot, new, window2)
        assert 'Tag source Second Source not found: skipped.' in log
        assert 'An error occurred' not in log
        assert 'Polling: Synthetic Source' in log
        assert len(SyntheticSource.searches) == 1
        assert SecondSource.searches == []
        for f in files:
            assert shown(user2, f, 'genre') == ('Synth', 'bold')
            assert previews(new)[str(f)]['genre'] == ['Synth']
        # The previews are cleared (Clear Preview asks first), or closing the
        # restarted window would ask whether to write them.
        dialogs.answer('QMessageBox.question', Yes)
        user2.click(button(window2, 'Clear &Preview'))
        qtbot.waitUntil(lambda: not new._table.model().previewMode)
    finally:
        tagsources.tagsources.append(SecondSource)


# The docs don't describe the log's closing line. Synthetic files and albums.

def test_no_valid_match_is_logged_when_no_file_gets_a_track(
        mainwin, make_audio, tmp_path, qtbot, user):
    SyntheticSource.albums = [(ALBUM_A, [dict(t, title=f'Other {t["track"]}')
                                         for t in tracks(genre='Synth')])]
    window, files = run_album(user, qtbot, mainwin, make_audio, tmp_path)
    log = search(user, qtbot, mainwin, window)
    no_previews(mainwin)
    assert 'Valid matches were found for the album.' not in log
    assert 'No valid matches were found for the album.' in log


def test_valid_matches_are_logged_when_the_recheck_found_the_album(
        mainwin, user, make_audio, tmp_path, qtbot):
    album_files(make_audio, tmp_path / 'music' / 'AA - Album A',
                artist='AA', album='Album A')
    load(mainwin, qtbot, tmp_path / 'music', 3)
    SyntheticSource.albums = [({'album': 'Album A', 'artist': 'Artist Alpha'},
                               tracks(genre='One'))]
    SecondSource.albums = [({'album': 'Album A', 'artist': 'AA'},
                            tracks(artist='Artist Alpha'))]
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic',
                   [{'source': 'Synthetic Source'}, {'source': 'Second Source'}], match='title')
    pick(user, qtbot, window.profileCombo, 'Synthetic')
    log = search(user, qtbot, mainwin, window)
    assert 'Valid matches were found for the album.' in log


def test_puddletag_starts_with_a_broken_profile(mainwin, qtbot, restart):
    # tut5.txt, How to use it: "A profile whose file puddletag can't read
    # isn't listed: the **Masstagging** window's log names the file instead."
    # Synthetic broken file; puddletag still starts.
    with open(os.path.join(CONFIGDIR, 'masstagging', 'Broken.mtp'), 'w') as f:
        f.write('{"info": 5}')
    new = restart()
    [window] = new.findChildren(MassTagWindow)
    assert window.profileCombo.count() == 0
    assert 'Broken.mtp' in window._log.toPlainText()


@pytest.mark.parametrize('name', ['', '.hidden', 'AC/DC'])
def test_a_profile_is_kept_whatever_its_name(mainwin, user, qtbot, restart, name):
    # Synthetic expectation (tut5.txt gives none on a name's characters): a
    # saved profile comes back after a restart whatever its name. tut5.txt,
    # Name: "The name of the profile."
    window = open_mass_tagging(user, mainwin, qtbot)
    # create_profile waits on the name in the combo, which findText doesn't
    # find for an empty one.
    user.click(button(window, '&Configure Profiles'))
    profiles = opened(qtbot, MassTagEdit)
    user.click(profiles.buttonlist.addButton)
    editor = opened(qtbot, MTProfileEdit)
    user.activate(editor)
    replace_text(user, editor._name, name)
    if not name:
        # Typing nothing leaves the default name selected: delete it.
        user.press(Key.Key_Backspace)
    assert editor._name.text() == name
    user.click(editor.buttonlist.addButton)
    config = opened(qtbot, TSProfileEdit)
    user.activate(config)
    pick(user, qtbot, config.source, 'Synthetic Source')
    user.click(button(config, 'OK'))
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is editor)
    user.activate(editor)
    user.click(button(editor, 'OK'))
    qtbot.waitUntil(lambda: profiles.listbox.count() == 1)
    user.click(button(profiles, 'OK'))
    qtbot.waitUntil(lambda: window.profileCombo.count() == 1)

    new = restart()
    [window2] = new.findChildren(MassTagWindow)
    combo = window2.profileCombo
    assert [combo.itemText(i) for i in range(combo.count())] == [name]


def test_start_leaves_an_old_ini_profile_alone(mainwin, qtbot, restart):
    # Synthetic INI profile, as puddletag wrote them before 1.0; puddletag no
    # longer reads INI configuration, so a start must not touch the file.
    folder = os.path.join(CONFIGDIR, 'masstagging')
    with open(os.path.join(folder, 'Old.conf'), 'w') as f:
        f.write('[info]\nname = Old\nnumsources = 0\n')
    restart()
    assert sorted(os.listdir(folder)) == ['Old.conf']


def saved_sources(name):
    """The tag sources a profile's file on disk names, in its order."""
    with open(os.path.join(CONFIGDIR, 'masstagging', f'{name}.mtp')) as f:
        data = json.load(f)
    return [data[f'config{n}']['source'] for n in range(data['info']['numsources'])]


def test_ok_keeps_a_tag_source_puddletag_lacks(mainwin, user, qtbot, restart):
    # tut5.txt, Tag Sources: "A tag source puddletag doesn't have (one removed
    # in an update, say) is listed with **(not found)** after its name. It's
    # kept when the profile is saved, and searches skip it." OK in Configure
    # Profiles saves every profile again, and the source keeps its name, so
    # it's polled again once puddletag has it.
    from puddlestuff import tagsources
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Old',
                   [{'source': 'Second Source'}, {'source': 'Synthetic Source'}])
    tagsources.tagsources.remove(SecondSource)
    try:
        new = restart()
        user2 = type(user)(qtbot, new)
        [window2] = new.findChildren(MassTagWindow)
        qtbot.waitUntil(window2.isVisible)
        user2.click(button(window2, '&Configure Profiles'))
        profiles = opened(qtbot, MassTagEdit)
        user2.click(button(profiles, 'OK'))
        qtbot.waitUntil(lambda: QApplication.activeModalWidget() is None)
        assert saved_sources('Old') == ['Second Source', 'Synthetic Source']
    finally:
        tagsources.tagsources.append(SecondSource)


def test_editor_shows_the_saved_percentages(mainwin, user, qtbot):
    # Synthetic expectation (tut5.txt says nothing on how profiles are kept):
    # a saved profile comes back as it was saved, so the editor shows 57 and 29
    # as they were set. tut5.txt lists the two percentages, "Minimum percentage
    # required for album matches." and "Minimum percentage required for track
    # match."
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'P', [{'source': 'Synthetic Source'}], album=57, track=29)
    user.click(button(window, '&Configure Profiles'))
    profiles = opened(qtbot, MassTagEdit)
    click_item(user, profiles.listbox, 0)
    user.click(profiles.buttonlist.editButton)
    editor = opened(qtbot, MTProfileEdit)
    assert editor.albumBound.value() == 57
    assert editor.trackBound.value() == 29
    user.click(button(editor, 'Cancel'))
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is profiles)
    user.click(button(profiles, 'Cancel'))


def test_editing_a_profile_keeps_a_tag_source_puddletag_lacks(mainwin, user, qtbot, restart):
    # tut5.txt, Tag Sources: "A tag source puddletag doesn't have (one removed
    # in an update, say) is listed with **(not found)** after its name. It's
    # kept when the profile is saved, and searches skip it." Edit then OK in
    # the profile editor keeps it too.
    from puddlestuff import tagsources
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Old',
                   [{'source': 'Second Source'}, {'source': 'Synthetic Source'}])
    tagsources.tagsources.remove(SecondSource)
    try:
        new = restart()
        user2 = type(user)(qtbot, new)
        [window2] = new.findChildren(MassTagWindow)
        qtbot.waitUntil(window2.isVisible)
        user2.click(button(window2, '&Configure Profiles'))
        profiles = opened(qtbot, MassTagEdit)
        click_item(user2, profiles.listbox, 0)
        user2.click(profiles.buttonlist.editButton)
        editor = opened(qtbot, MTProfileEdit)
        rows = [editor.listbox.item(i).text() for i in range(editor.listbox.count())]
        user2.click(button(editor, 'OK'))
        qtbot.waitUntil(lambda: QApplication.activeModalWidget() is profiles)
        user2.click(button(profiles, 'OK'))
        qtbot.waitUntil(lambda: QApplication.activeModalWidget() is None)
        assert rows == ['Second Source (not found)', 'Synthetic Source']
        assert saved_sources('Old') == ['Second Source', 'Synthetic Source']
    finally:
        tagsources.tagsources.append(SecondSource)


class Gate:
    """Holds a tag source inside a call, as a slow web service does, until
    the test opens it: nothing waits on a clock. arrived lists every (source,
    album) that reached the call; reached is set once the held one did."""

    def __init__(self):
        self.arrived = []
        self.opening = threading.Event()
        self.reached = threading.Event()


@pytest.fixture
def hold(mainwin, monkeypatch):
    """hold('search' or 'retrieve', source name, album) returns a Gate that
    holds that call. The gates open at teardown and the lookup's thread is
    waited for, as a running QThread can't be destroyed."""
    gates = []

    def holding(method, source, album):
        gate = Gate()
        call = getattr(SyntheticSource, method)

        def held(self, first, *rest):
            key = (self.name, first if method == 'search' else first['album'])
            gate.arrived.append(key)
            if key == (source, album):
                gate.reached.set()
                assert gate.opening.wait(10), 'the test never opened the gate'
            return call(self, first, *rest)

        monkeypatch.setattr(SyntheticSource, method, held)
        gates.append(gate)
        return gate

    yield holding
    for gate in gates:
        gate.opening.set()
    for thread in mainwin.findChildren(QThread):
        thread.wait(10000)


def press_search(user, mainwin, window):
    """Selects every file and clicks Search, without waiting for the run."""
    user.activate()
    mainwin._table.setFocus()
    user.press(Key.Key_A, Ctrl)
    user.click(button(window, '&Search'))


def end_of_run(gate, qtbot, window):
    """Opens the gate and waits for the log's last line. Returns the log."""
    gate.opening.set()
    [log] = window.findChildren(QTextEdit)
    qtbot.waitUntil(lambda: 'Lookups completed.' in log.toPlainText(), timeout=10000)
    return log.toPlainText()


def stop_during(user, qtbot, mainwin, window, gate):
    """Searches, clicks Stop once the source holds the call, lets the source
    go and returns the log."""
    press_search(user, mainwin, window)
    qtbot.waitUntil(gate.reached.is_set)
    user.click(button(window, '&Stop'))
    return end_of_run(gate, qtbot, window)


# Synthetic expectation (tut5.txt never mentions Stop; it says "Click on
# Search. Wait until it's done.").

def test_stop_ends_the_lookup(mainwin, make_audio, user, qtbot, tmp_path, hold):
    files = synthetic_album(make_audio, mainwin, qtbot, tmp_path)
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic', [{'source': 'Synthetic Source'}])
    gate = hold('search', 'Synthetic Source', 'Album A')
    press_search(user, mainwin, window)
    qtbot.waitUntil(gate.reached.is_set)
    assert button(window, '&Stop')
    user.click(button(window, '&Stop'))
    log = end_of_run(gate, qtbot, window)
    assert button(window, '&Search')
    assert 'No valid matches were found for the album.' in log
    assert SyntheticSource.retrieved == []
    no_previews(mainwin)
    for f in files:
        assert 'genre' not in in_file(f)


# tut5.txt: "sequentially process each directory". It says nothing on Stop;
# synthetic expectation: the albums Stop leaves unreached log nothing.

def test_stop_leaves_the_albums_not_reached(mainwin, make_audio, user, qtbot, tmp_path, hold):
    music = tmp_path / 'music'
    for name in ('One', 'Three', 'Two'):
        album_files(make_audio, music / name, artist=f'Artist {name}', album=f'Album {name}')
    load(mainwin, qtbot, music, 9)
    SyntheticSource.albums = [
        ({'album': f'Album {name}', 'artist': f'Artist {name}'},
         tracks(artist=f'Artist {name}', genre=name))
        for name in ('One', 'Three', 'Two')]
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic', [{'source': 'Synthetic Source'}])
    gate = hold('search', 'Synthetic Source', 'Album One')
    log = stop_during(user, qtbot, mainwin, window, gate)
    assert log.count('No valid matches were found for the album.') == 1
    assert SyntheticSource.searches == [('Album One', ['Artist One'])]


# Synthetic expectation (tut5.txt never mentions Stop): Search works again
# once a stopped run is over.

def test_search_works_again_after_stop(mainwin, make_audio, user, qtbot, tmp_path, hold):
    files = synthetic_album(make_audio, mainwin, qtbot, tmp_path)
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic', [{'source': 'Synthetic Source'}])
    gate = hold('search', 'Synthetic Source', 'Album A')
    stop_during(user, qtbot, mainwin, window, gate)
    log = search(user, qtbot, mainwin, window)
    assert 'Valid matches were found for the album.' in log
    for f in files:
        assert shown(user, f, 'genre') == ('Synth', 'bold')
        assert previews(mainwin)[str(f)]['genre'] == ['Synth']
        assert 'genre' not in in_file(f)


# tut5.txt: "When done and if matches were found, the metadata will be applied
# to the files and puddletag will be in Preview Mode". Stop itself is a
# synthetic expectation: the albums found before it stay.

def test_stop_keeps_the_albums_already_found(mainwin, make_audio, user, qtbot, tmp_path, hold):
    music = tmp_path / 'music'
    one = album_files(make_audio, music / 'One', artist='Artist A', album='Album A')
    two = album_files(make_audio, music / 'Two', artist='Artist B', album='Album B')
    load(mainwin, qtbot, music, 6)
    SyntheticSource.albums = [
        ({'album': 'Album A', 'artist': 'Artist A'}, tracks(artist='Artist A', genre='GA')),
        ({'album': 'Album B', 'artist': 'Artist B'}, tracks(artist='Artist B', genre='GB'))]
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic', [{'source': 'Synthetic Source'}])
    gate = hold('search', 'Synthetic Source', 'Album B')
    log = stop_during(user, qtbot, mainwin, window, gate)
    assert mainwin._table.model().previewMode
    for f in one:
        assert previews(mainwin)[str(f)]['genre'] == ['GA']
    for f in two:
        assert previews(mainwin)[str(f)] == {}
    assert 'Valid matches were found for the album.' in log
    write_previews(user, window)
    qtbot.waitUntil(lambda: all(in_file(f).get('genre') == ['GA'] for f in one))
    for f in two:
        assert 'genre' not in in_file(f)


# tut5.txt, of the other Stop: "Stop the lookup and use any previously
# retrieved results." Synthetic expectation for this Stop.

def test_stop_uses_the_source_that_already_answered(
        mainwin, make_audio, user, qtbot, tmp_path, hold):
    files = synthetic_album(make_audio, mainwin, qtbot, tmp_path)
    SecondSource.albums = [(ALBUM_A, tracks(genre='Two'))]
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic',
                   [{'source': 'Synthetic Source'}, {'source': 'Second Source'}])
    gate = hold('search', 'Second Source', 'Album A')
    log = stop_during(user, qtbot, mainwin, window, gate)
    assert SyntheticSource.retrieved == ['Album A']
    assert SecondSource.retrieved == []
    for f in files:
        assert previews(mainwin)[str(f)]['genre'] == ['Synth']
    assert 'Valid matches were found for the album.' in log


# Synthetic expectation (tut5.txt never mentions Stop; its other Stop says
# "use any previously retrieved results"): the album being retrieved when
# Stop is clicked is used.

def test_stop_during_a_retrieval_keeps_the_album(
        mainwin, make_audio, user, qtbot, tmp_path, hold):
    files = synthetic_album(make_audio, mainwin, qtbot, tmp_path)
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic', [{'source': 'Synthetic Source'}])
    gate = hold('retrieve', 'Synthetic Source', 'Album A')
    log = stop_during(user, qtbot, mainwin, window, gate)
    for f in files:
        assert previews(mainwin)[str(f)]['genre'] == ['Synth']
    assert 'Valid matches were found for the album.' in log
    assert SyntheticSource.retrieved == ['Album A']


def rows(listbox):
    """Each row's text."""
    return [listbox.item(n).text() for n in range(listbox.count())]


def combo_rows(window):
    combo = window.profileCombo
    return [combo.itemText(n) for n in range(combo.count())]


def profile_files():
    """The profile folder's files, and its order file's lines."""
    folder = os.path.join(CONFIGDIR, 'masstagging')
    with open(os.path.join(folder, 'order')) as f:
        return sorted(os.listdir(folder)), f.read().split('\n')


def open_profiles(user, qtbot, window):
    user.click(button(window, '&Configure Profiles'))
    return opened(qtbot, MassTagEdit)


def open_row(user, qtbot, dialog, row, clicked, kind):
    """Selects this row of Configure Profiles or of the profile editor and
    clicks its button (editButton or duplicateButton). Returns the dialog of
    this kind that opens, activated."""
    click_item(user, dialog.listbox, row)
    user.click(getattr(dialog.buttonlist, clicked))
    opening = opened(qtbot, kind)
    user.activate(opening)
    return opening


def ok(user, qtbot, dialog, below=None):
    """Clicks OK and waits for the dialog below it, activated, or for no
    dialog at all."""
    user.click(button(dialog, 'OK'))
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is below)
    if below:
        user.activate(below)


one = [{'source': 'Synthetic Source'}]
two = [{'source': 'Second Source'}]


def test_duplicate_adds_a_copy_with_the_same_name(mainwin, user, qtbot):
    # Synthetic expectation (tut5.txt says nothing on Configure Profiles' other
    # buttons; their tooltips say Duplicate, Edit, Remove, Move Up, Move Down):
    # Duplicate opens the editor with the profile's name, sources and options,
    # and OK adds the copy under the same name.
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Alpha', one, album=60)
    profiles = open_profiles(user, qtbot, window)
    editor = open_row(user, qtbot, profiles, 0, 'duplicateButton', MTProfileEdit)
    assert editor._name.text() == 'Alpha'
    assert rows(editor.listbox) == ['Synthetic Source']
    assert editor.albumBound.value() == 60
    ok(user, qtbot, editor, profiles)
    assert rows(profiles.listbox) == ['Alpha', 'Alpha']
    ok(user, qtbot, profiles)
    assert combo_rows(window) == ['Alpha', 'Alpha']
    assert profile_files() == (['Alpha.mtp', 'Alpha_0.mtp', 'order'], ['Alpha', 'Alpha'])


def test_a_duplicate_can_differ_from_its_original(mainwin, user, qtbot):
    # Synthetic expectation (tut5.txt says nothing on Configure Profiles' other
    # buttons; their tooltips say Duplicate, Edit, Remove, Move Up, Move Down):
    # the copy is edited before it is added, and the original stays as it was.
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Alpha', one, album=60)
    profiles = open_profiles(user, qtbot, window)
    editor = open_row(user, qtbot, profiles, 0, 'duplicateButton', MTProfileEdit)
    replace_text(user, editor._name, 'Beta')
    replace_text(user, editor.albumBound, '50')
    ok(user, qtbot, editor, profiles)
    editor = open_row(user, qtbot, profiles, 0, 'editButton', MTProfileEdit)
    assert editor._name.text() == 'Alpha'
    assert editor.albumBound.value() == 60
    user.click(button(editor, 'Cancel'))
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is profiles)
    ok(user, qtbot, profiles)
    assert combo_rows(window) == ['Alpha', 'Beta']


def test_same_named_profiles_keep_their_order_after_a_restart(mainwin, user, qtbot, restart):
    # tut5:57 "The name of the profile." Synthetic expectation (tut5.txt says
    # nothing on Configure Profiles' other buttons; their tooltips say
    # Duplicate, Edit, Remove, Move Up, Move Down): profiles that share a name
    # come back in the order they were saved, each with its own sources.
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Same', one)
    create_profile(user, qtbot, window, 'Other', two)
    create_profile(user, qtbot, window, 'Same', two)
    profiles = open_profiles(user, qtbot, window)
    click_item(user, profiles.listbox, 2)
    user.click(profiles.buttonlist.moveupButton)
    assert rows(profiles.listbox) == ['Same', 'Same', 'Other']
    ok(user, qtbot, profiles)

    new = restart()
    [window2] = new.findChildren(MassTagWindow)
    assert [(p.name, p.profiles[0].tag_source.name) for p in window2.profiles] == [
        ('Same', 'Synthetic Source'), ('Same', 'Second Source'), ('Other', 'Second Source')]


def test_remove_takes_a_profile_off_the_list(mainwin, user, qtbot):
    # Synthetic expectation (tut5.txt says nothing on Configure Profiles' other
    # buttons; their tooltips say Duplicate, Edit, Remove, Move Up, Move Down):
    # a removed profile is gone from the list, the combo and the disk after OK.
    window = open_mass_tagging(user, mainwin, qtbot)
    for name in ('Alpha', 'Beta', 'Gamma'):
        create_profile(user, qtbot, window, name, one)
    profiles = open_profiles(user, qtbot, window)
    click_item(user, profiles.listbox, 1)
    user.click(profiles.buttonlist.removeButton)
    assert rows(profiles.listbox) == ['Alpha', 'Gamma']
    ok(user, qtbot, profiles)
    assert combo_rows(window) == ['Alpha', 'Gamma']
    assert profile_files() == (['Alpha.mtp', 'Gamma.mtp', 'order'], ['Alpha', 'Gamma'])


def test_move_sets_the_saved_order(mainwin, user, qtbot, restart):
    # Synthetic expectation (tut5.txt says nothing on Configure Profiles' other
    # buttons; their tooltips say Duplicate, Edit, Remove, Move Up, Move Down):
    # Move Up and Move Down reorder the list, the top row can't go up nor the
    # bottom row down, and OK saves the order.
    window = open_mass_tagging(user, mainwin, qtbot)
    for name in ('Alpha', 'Beta', 'Gamma'):
        create_profile(user, qtbot, window, name, one)
    profiles = open_profiles(user, qtbot, window)
    up = profiles.buttonlist.moveupButton
    down = profiles.buttonlist.movedownButton
    click_item(user, profiles.listbox, 2)
    user.click(up)
    assert rows(profiles.listbox) == ['Alpha', 'Gamma', 'Beta']
    user.click(up)
    assert rows(profiles.listbox) == ['Gamma', 'Alpha', 'Beta']
    user.click(up)
    assert rows(profiles.listbox) == ['Gamma', 'Alpha', 'Beta']
    user.click(down)
    assert rows(profiles.listbox) == ['Alpha', 'Gamma', 'Beta']
    click_item(user, profiles.listbox, 2)
    user.click(down)
    assert rows(profiles.listbox) == ['Alpha', 'Gamma', 'Beta']
    ok(user, qtbot, profiles)
    assert combo_rows(window) == ['Alpha', 'Gamma', 'Beta']
    assert profile_files()[1] == ['Alpha', 'Gamma', 'Beta']

    new = restart()
    [window2] = new.findChildren(MassTagWindow)
    assert combo_rows(window2) == ['Alpha', 'Gamma', 'Beta']


def test_edit_renames_a_profile_and_its_file(mainwin, user, qtbot):
    # Synthetic expectation (tut5.txt says nothing on Configure Profiles' other
    # buttons; their tooltips say Duplicate, Edit, Remove, Move Up, Move Down):
    # renaming a profile in its editor renames it in the combo and on disk.
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Old', one)
    profiles = open_profiles(user, qtbot, window)
    editor = open_row(user, qtbot, profiles, 0, 'editButton', MTProfileEdit)
    replace_text(user, editor._name, 'New')
    ok(user, qtbot, editor, profiles)
    ok(user, qtbot, profiles)
    assert combo_rows(window) == ['New']
    assert window.profileCombo.currentText() == 'New'
    assert profile_files() == (['New.mtp', 'order'], ['New'])


def test_double_click_opens_a_profile(mainwin, user, qtbot):
    # Synthetic expectation (tut5.txt says nothing on Configure Profiles' other
    # buttons; their tooltips say Duplicate, Edit, Remove, Move Up, Move Down):
    # a double-click on a row does what Edit does.
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Alpha', one)
    profiles = open_profiles(user, qtbot, window)
    listbox = profiles.listbox
    user.double_click(listbox.viewport(), listbox.visualItemRect(listbox.item(0)).center())
    editor = opened(qtbot, MTProfileEdit)
    assert editor._name.text() == 'Alpha'
    user.click(button(editor, 'Cancel'))
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is profiles)
    user.click(button(profiles, 'Cancel'))


def test_list_buttons_wait_for_a_row(mainwin, user, qtbot):
    # Synthetic expectation (tut5.txt says nothing on Configure Profiles' other
    # buttons; their tooltips say Duplicate, Edit, Remove, Move Up, Move Down):
    # the buttons that act on a row are off until a row is clicked, and off
    # again once the last row is removed. Add is always on.
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Alpha', one)
    profiles = open_profiles(user, qtbot, window)
    buttons = profiles.buttonlist
    on_a_row = [buttons.duplicateButton, buttons.editButton, buttons.movedownButton,
                buttons.moveupButton, buttons.removeButton]
    assert buttons.addButton.isEnabled()
    assert not any(b.isEnabled() for b in on_a_row)
    click_item(user, profiles.listbox, 0)
    assert all(b.isEnabled() for b in on_a_row)
    user.click(buttons.removeButton)
    assert not any(b.isEnabled() for b in on_a_row)
    user.click(button(profiles, 'Cancel'))


def test_the_chosen_profile_is_kept_after_a_restart(mainwin, user, qtbot, restart):
    # Synthetic expectation (tut5.txt says nothing on Configure Profiles' other
    # buttons; their tooltips say Duplicate, Edit, Remove, Move Up, Move Down):
    # the profile chosen in the combo is the one chosen after a restart.
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'A', one)
    create_profile(user, qtbot, window, 'B', two)
    pick(user, qtbot, window.profileCombo, 'B')

    new = restart()
    [window2] = new.findChildren(MassTagWindow)
    assert window2.profileCombo.currentText() == 'B'
    assert window2.profile.name == 'B'


def test_ok_goes_on_past_a_file_it_cannot_remove(mainwin, user, qtbot, restart):
    # Synthetic expectation (tut5.txt says nothing on Configure Profiles' other
    # buttons; their tooltips say Duplicate, Edit, Remove, Move Up, Move Down):
    # a folder named like a profile file, which os.remove refuses even as root,
    # doesn't stop OK, and the next start skips it. tut5:33 "the Masstagging
    # window's log names the file".
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'A', one)
    folder = os.path.join(CONFIGDIR, 'masstagging')
    os.mkdir(os.path.join(folder, 'Stale.mtp'))
    profiles = open_profiles(user, qtbot, window)
    ok(user, qtbot, profiles)
    assert profile_files() == (['A.mtp', 'Stale.mtp', 'order'], ['A'])

    new = restart()
    [window2] = new.findChildren(MassTagWindow)
    assert combo_rows(window2) == ['A']
    assert 'Stale.mtp' in window2._log.toPlainText()


def two_sources_editor(user, qtbot, window):
    """A profile 'A' of two tag sources, open in its editor from Configure
    Profiles. Returns the editor and the dialog below it."""
    create_profile(user, qtbot, window, 'A',
                   [{'source': 'Synthetic Source', 'fields': 'genre'}, {'source': 'Second Source'}])
    profiles = open_profiles(user, qtbot, window)
    return open_row(user, qtbot, profiles, 0, 'editButton', MTProfileEdit), profiles


def test_duplicate_tag_source_copies_its_options(mainwin, user, qtbot):
    # Synthetic expectation (tut5.txt says nothing on Configure Profiles' other
    # buttons; their tooltips say Duplicate, Edit, Remove, Move Up, Move Down):
    # Duplicate opens the tag source dialog with the row's source and fields,
    # and OK adds the copy at the end.
    window = open_mass_tagging(user, mainwin, qtbot)
    editor, profiles = two_sources_editor(user, qtbot, window)
    config = open_row(user, qtbot, editor, 0, 'duplicateButton', TSProfileEdit)
    assert config.source.currentText() == 'Synthetic Source'
    assert config.fields.text() == 'genre'
    ok(user, qtbot, config, editor)
    assert rows(editor.listbox) == ['Synthetic Source', 'Second Source', 'Synthetic Source']
    ok(user, qtbot, editor, profiles)
    ok(user, qtbot, profiles)
    assert saved_sources('A') == ['Synthetic Source', 'Second Source', 'Synthetic Source']


def test_moving_a_tag_source_changes_the_polling_order(mainwin, user, album, qtbot):
    # tut5:65 "Each tag source will be polled in the order listed here."
    files, window = album
    SyntheticSource.albums = [(ALBUM_A, tracks(genre='One'))]
    SecondSource.albums = [(ALBUM_A, tracks(genre='Two'))]
    editor, profiles = two_sources_editor(user, qtbot, window)
    click_item(user, editor.listbox, 1)
    user.click(editor.buttonlist.moveupButton)
    assert rows(editor.listbox) == ['Second Source', 'Synthetic Source']
    assert [t.fields for t in editor._tsps] == [[], ['genre']]
    user.click(editor.buttonlist.movedownButton)
    assert rows(editor.listbox) == ['Synthetic Source', 'Second Source']
    assert [t.fields for t in editor._tsps] == [['genre'], []]
    user.click(editor.buttonlist.moveupButton)
    assert rows(editor.listbox) == ['Second Source', 'Synthetic Source']
    assert [t.fields for t in editor._tsps] == [[], ['genre']]
    ok(user, qtbot, editor, profiles)
    ok(user, qtbot, profiles)
    log = search(user, qtbot, mainwin, window)
    assert saved_sources('A') == ['Second Source', 'Synthetic Source']
    assert log.index('Polling: Second Source') < log.index('Polling: Synthetic Source')


def test_edit_tag_source_replaces_its_row(mainwin, user, qtbot):
    # Synthetic expectation (tut5.txt says nothing on Configure Profiles' other
    # buttons; their tooltips say Duplicate, Edit, Remove, Move Up, Move Down):
    # Edit on a tag source replaces its row with what the dialog is left with.
    window = open_mass_tagging(user, mainwin, qtbot)
    editor, profiles = two_sources_editor(user, qtbot, window)
    config = open_row(user, qtbot, editor, 1, 'editButton', TSProfileEdit)
    pick(user, qtbot, config.source, 'Synthetic Source')
    replace_text(user, config.fields, 'year')
    ok(user, qtbot, config, editor)
    assert rows(editor.listbox) == ['Synthetic Source', 'Synthetic Source']
    ok(user, qtbot, editor, profiles)
    ok(user, qtbot, profiles)
    assert saved_sources('A') == ['Synthetic Source', 'Synthetic Source']
    assert window.profile.profiles[1].fields == ['year']


def test_remove_tag_source(mainwin, user, qtbot):
    # Synthetic expectation (tut5.txt says nothing on Configure Profiles' other
    # buttons; their tooltips say Duplicate, Edit, Remove, Move Up, Move Down):
    # a removed tag source leaves the list and the saved profile, and the next
    # row is current.
    window = open_mass_tagging(user, mainwin, qtbot)
    editor, profiles = two_sources_editor(user, qtbot, window)
    click_item(user, editor.listbox, 0)
    user.click(editor.buttonlist.removeButton)
    assert rows(editor.listbox) == ['Second Source']
    assert editor.buttonlist.editButton.isEnabled()
    ok(user, qtbot, editor, profiles)
    ok(user, qtbot, profiles)
    assert saved_sources('A') == ['Second Source']


def test_double_click_opens_a_tag_source(mainwin, user, qtbot):
    # Synthetic expectation (tut5.txt says nothing on Configure Profiles' other
    # buttons; their tooltips say Duplicate, Edit, Remove, Move Up, Move Down):
    # a double-click on a tag source does what Edit does.
    window = open_mass_tagging(user, mainwin, qtbot)
    editor, profiles = two_sources_editor(user, qtbot, window)
    listbox = editor.listbox
    user.double_click(listbox.viewport(), listbox.visualItemRect(listbox.item(0)).center())
    config = opened(qtbot, TSProfileEdit)
    assert config.fields.text() == 'genre'
    user.click(button(config, 'Cancel'))
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is editor)
    user.activate(editor)
    ok(user, qtbot, editor, profiles)
    ok(user, qtbot, profiles)


MP3TAG_SCRIPT = """[Name]=Synthetic Mp3tag
[IndexUrl]={url}/search?q=%s
[AlbumUrl]={url}/album?id=
[IndexFormat]=%_url%|%album%|%artist%
[SearchBy]={search_by}
[ParserScriptIndex]=...
sayrest
[ParserScriptAlbum]=...
outputto "album"
say "Album A"
outputto "artist"
say "Artist A"
outputto "genre"
say "Web"
outputto "tracks"
say "Song 1|Song 2|Song 3"
"""


def install_mp3tag_script(web_server, monkeypatch, search_by):
    """A script in the user's mp3tag_sources folder, written before mainwin
    builds the window, answered by the local web server. Its requests go
    without Mp3tag scripts' second between them."""
    monkeypatch.setattr(discogs, '_wait', lambda: None)
    folder = Path(CONFIGDIR) / 'mp3tag_sources'
    folder.mkdir(exist_ok=True)
    (folder / 'Synthetic.src').write_text(
        MP3TAG_SCRIPT.format(url=web_server.url, search_by=search_by))
    web_server.add('/search', 'u1|Album A|Artist A')
    web_server.add('/album', 'Any page: the script says its own text.')


@pytest.fixture
def mp3tag_script(clean_profile, web_server, monkeypatch):
    install_mp3tag_script(web_server, monkeypatch, '%album%')
    return web_server


@pytest.fixture
def mp3tag_script_several_fields(clean_profile, web_server, monkeypatch):
    install_mp3tag_script(web_server, monkeypatch, 'Search for||%album%||%s')
    return web_server


def test_a_profile_can_poll_an_mp3tag_script(mp3tag_script, mainwin, make_audio, user, qtbot,
                                             tmp_path, restart, dialogs):
    # tut5.txt: "The tag source to use. See tagsources"; tagsources.txt:
    # "Selecting files and searching works too, for a tag source whose
    # [SearchBy] line names plain fields". Synthetic script and album.
    files = load_album_a(make_audio, mainwin, qtbot, tmp_path)
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Web', [{'source': 'Synthetic Mp3tag [M]'}])
    log = search(user, qtbot, mainwin, window)
    assert saved_sources('Web') == ['Synthetic Mp3tag [M]']
    assert 'Polling: Synthetic Mp3tag [M]' in log
    assert [(r.path, r.query) for r in mp3tag_script.requests] == [
        ('/search', {'q': ['Album A']}), ('/album', {'id': ['u1']})]
    for n, f in enumerate(files, 1):
        assert previews(mainwin)[str(f)]['genre'] == ['Web']
        assert previews(mainwin)[str(f)]['title'] == [f'Song {n}']
        assert 'genre' not in in_file(f)

    dialogs.answer('QMessageBox.question', Yes)
    user.click(button(window, 'Clear &Preview'))
    qtbot.waitUntil(lambda: not mainwin._table.model().previewMode)
    new = restart()
    [window2] = new.findChildren(MassTagWindow)
    assert window2.profile.profiles[0].tag_source.name == 'Synthetic Mp3tag [M]'


def test_an_mp3tag_script_it_cannot_search_says_why(mp3tag_script_several_fields, mainwin,
                                                    make_audio, user, qtbot, tmp_path):
    # tagsources.txt: "You can search as you do using Mp3tag by using the
    # Search box. Selecting files and searching works too, for a tag source
    # whose [SearchBy] line names plain fields". Synthetic script and album.
    load_album_a(make_audio, mainwin, qtbot, tmp_path)
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Web', [{'source': 'Synthetic Mp3tag [M]'}])
    log = search(user, qtbot, mainwin, window)
    assert ("An error occurred during the search: [SearchBy] with several search fields (||) "
            "isn't supported.") in log
    assert mp3tag_script_several_fields.requests == []
    no_previews(mainwin)


# Synthetic expectation (tut5.txt never mentions Stop): Search stays off,
# still reading Stop, until the stopped run has ended.

def test_search_stays_off_until_the_stopped_run_ends(
        mainwin, make_audio, user, qtbot, tmp_path, hold):
    synthetic_album(make_audio, mainwin, qtbot, tmp_path)
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic', [{'source': 'Synthetic Source'}])
    gate = hold('search', 'Synthetic Source', 'Album A')
    press_search(user, mainwin, window)
    qtbot.waitUntil(gate.reached.is_set)
    user.click(button(window, '&Stop'))
    start = window._startButton
    assert not start.isEnabled()
    assert start.text() == '&Stop'
    user.click(start)
    log = end_of_run(gate, qtbot, window)
    assert gate.arrived == [('Synthetic Source', 'Album A')]
    assert log.count('Lookups completed.') == 1
    assert start.isEnabled()
    assert start.text() == '&Search'


# tut5.txt: "each Tag Source is searched a second time with the album name
# without it". Stop is a synthetic expectation: it ends the retry as well.

def test_stop_skips_the_retry_without_brackets(
        mainwin, make_audio, user, qtbot, tmp_path, hold):
    album_files(make_audio, tmp_path / 'music' / 'One', artist='Artist A',
                album='Album A (Deluxe)')
    load(mainwin, qtbot, tmp_path / 'music', 3)
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic', [{'source': 'Synthetic Source'}])
    gate = hold('search', 'Synthetic Source', 'Album A (Deluxe)')
    log = stop_during(user, qtbot, mainwin, window, gate)
    assert gate.arrived == [('Synthetic Source', 'Album A (Deluxe)')]
    assert 'Retrying search' not in log


# tut5.txt: "Otherwise the next matching album is retrieved". Stop is a
# synthetic expectation: it ends that as well.

def test_stop_retrieves_no_further_album(mainwin, make_audio, user, qtbot, tmp_path, hold):
    load_album_a(make_audio, mainwin, qtbot, tmp_path)
    SyntheticSource.albums = [
        (ALBUM_A, tracks(5, genre='Five')),
        ({'album': 'Album A (2)', 'artist': 'Artist A'}, tracks(5, genre='Two'))]
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'Synthetic', [{'source': 'Synthetic Source'}])
    gate = hold('retrieve', 'Synthetic Source', 'Album A')
    log = stop_during(user, qtbot, mainwin, window, gate)
    assert gate.arrived == [('Synthetic Source', 'Album A')]
    assert 'Retrieving next matching album' not in log
    no_previews(mainwin)


def describe(user, qtbot, window, row, text):
    """Types the profile's Description in its editor."""
    profiles = open_profiles(user, qtbot, window)
    editor = open_row(user, qtbot, profiles, row, 'editButton', MTProfileEdit)
    replace_text(user, editor._desc, text)
    ok(user, qtbot, editor, profiles)
    ok(user, qtbot, profiles)


@pytest.mark.xfail(strict=True, reason="the tooltip stays on the first profile's description")
def test_tooltip_shows_the_chosen_profiles_description(mainwin, user, qtbot):
    # tut5:61: "Any description you'd like. Will be shown as a tooltip for the
    # profile in the Masstagging Window." Synthetic profiles.
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'A', one)
    create_profile(user, qtbot, window, 'B', two)
    create_profile(user, qtbot, window, 'C', one)
    describe(user, qtbot, window, 0, 'desc a')
    describe(user, qtbot, window, 1, 'desc b')
    pick(user, qtbot, window.profileCombo, 'B')
    assert window.profileCombo.toolTip() == 'desc b'
    pick(user, qtbot, window.profileCombo, 'C')
    assert window.profileCombo.toolTip() == ''
    pick(user, qtbot, window.profileCombo, 'A')
    assert window.profileCombo.toolTip() == 'desc a'


@pytest.mark.xfail(strict=True, reason='Cancel keeps what was done in Configure Profiles')
@pytest.mark.parametrize('change', ['add', 'edit', 'move', 'remove'])
def test_cancel_discards_the_changes(mainwin, user, qtbot, change):
    # Synthetic expectation (tut5.txt says nothing on Configure Profiles'
    # other buttons): Cancel throws away everything done in the dialog.
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'A', one)
    create_profile(user, qtbot, window, 'B', two)
    profiles = open_profiles(user, qtbot, window)
    if change == 'add':
        user.click(profiles.buttonlist.addButton)
        editor = opened(qtbot, MTProfileEdit)
        user.activate(editor)
        replace_text(user, editor._name, 'C')
        ok(user, qtbot, editor, profiles)
    elif change == 'edit':
        editor = open_row(user, qtbot, profiles, 0, 'editButton', MTProfileEdit)
        replace_text(user, editor._name, 'Z')
        ok(user, qtbot, editor, profiles)
    elif change == 'move':
        click_item(user, profiles.listbox, 1)
        user.click(profiles.buttonlist.moveupButton)
    else:
        click_item(user, profiles.listbox, 0)
        user.click(profiles.buttonlist.removeButton)
    user.click(button(profiles, 'Cancel'))
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is None)
    profiles = open_profiles(user, qtbot, window)
    assert rows(profiles.listbox) == ['A', 'B']
    assert combo_rows(window) == ['A', 'B']
    user.click(button(profiles, 'Cancel'))


@pytest.mark.xfail(strict=True, reason='Search still runs the removed profile')
def test_removing_every_profile_leaves_none_chosen(mainwin, make_audio, user, qtbot, tmp_path):
    # tut5:26: "Select a profile from the Masstagging Window."; with none
    # left the window says "Please choose a tagging profile." Synthetic files
    # and album.
    synthetic_album(make_audio, mainwin, qtbot, tmp_path)
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'A', one)
    describe(user, qtbot, window, 0, 'desc a')
    profiles = open_profiles(user, qtbot, window)
    click_item(user, profiles.listbox, 0)
    user.click(profiles.buttonlist.removeButton)
    ok(user, qtbot, profiles)
    press_search(user, mainwin, window)
    [log] = window.findChildren(QTextEdit)
    # Either line ends the run, so no thread outlives the test.
    qtbot.waitUntil(lambda: 'Please choose a tagging profile.' in log.toPlainText()
                    or 'Lookups completed.' in log.toPlainText(), timeout=10000)
    assert 'Please choose a tagging profile.' in log.toPlainText()
    assert SyntheticSource.searches == []
    no_previews(mainwin)
    assert button(window, '&Search')
    assert window.profileCombo.toolTip() == ''


@pytest.mark.xfail(strict=True,
                   reason='moving the chosen profile leaves the saved choice on the old row')
def test_the_chosen_profile_stays_chosen_after_a_move_and_a_restart(mainwin, user, qtbot, restart):
    # Synthetic expectation (tut5.txt says nothing on Configure Profiles' other
    # buttons; their tooltips say Move Up, Move Down): the chosen profile is
    # still the chosen one after it is moved and puddletag restarts.
    window = open_mass_tagging(user, mainwin, qtbot)
    create_profile(user, qtbot, window, 'A', one)
    create_profile(user, qtbot, window, 'B', two)
    pick(user, qtbot, window.profileCombo, 'B')
    profiles = open_profiles(user, qtbot, window)
    click_item(user, profiles.listbox, 1)
    user.click(profiles.buttonlist.moveupButton)
    ok(user, qtbot, profiles)

    new = restart()
    [window2] = new.findChildren(MassTagWindow)
    assert window2.profileCombo.currentText() == 'B'
