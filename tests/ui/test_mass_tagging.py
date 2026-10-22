"""The Mass Tagging window (tut5.txt), run as a user runs it: Windows →
Mass Tagging, a profile made in Configure Profiles, the files selected,
Search, then Write Previews. Two synthetic tag sources stand in for the
web ones, so nothing goes to the network. Synthetic files and albums.
"""
import os

import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QApplication, QMessageBox, QPushButton, QTextEdit

from puddlestuff import audioinfo
from puddlestuff.constants import CONFIGDIR
from puddlestuff.masstag.dialogs import MassTagEdit, MassTagWindow, MTProfileEdit, TSProfileEdit
from puddlestuff.tagsources import RetrievalError

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


@pytest.mark.xfail(strict=True, reason='a track that matches exactly the minimum track '
                                       'percentage is not matched')
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

    assert 'An error occured during the search: synthetic search failure' in log
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

    assert 'An error occured during album retrieval: synthetic retrieval failure' in log
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


@pytest.mark.xfail(strict=True, reason='a saved profile loses its filename pattern and its If no results found choice')
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
