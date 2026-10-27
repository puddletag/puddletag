"""The Tag Sources window, used as tut4.txt and tagsources.txt describe
it: select the files, Search, pick an album, check the previews, Write.
A synthetic tag source stands in for the web ones, so nothing goes to
the network; the real sources' parsing is tested on its own. Synthetic
files, albums and images.
"""
from pathlib import Path

import mutagen.id3
import pytest
from PyQt6.QtCore import QBuffer, QIODevice, QModelIndex, QPoint, Qt, QTimer, QTranslator
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import (QApplication, QCheckBox, QLabel, QMenu, QMessageBox, QPushButton, QStyle,
                             QStyleOptionViewItem)

from puddlestuff import audioinfo, tagsources
from puddlestuff.constants import CONFIGDIR, PLUGINDIR
from puddlestuff.puddleobjects import PuddleConfig
from puddlestuff.puddlesettings import SettingsDialog
from puddlestuff.tagsources import RetrievalError, write_log

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
Yes = QMessageBox.StandardButton.Yes


class Synthetic:
    """A tag source written as tagsources.txt's example plugin writes one:
    search gets the selected files grouped by album, then by artist, and
    returns albums whose tracks retrieve fetches when the user picks one.
    A test changes the instance's albums, tracks and errors."""
    group_by = ['album', 'artist']
    name = 'Synthetic'

    def __init__(self):
        self.albums = [({'#id': 'alpha', 'album': 'Alpha', 'artist': 'Band', 'year': '1999'}, []),
                       ({'#id': 'zeta', 'album': 'Zeta', 'artist': 'Band'}, [])]
        # The error the next search or retrieve raises, once.
        self.errors = {}
        # (position of the file among the selected ones, track) pairs: search
        # then returns one album whose tracks match those files exactly.
        self.exact = []
        self.keywords = []
        self.retrieved = []
        self.searches = []
        self.tracks = {
            'alpha': [{'title': 'One', 'track': '1'}, {'title': 'Two', 'track': '2'},
                      {'title': 'Three', 'track': '3'}],
            'zeta': [{'title': 'Z1', 'track': '1'}, {'title': 'Z2', 'track': '2'},
                     {'title': 'Z3', 'track': '3'}]}

    def fail(self, step):
        error = self.errors.pop(step, None)
        if error:
            raise error

    def keyword_search(self, text):
        self.keywords.append(text)
        self.fail('search')
        return [(dict(info), list(tracks)) for info, tracks in self.albums]

    def search(self, album, artists):
        write_log(f'Synthetic search: {album}')
        self.searches.append((album, {artist: len(files) for artist, files in artists.items()}))
        self.fail('search')
        if self.exact:
            files = [f for group in artists.values() for f in group]
            tracks = [dict(track, **{'#exact': files[position]}) for position, track in self.exact]
            return [({'#id': 'alpha', 'album': 'Alpha', 'artist': 'Band'}, tracks)]
        return [(dict(info), list(tracks)) for info, tracks in self.albums]

    def retrieve(self, info):
        self.retrieved.append(info['#id'])
        self.fail('retrieve')
        return info, [dict(track) for track in self.tracks[info['#id']]]


@pytest.fixture(autouse=True)
def synthetic(clean_profile):
    """Adds the synthetic source to the list the Tag Sources window builds
    its sources from, as puddletag adds a plugin's tag sources. Autouse, so
    it runs before mainwin builds the window. The window's module holds the
    list object itself, so it's changed in place, then restored."""
    saved = list(tagsources.tagsources)
    tagsources.tagsources.append(Synthetic)
    yield
    tagsources.tagsources[:] = saved


ALBUM = [{'album': 'Alpha', 'artist': 'Band', 'title': f'Old {n}'} for n in (1, 2, 3)]


def png(width):
    """A real PNG; the width tells images apart."""
    picture = QImage(width, 1, QImage.Format.Format_RGB32)
    picture.fill(0)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert picture.save(buffer, 'PNG')
    return bytes(buffer.data())


def covers(path):
    """The file's covers as mutagen reads them: (description, data)."""
    return [(p.desc, p.data) for p in mutagen.id3.ID3(str(path)).getall('APIC')]


def in_file(path):
    return audioinfo.usertags(audioinfo.Tag(str(path)))


def previews(mainwin):
    return [dict(audio.preview) for audio in mainwin._table.model().taginfo]


def the_source():
    """The window's instance of the synthetic source."""
    from puddlestuff.puddletag import status
    [source] = [s for s in status['initialized_tagsources'] if isinstance(s, Synthetic)]
    return source


def tag_sources_window():
    from puddlestuff.puddletag import status
    return status['dialogs']['Tag Sources']


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


def load(mainwin, make_audio, tmp_path, qtbot, user, tags=ALBUM, cover=None, select=True):
    """Loads one MP3 per dict of tags, opens the Tag Sources window from the
    Windows menu, picks the synthetic source and selects every file. cover:
    image data the first file holds before it's loaded."""
    music = tmp_path / 'music'
    paths = [make_audio(f'0{n}.mp3', music, **t) for n, t in enumerate(tags, 1)]
    if cover:
        tag = mutagen.id3.ID3(str(paths[0]))
        tag.add(mutagen.id3.APIC(encoding=3, mime='image/png', type=3, desc='Old', data=cover))
        tag.save()
    mainwin.openDir(str(music), False)
    qtbot.waitUntil(lambda: mainwin._table.model().rowCount() == len(paths))
    user.click_menu('Tag Sources')
    window = tag_sources_window()
    qtbot.waitUntil(window.isVisible)
    pick(user, qtbot, window.sourcelist, 'Synthetic')
    user.activate()
    if select:
        user.click_cell(user.cell(0, 'title'))
        user.press(Key.Key_A, Ctrl)
    return window, paths


def albums(window):
    """The album list's rows, as shown."""
    model = window.listbox.model()
    return [model.index(row, 0, QModelIndex()).data() for row in range(model.rowCount(QModelIndex()))]


def search(user, qtbot, window, count=2):
    """Clicks Search and waits for the albums."""
    user.click(window.searchButton)
    qtbot.waitUntil(lambda: window.searchButton.isEnabled() and len(albums(window)) == count)


def album_index(window, album):
    [row] = [row for row, shown in enumerate(albums(window)) if f' - {album}' in shown]
    return window.listbox.model().index(row, 0, QModelIndex())


def click_album(user, window, album):
    tree = window.listbox
    user.click(tree.viewport(), tree.visualRect(album_index(window, album)).center())


def button(window, text):
    [found] = [b for b in window.findChildren(QPushButton) if b.text() == text]
    return found


def box(window, text):
    [found] = [b for b in window.findChildren(QCheckBox) if b.text() == text]
    return found


def type_fields(user, window, text):
    """Replaces the Fields box's text by typing."""
    [label] = [label for label in window.findChildren(QLabel) if label.text() == '&Fields']
    user.click(label.buddy())
    user.press(Key.Key_A, Ctrl)
    user.type(text)


def pick_sort(user, qtbot, window, text):
    """Right-clicks the album list's header and picks a sort option
    (preferences.txt). The menu runs its own event loop, so the pick waits
    on a timer, as conftest's right_click does. Returns the menu's items."""
    header = window.listbox.header()
    shown = []

    def choose(tries=100):
        menu = QApplication.activePopupWidget()
        if not (isinstance(menu, QMenu) and menu.isVisible()):
            if tries:
                QTimer.singleShot(10, lambda: choose(tries - 1))
            return
        shown.append([action.text() for action in menu.actions()])
        [action] = [action for action in menu.actions() if action.text() == text]
        user.click(menu, menu.actionGeometry(action).center())

    QTimer.singleShot(0, choose)
    top = header.window()
    qtbot.mouseMove(top.windowHandle(), QPoint(5, 5))
    qtbot.mouseClick(top.windowHandle(), Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier,
                     header.mapTo(top, header.rect().center()))
    user.activate()
    assert shown, 'no menu opened'
    return shown[0]


def the_status():
    from puddlestuff.puddletag import status
    return status


def open_preferences(user, qtbot, mainwin):
    user.click_menu('&Preferences')
    qtbot.waitUntil(lambda: any(w.isVisible() for w in mainwin.findChildren(SettingsDialog)))
    [dialog] = [w for w in mainwin.findChildren(SettingsDialog) if w.isVisible()]
    user.activate(dialog)
    return dialog


def preferences_page(user, qtbot, dialog, title):
    """Opens the Preferences page with that title and returns it."""
    [row] = [r for r, w in dialog._widgets.items() if w[0] == title]
    index = dialog.model.index(row, 0)
    user.click(dialog.listbox.viewport(), dialog.listbox.visualRect(index).center())
    page = dialog._widgets[row][1]
    qtbot.waitUntil(lambda: dialog.stack.currentWidget() is page)
    return page


def close_preferences(user, qtbot, dialog):
    user.click(dialog.okbuttons.okButton)
    qtbot.waitUntil(lambda: not dialog.isVisible())
    user.activate()


# The steps tut4.txt describes.

def alpha_preview(title, track):
    return {'album': 'Alpha', 'artist': 'Band', 'title': title, 'track': track, 'year': '1999'}


ALPHA_PREVIEWS = [alpha_preview('One', '1'), alpha_preview('Two', '2'), alpha_preview('Three', '3')]
ALPHA_FILES = [{'album': ['Alpha'], 'artist': ['Band'], 'title': [title], 'track': [track], 'year': ['1999']}
               for title, track in (('One', '1'), ('Two', '2'), ('Three', '3'))]


def picked_alpha(mainwin, make_audio, tmp_path, qtbot, user, tracks=None):
    """The steps tut4.txt describes: select the files, Search, pick Alpha.
    Returns once all three previews are shown."""
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user)
    source = the_source()
    if tracks is not None:
        source.tracks['alpha'] = tracks
    search(user, qtbot, window)
    click_album(user, window, 'Alpha')
    expected = ALPHA_PREVIEWS if tracks is None else ALPHA_PREVIEWS[:len(tracks)] + [{}] * (3 - len(tracks))
    qtbot.waitUntil(lambda: previews(mainwin) == expected)
    return window, paths, source


def test_windows_menu_shows_and_hides_the_window(mainwin, make_audio, tmp_path, qtbot, user):
    # menus.txt: "Shows/Hides the Tag Sources dialog." (synthetic files)
    window, _ = load(mainwin, make_audio, tmp_path, qtbot, user, select=False)
    assert window.isVisible()

    user.click_menu('Tag Sources')

    qtbot.waitUntil(lambda: not window.isVisible())


def test_search_looks_up_the_selected_files_album_and_artists(mainwin, make_audio, tmp_path, qtbot, user):
    # tagsources.txt: "Select all the files in an album you want to tag.
    # Click on Search. The album's tag's will then be used to poll the tag
    # sources." (synthetic files and source)
    window, _ = load(mainwin, make_audio, tmp_path, qtbot, user)
    source = the_source()

    search(user, qtbot, window)

    assert source.searches == [('Alpha', {'Band': 3})]
    assert source.keywords == []
    assert albums(window) == ['Band - Alpha', 'Band - Zeta']
    assert window.label.text() == 'Searching complete.'


def test_search_box_text_is_searched_instead_of_the_files(mainwin, make_audio, tmp_path, qtbot, user):
    # tagsources.txt: "If the Search Box has *any* text, it'll be used to
    # search with instead of the selected files." (synthetic files and source)
    window, _ = load(mainwin, make_audio, tmp_path, qtbot, user)
    source = the_source()

    user.click(window.searchEdit)
    user.type('Band;Alpha')
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: window.searchButton.isEnabled() and len(albums(window)) == 2)

    assert source.keywords == ['Band;Alpha']
    assert source.searches == []


def test_search_with_nothing_selected_asks_for_files(mainwin, make_audio, tmp_path, qtbot, user):
    # The docs don't say; this is what puddletag does. (synthetic files)
    window, _ = load(mainwin, make_audio, tmp_path, qtbot, user, select=False)
    source = the_source()
    # Loading selects the first row; a click on the empty area below the
    # rows deselects it.
    user.activate()
    viewport = user.table.viewport()
    user.click(viewport, QPoint(viewport.width() // 2, viewport.height() - 5))
    qtbot.waitUntil(lambda: the_status()['selectedrows'] == [])

    user.click(window.searchButton)

    qtbot.waitUntil(lambda: window.label.text() == '<b>Select some files or enter search paramaters.</b>')
    assert source.searches == []
    assert albums(window) == []


def test_picking_an_album_previews_its_tracks_in_file_order(mainwin, make_audio, tmp_path, qtbot, user):
    # tut4.txt step 7: "Select the correct (or any really) album from the
    # Tag Sources dialog. Retrieved metadata now be matched to the selected
    # files." Step 8: "The matching process will "connect" each file to a
    # retrieved track. Going from track 1 to the end." Step 9: "puddletag
    # will now be in **Preview Mode**." (synthetic files and source)
    window, paths, source = picked_alpha(mainwin, make_audio, tmp_path, qtbot, user)

    assert previews(mainwin) == ALPHA_PREVIEWS
    assert the_status()['previewmode']
    assert source.retrieved == ['alpha']
    assert [user.cell(n, 'title').data() for n in range(3)] == ['One', 'Two', 'Three']
    assert in_file(paths[0])['title'] == ['Old 1']


def test_write_saves_the_previews_to_every_file(mainwin, make_audio, tmp_path, qtbot, user):
    # tut4.txt step 11: "Use **Write** on the Tag Sources dialog or **Write
    # Previews** from the Preview Mode menu to save the changes to file."
    # (#364; synthetic files and source)
    window, paths, _ = picked_alpha(mainwin, make_audio, tmp_path, qtbot, user)

    user.click(button(window, '&Write'))

    qtbot.waitUntil(lambda: in_file(paths[2])['title'] == ['Three'])
    assert [in_file(path) for path in paths] == ALPHA_FILES
    assert previews(mainwin) == [{}, {}, {}]
    assert not the_status()['previewmode']
    assert window.label.text() == '<b>Tags were written.</b>'


def test_write_previews_from_the_preview_mode_menu(mainwin, make_audio, tmp_path, qtbot, user):
    # tut4.txt step 11: "Use **Write** on the Tag Sources dialog or **Write
    # Previews** from the Preview Mode menu to save the changes to file."
    # (synthetic files and source)
    window, paths, _ = picked_alpha(mainwin, make_audio, tmp_path, qtbot, user)

    user.click_menu('&Write Previews')

    qtbot.waitUntil(lambda: in_file(paths[2])['title'] == ['Three'])
    assert [in_file(path) for path in paths] == ALPHA_FILES


def test_picking_a_track_previews_it_on_the_selected_file(mainwin, make_audio, tmp_path, qtbot, user):
    # tut4.txt step 10: "You can tag individual tracks by selecting the
    # track in the File-View and then clicking on the corresponding track in
    # the Tag Source's track list." (synthetic files and source)
    window, _, _ = picked_alpha(mainwin, make_audio, tmp_path, qtbot, user)
    tree = window.listbox
    # The album click leaves the focus on the Search button, so the keyboard
    # can't expand it: click its arrow, left of the row.
    rect = tree.visualRect(album_index(window, 'Alpha'))
    user.click(tree.viewport(), QPoint(rect.left() - tree.indentation() // 2, rect.center().y()))
    qtbot.waitUntil(lambda: tree.isExpanded(album_index(window, 'Alpha')))
    user.activate()
    # Row 2 holds Three's preview; picking track 2 replaces it with Two's.
    user.click_cell(user.cell(2, 'title'))
    track = tree.model().index(1, 0, album_index(window, 'Alpha'))

    user.click(tree.viewport(), tree.visualRect(track).center())

    qtbot.waitUntil(lambda: previews(mainwin)[2] == alpha_preview('Two', '2'))
    assert previews(mainwin)[:2] == ALPHA_PREVIEWS[:2]


def test_files_beyond_the_last_track_get_nothing(mainwin, make_audio, tmp_path, qtbot, user):
    # tut4.txt step 8: "The matching process will "connect" each file to a
    # retrieved track. Going from track 1 to the end." The docs don't say
    # what happens past the last track; this is what puddletag does.
    # (synthetic files and source)
    tracks = [{'title': 'One', 'track': '1'}, {'title': 'Two', 'track': '2'}]

    picked_alpha(mainwin, make_audio, tmp_path, qtbot, user, tracks)

    assert previews(mainwin) == [alpha_preview('One', '1'), alpha_preview('Two', '2'), {}]


def test_clear_preview_exits_preview_mode(mainwin, make_audio, tmp_path, qtbot, user, dialogs):
    # tagsources.txt: "Clear preview does as it says and exits preview
    # mode." (synthetic files and source)
    window, paths, _ = picked_alpha(mainwin, make_audio, tmp_path, qtbot, user)
    dialogs.answer('QMessageBox.question', Yes)

    user.click(button(window, 'Clea&r preview'))

    qtbot.waitUntil(lambda: previews(mainwin) == [{}, {}, {}])
    assert not the_status()['previewmode']
    assert [in_file(path)['title'] for path in paths] == [[f'Old {n}'] for n in (1, 2, 3)]


def test_album_tracks_are_retrieved_once(mainwin, make_audio, tmp_path, qtbot, user):
    # tagsources.txt: "Lists the retrieved albums. Click on an album to
    # retrieve metadata." The docs don't say what a second click does; this
    # is what puddletag does (#686). (synthetic files and source)
    window, _, source = picked_alpha(mainwin, make_audio, tmp_path, qtbot, user)

    click_album(user, window, 'Alpha')
    qtbot.wait(500)

    model = window.listbox.model()
    alpha = album_index(window, 'Alpha')
    assert source.retrieved == ['alpha']
    assert model.rowCount(alpha) == 3
    assert model.index(0, 0, alpha).data() == '1 - One'
    assert albums(window)[0] == 'Band - Alpha[3]'


# The Fields box, Update empty fields only and covers.

UPDATE_EMPTY = 'Update empty fields only.'


def with_genre(source):
    """Every track of Alpha carries the genre Pop."""
    source.tracks['alpha'] = [dict(track, genre='Pop') for track in source.tracks['alpha']]


def write_all(user, qtbot, window, paths, titles):
    """Clicks Write and waits until the files hold the titles."""
    user.activate()
    user.click(button(window, '&Write'))
    qtbot.waitUntil(lambda: [in_file(path).get('title') for path in paths] == [[t] for t in titles])


def test_fields_box_writes_only_the_listed_fields(mainwin, make_audio, tmp_path, qtbot, user):
    # "Enter a comma separated list of fields to retrieve only those field.
    # Eg. artist, title, album, genre" (tut4.txt). Synthetic album and tracks.
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user)
    with_genre(the_source())
    type_fields(user, window, 'title, genre')
    search(user, qtbot, window)
    click_album(user, window, 'Alpha')
    expected = [{'genre': 'Pop', 'title': title} for title in ('One', 'Two', 'Three')]
    qtbot.waitUntil(lambda: previews(mainwin) == expected)
    write_all(user, qtbot, window, paths, ('One', 'Two', 'Three'))
    assert in_file(paths[0]) == {'album': ['Alpha'], 'artist': ['Band'], 'genre': ['Pop'],
                                 'title': ['One']}


def test_fields_box_tilde_writes_all_but_the_listed_fields(mainwin, make_audio, tmp_path, qtbot, user):
    # "use the tilde character ("~") followed by a comma delimited list of
    # fields you'd like to exclude ... if you entered ~genre,album and the Tag
    # Source returned a tag with artist, title, album, track, genre fields.
    # Only the artist, title, track fields would be written to the files"
    # (tut4.txt). Synthetic album and tracks.
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user)
    with_genre(the_source())
    type_fields(user, window, '~genre,album')
    search(user, qtbot, window)
    click_album(user, window, 'Alpha')
    expected = [{'artist': 'Band', 'title': title, 'track': str(n), 'year': '1999'}
                for n, title in enumerate(('One', 'Two', 'Three'), 1)]
    qtbot.waitUntil(lambda: previews(mainwin) == expected)


def test_update_empty_fields_only_keeps_values_in_the_files(mainwin, make_audio, tmp_path, qtbot, user):
    # "Check this box and only fields that aren't already in the file will
    # get updated." (tagsources.txt) and "If you want to prevent existing
    # values from being overwritten ensure Update empty fields only is
    # checked." (tut4.txt). Synthetic files, album and tracks.
    tags = [{'album': 'Alpha', 'artist': 'Band', 'title': 'Mine'},
            {'album': 'Alpha', 'artist': 'Band'},
            {'album': 'Alpha', 'artist': 'Band', 'genre': 'Rock'}]
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user, tags)
    with_genre(the_source())
    user.click(box(window, UPDATE_EMPTY))
    search(user, qtbot, window)
    click_album(user, window, 'Alpha')
    expected = [{'genre': 'Pop', 'track': '1', 'year': '1999'},
                {'genre': 'Pop', 'title': 'Two', 'track': '2', 'year': '1999'},
                {'title': 'Three', 'track': '3', 'year': '1999'}]
    qtbot.waitUntil(lambda: previews(mainwin) == expected)
    write_all(user, qtbot, window, paths, ('Mine', 'Two', 'Three'))
    assert in_file(paths[0])['title'] == ['Mine']
    assert in_file(paths[2])['genre'] == ['Rock']


def test_update_empty_fields_only_after_another_album(mainwin, make_audio, tmp_path, qtbot, user):
    # "Check this box and only fields that aren't already in the file will
    # get updated." (tagsources.txt). Synthetic files and albums: the files
    # have no title or track, so Alpha previews both again after Zeta's.
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user, [{'album': 'Alpha', 'artist': 'Band'}] * 3)
    user.click(box(window, UPDATE_EMPTY))
    search(user, qtbot, window)
    click_album(user, window, 'Alpha')
    qtbot.waitUntil(lambda: [p.get('title') for p in previews(mainwin)] == ['One', 'Two', 'Three'])
    click_album(user, window, 'Zeta')
    qtbot.waitUntil(lambda: [p.get('title') for p in previews(mainwin)] == ['Z1', 'Z2', 'Z3'])
    click_album(user, window, 'Alpha')
    qtbot.wait(500)
    assert previews(mainwin) == [{'title': title, 'track': str(n), 'year': '1999'}
                                 for n, title in enumerate(('One', 'Two', 'Three'), 1)]


def test_update_empty_fields_only_with_exact_matches(mainwin, make_audio, tmp_path, qtbot, user):
    # "Check this box and only fields that aren't already in the file will
    # get updated." (tagsources.txt). Synthetic files and matches, given for
    # the last file first.
    tags = [{'album': 'Alpha', 'artist': 'Band', 'title': 'T1'},
            {'album': 'Alpha', 'artist': 'Band'},
            {'album': 'Alpha', 'artist': 'Band', 'genre': 'Rock'}]
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user, tags)
    the_source().exact = [(position, {'artist': 'New', 'genre': 'G', 'title': f'E{position}'})
                          for position in (2, 1, 0)]
    type_fields(user, window, 'artist, title')
    user.click(box(window, UPDATE_EMPTY))
    user.click(window.searchButton)
    qtbot.waitUntil(lambda: previews(mainwin) == [{}, {'title': 'E1'}, {'title': 'E2'}])


def test_fields_box_retrieves_only_the_cover(mainwin, make_audio, tmp_path, qtbot, user):
    # "Enter a comma separated list of fields to retrieve only those field"
    # (tut4.txt) and the Fields box's tooltip: "Eg ~composer, __image will
    # write all fields but the composer and __image fields." (#402).
    # Synthetic album and image.
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user)
    the_source().albums[0][0]['__image'] = [{'data': png(9)}]
    type_fields(user, window, '__image')
    search(user, qtbot, window)
    click_album(user, window, 'Alpha')
    qtbot.waitUntil(lambda: [sorted(p) for p in previews(mainwin)] == [['__image']] * 3)
    write_all(user, qtbot, window, paths, ('Old 1', 'Old 2', 'Old 3'))
    qtbot.waitUntil(lambda: all(covers(path) == [('', png(9))] for path in paths))
    for path in paths:
        [image] = audioinfo.Tag(str(path)).images
        assert (image['mime'], image['imagetype']) == ('image/png', 3)
    assert [in_file(path)['title'] for path in paths] == [[f'Old {n}'] for n in (1, 2, 3)]


def test_fields_without_the_cover_keep_the_files_cover(mainwin, make_audio, tmp_path, qtbot, user):
    # "Enter a comma separated list of fields to retrieve only those field.
    # Eg. artist, title, album, genre" (tut4.txt), so the cover isn't
    # touched (#383). Synthetic album and image.
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user, cover=png(5))
    type_fields(user, window, 'artist, title')
    search(user, qtbot, window)
    click_album(user, window, 'Alpha')
    qtbot.waitUntil(lambda: [p.get('title') for p in previews(mainwin)] == ['One', 'Two', 'Three'])
    write_all(user, qtbot, window, paths, ('One', 'Two', 'Three'))
    assert covers(paths[0]) == [('Old', png(5))]
    assert in_file(paths[0])['title'] == ['One']


def test_exact_matches_keep_the_files_cover(mainwin, make_audio, tmp_path, qtbot, user):
    # "Enter a comma separated list of fields to retrieve only those field.
    # Eg. artist, title, album, genre" (tut4.txt) and "Lookups are done by
    # album, but you can select metadata by track too." (tagsources.txt):
    # the path AcoustID takes (#383). Synthetic files, matches and image.
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user, cover=png(5))
    the_source().exact = [(position, {'artist': 'New', 'title': f'E{position}'}) for position in (0, 1, 2)]
    type_fields(user, window, 'artist, title')
    search(user, qtbot, window, 1)
    qtbot.waitUntil(lambda: previews(mainwin) == [{'artist': 'New', 'title': f'E{n}'} for n in (0, 1, 2)])
    model = window.listbox.model()
    parent = album_index(window, 'Alpha')
    assert [model.index(n, 0, parent).data(Qt.ItemDataRole.CheckStateRole) for n in (0, 1, 2)] \
        == [Qt.CheckState.Checked] * 3
    write_all(user, qtbot, window, paths, ('E0', 'E1', 'E2'))
    assert covers(paths[0]) == [('Old', png(5))]


# Errors and the Logs dock.

def logs_text():
    return the_status()['dialogs']['Logs']._text.toPlainText()


def fail_to_search(user, qtbot, window, error, label):
    """Makes the next search raise the error, clicks Search and waits for the
    label to show the failure."""
    the_source().errors['search'] = error
    user.click(window.searchButton)
    qtbot.waitUntil(lambda: bool(window.searchButton.isEnabled() and window.label.text() == label))


def fail_to_retrieve(user, qtbot, window, error, label):
    """Searches, makes the next retrieval raise the error, clicks Alpha and
    waits for the label to show the failure."""
    search(user, qtbot, window)
    the_source().errors['retrieve'] = error
    click_album(user, window, 'Alpha')
    qtbot.waitUntil(lambda: window.label.text() == label)


def test_search_error_is_shown_in_the_window(mainwin, make_audio, tmp_path, qtbot, user, dialogs):
    # The docs don't say what the window does when a search fails; this is what
    # puddletag does. tagsources.txt's example plugin: "Raise
    # puddlestuff.tagsources.RetrievalError if an error occurs. It accepts a
    # message the only argument (may be html)." Synthetic source and error.
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user)
    fail_to_search(user, qtbot, window, RetrievalError('<b>Synthetic failure</b>'),
                   'An error occured: <b>Synthetic failure</b>')
    assert albums(window) == []
    assert window.searchButton.isEnabled()
    assert dialogs.calls == []


def test_unhandled_search_error_is_shown_in_the_window(mainwin, make_audio, tmp_path, qtbot, user, dialogs):
    # The docs don't say; this is what puddletag does (the traceback on stderr
    # is expected). Synthetic source and error.
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user)
    fail_to_search(user, qtbot, window, RuntimeError('Synthetic crash'),
                   'An unhandled error occurred: Synthetic crash')
    assert albums(window) == []
    assert window.searchButton.isEnabled()
    assert dialogs.calls == []


def test_retrieval_error_is_shown_and_the_album_can_be_retried(mainwin, make_audio, tmp_path, qtbot, user):
    # The docs don't say what a failed retrieval does; this is what puddletag
    # does. tagsources.txt's example plugin: "Raise
    # puddlestuff.tagsources.RetrievalError if an error occurs." Synthetic
    # source and error.
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user)
    source = the_source()
    fail_to_retrieve(user, qtbot, window, RetrievalError('Synthetic failure'),
                     'An error occured: Synthetic failure')
    assert previews(mainwin) == [{}, {}, {}]
    assert [in_file(p)['title'] for p in paths] == [['Old 1'], ['Old 2'], ['Old 3']]

    click_album(user, window, 'Alpha')
    expected = [{'album': 'Alpha', 'artist': 'Band', 'title': title, 'track': track, 'year': '1999'}
                for title, track in (('One', '1'), ('Two', '2'), ('Three', '3'))]
    qtbot.waitUntil(lambda: previews(mainwin) == expected)
    assert source.retrieved == ['alpha', 'alpha']
    assert window.label.text() == 'Retrieval complete.'


def test_unhandled_retrieval_error_is_shown_in_the_window(mainwin, make_audio, tmp_path, qtbot, user):
    # The docs don't say; this is what puddletag does (the traceback on stderr
    # is expected). Synthetic source and error.
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user)
    fail_to_retrieve(user, qtbot, window, RuntimeError('Synthetic crash'),
                     'An unhandled error occured: Synthetic crash')
    assert previews(mainwin) == [{}, {}, {}]


def test_failed_retrieval_keeps_the_album_expandable(mainwin, make_audio, tmp_path, qtbot, user):
    # The docs are silent; an album with tracks to fetch has an expand arrow
    # before the click, and a failed click shouldn't take it away. Synthetic
    # source and error.
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user)
    fail_to_retrieve(user, qtbot, window, RetrievalError('Synthetic failure'),
                     'An error occured: Synthetic failure')
    assert window.listbox.model().hasChildren(album_index(window, 'Alpha'))


def test_source_messages_go_to_the_logs(mainwin, make_audio, tmp_path, qtbot, user):
    # menus.txt: "Logs: Currently displays extra info from Tag Sources."
    # Synthetic source and message.
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user)
    user.click_menu('Logs')
    logs = the_status()['dialogs']['Logs']
    qtbot.waitUntil(logs.isVisible)
    search(user, qtbot, window)
    qtbot.waitUntil(lambda: 'Synthetic search: Alpha' in logs._text.toPlainText())


def test_album_with_brackets_is_searched_again_without_them(mainwin, make_audio, tmp_path, qtbot, user, monkeypatch):
    # The docs don't say; this is what puddletag does: an album that finds
    # nothing and has a bracketed part is searched again without it. Synthetic
    # album name and source.
    tags = [{'album': 'Alpha (Deluxe)', 'artist': 'Band', 'title': f'Old {n}'} for n in (1, 2, 3)]
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user, tags=tags)
    source = the_source()
    real = source.search
    monkeypatch.setattr(source, 'search',
                        lambda album, artists: [] if album == 'Alpha (Deluxe)' else real(album, artists))
    search(user, qtbot, window)
    assert source.searches == [('Alpha', {'Band': 3})]
    assert len(albums(window)) == 2
    assert 'Retrying search with Alpha' in logs_text()


# Sorting the retrieved albums

THREE_ALBUMS = [({'album': 'B', 'artist': 'Zed'}, []),
                ({'album': 'C', 'artist': 'Abe'}, []),
                ({'album': 'A', 'artist': 'Moe'}, [])]


def header_text(window):
    return window.listbox.model().headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)


def stripped(window):
    """The albums as shown, without the trailing space the Preferences
    page's album pattern adds once the user has pressed OK there."""
    return [shown.strip() for shown in albums(window)]


def test_albums_are_sorted_by_artist_then_album(mainwin, make_audio, tmp_path, qtbot, user):
    # preferences.txt: "Sort retrieved albums using order: Will sort the
    # retrieved album by the order listed." The default order is the
    # page's first item, `artist, album` (the docs don't list the
    # defaults). Synthetic albums.
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user)
    the_source().albums = THREE_ALBUMS
    search(user, qtbot, window, 3)

    assert albums(window) == ['Abe - C', 'Moe - A', 'Zed - B']
    assert header_text(window) == 'Retrieved Albums (sorted by artist / album)'


def test_header_right_click_sorts_by_another_option(mainwin, make_audio, tmp_path, qtbot, user):
    # preferences.txt: "You can change the order dynamically by right
    # clicking on the header of the Tag Sources dialog's album list and
    # choosing from the sort options you defined." Synthetic albums.
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user)
    the_source().albums = THREE_ALBUMS
    search(user, qtbot, window, 3)

    assert pick_sort(user, qtbot, window, 'album/artist') == ['artist/album', 'album/artist']

    assert albums(window) == ['Moe - A', 'Zed - B', 'Abe - C']
    assert header_text(window) == 'Retrieved Albums (sorted by album / artist)'


def test_sort_option_from_preferences_is_kept_after_a_restart(mainwin, make_audio, tmp_path, qtbot, user,
                                                               restart):
    # preferences.txt: "Sort retrieved albums using order: Will sort the
    # retrieved album by the order listed." #258: "When puddletag is
    # opened, the first retrieved albums are not being sorted according to
    # the preferences set in: Edit -> Preferences -> Tag Sources -> Sort
    # retrieved albums using order". Synthetic albums.
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user)
    the_source().albums = THREE_ALBUMS
    search(user, qtbot, window, 3)

    dialog = open_preferences(user, qtbot, mainwin)
    page = preferences_page(user, qtbot, dialog, 'Tag Sources')
    pick(user, qtbot, page._sortoptions, 'album, artist')
    close_preferences(user, qtbot, dialog)
    assert stripped(window) == ['Moe - A', 'Zed - B', 'Abe - C']

    win = restart()
    user = type(user)(qtbot, win)
    window = tag_sources_window()
    if not window.isVisible():
        user.click_menu('Tag Sources')
        qtbot.waitUntil(window.isVisible)
    assert window.sourcelist.currentText() == 'Synthetic'
    the_source().albums = THREE_ALBUMS
    user.activate(win)
    user.click(window.searchEdit)
    user.type('Band;')
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: window.searchButton.isEnabled() and len(albums(window)) == 3)

    assert stripped(window) == ['Moe - A', 'Zed - B', 'Abe - C']


def test_preferences_ok_keeps_the_header_sort(mainwin, make_audio, tmp_path, qtbot, user):
    # preferences.txt: "You can change the order dynamically by right
    # clicking on the header of the Tag Sources dialog's album list and
    # choosing from the sort options you defined." Opening Preferences and
    # clicking OK without touching anything keeps that order. Synthetic
    # albums.
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user)
    the_source().albums = THREE_ALBUMS
    search(user, qtbot, window, 3)
    pick_sort(user, qtbot, window, 'album/artist')

    dialog = open_preferences(user, qtbot, mainwin)
    close_preferences(user, qtbot, dialog)

    assert stripped(window) == ['Moe - A', 'Zed - B', 'Abe - C']


# Automatic retrieval, the default source and the album tooltip.

def test_automatic_retrieval_previews_the_best_album(mainwin, make_audio, tmp_path, qtbot, user):
    # tagsources.txt: "7. If checked, the album that best matches the retrieved
    # albums will be automatically retrieved." preferences.txt: "If automatic
    # retrieval of albums is enabled in the Tag Sources dialog, then the options
    # you specify here will be used to determine which album best matches.
    # Options are as used in Masstagging." Synthetic files and albums.
    tags = [{'album': 'Alpha', 'artist': 'Band', 'title': t} for t in ('One', 'Two', 'Three')]
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user, tags=tags)
    source = the_source()
    source.tracks['alpha'] = [{'artist': 'Band', 'genre': 'Pop', 'title': t, 'track': n}
                              for t, n in (('One', '1'), ('Two', '2'), ('Three', '3'))]
    user.click(box(window, 'Automatically retrieve matches.'))
    user.click(window.searchButton)
    qtbot.waitUntil(lambda: source.retrieved == ['alpha'] and window.label.text() == 'Retrieval complete.')
    expected = [{'album': 'Alpha', 'artist': 'Band', 'genre': 'Pop', 'title': t, 'track': n,
                 'year': '1999'} for t, n in (('One', '1'), ('Two', '2'), ('Three', '3'))]
    qtbot.waitUntil(lambda: previews(mainwin) == expected, timeout=2000)


def test_fresh_profile_starts_on_musicbrainz(mainwin, qtbot, user):
    # The docs don't say; this is what puddletag should do: a fresh profile
    # opens the Tag Sources window on MusicBrainz, the source listed for it.
    user.click_menu('Tag Sources')
    window = tag_sources_window()
    qtbot.waitUntil(window.isVisible)
    assert window.sourcelist.currentText() == 'MusicBrainz'


def test_album_tooltip_shows_the_fields_to_write(mainwin, make_audio, tmp_path, qtbot, user):
    # tagsources.txt: "Hover over an album/track to see an overview of the
    # metadata that'll get written." Synthetic files and albums.
    window, paths = load(mainwin, make_audio, tmp_path, qtbot, user)
    source = the_source()
    search(user, qtbot, window)
    click_album(user, window, 'Alpha')
    qtbot.waitUntil(lambda: source.retrieved == ['alpha'] and window.label.text() == 'Retrieval complete.')
    tooltip = album_index(window, 'Alpha').data(Qt.ItemDataRole.ToolTipRole)
    assert tooltip == '<b>album</b>: Alpha<br /><b>artist</b>: Band<br /><b>year</b>: 1999<br />'


# A tag source plugin.

PLUGIN_INFO = """[info]
author = Synthetic Author
description = A tag source in the user's plugin folder
name = Synthetic Plugin
puddletag_version = 2.0
version = 1.0
"""

PLUGIN_CODE = """class PluginSource:
    group_by = ['album']
    name = 'Plugin Source'

    def search(self, album, artists):
        return []


tagsources = [PluginSource]
"""


@pytest.fixture
def user_plugin(clean_profile):
    """A tag source plugin in the user's plugin folder, written before
    mainwin builds the window."""
    folder = Path(PLUGINDIR) / 'synthetic_plugin_source'
    folder.mkdir(parents=True)
    (folder / 'info').write_text(PLUGIN_INFO)
    (folder / '__init__.py').write_text(PLUGIN_CODE)


def test_tag_source_plugin_appears_in_the_source_list(user_plugin, mainwin, user, qtbot, restart):
    # plugins.txt: "puddletag plugins are stored in ~/.puddletag/plugins"
    # and the example's "tagsources = [Amazon]": "Required in order to let
    # your tagsource be loaded." The plugin is synthetic.
    dialog = open_preferences(user, qtbot, mainwin)
    page = preferences_page(user, qtbot, dialog, 'Plugins')

    listbox = page._listbox
    [item] = listbox.findItems('Synthetic Plugin', Qt.MatchFlag.MatchExactly)
    option = QStyleOptionViewItem()
    listbox.initViewItemOption(option)
    option.rect = listbox.visualItemRect(item)
    option.features |= QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
    check_box = listbox.style().subElementRect(QStyle.SubElement.SE_ItemViewItemCheckIndicator, option, listbox)
    user.click(listbox.viewport(), check_box.center())
    assert item.checkState() == Qt.CheckState.Checked
    user.click(dialog.okbuttons.okButton)
    qtbot.waitUntil(lambda: not dialog.isVisible())

    restart()

    window = tag_sources_window()
    shown = [window.sourcelist.itemText(n) for n in range(window.sourcelist.count())]
    assert 'Plugin Source' in shown


# Built-in tag sources.

def test_source_list_offers_the_built_in_sources(user, qtbot):
    # tagsources.txt: "Included with puddletag are tag sources supporting
    # lookups from Discogs, FreeDB, MusicBrainz and AcoustID." AcoustID is
    # listed only where fpcalc is installed (tagsources.txt: "you need to
    # have chromaprint (specifically the fpcalc binary) installed").
    user.click_menu('Tag Sources')
    window = tag_sources_window()
    qtbot.waitUntil(window.isVisible)
    listed = {window.sourcelist.itemText(n) for n in range(window.sourcelist.count())}
    assert listed - {'AcoustID'} == {'Discogs.com', 'FreeDB', 'MusicBrainz', 'Synthetic'}


@pytest.fixture(params=['AllMusic.com', 'Amazon'])
def gone_source_saved(request, clean_profile):
    """tagsources.conf as puddletag saved it when the user last used a
    source it no longer has: the window's last source and that
    source's fields. Synthetic."""
    config = PuddleConfig(str(Path(CONFIGDIR) / 'tagsources.conf'))
    config.set('tagsources', 'lastsource', request.param)
    config.set('tagsourcetags', request.param, ['album'])
    return request.param


def test_saved_source_that_is_gone_opens_on_musicbrainz(gone_source_saved, mainwin, user, qtbot):
    # The docs are silent: tut4.txt and tagsources.txt say only "Choose a
    # tag source". A fresh profile opens on MusicBrainz, so a saved source
    # that is no longer there does too.
    user.click_menu('Tag Sources')
    window = tag_sources_window()
    qtbot.waitUntil(window.isVisible)
    assert window.sourcelist.currentText() == 'MusicBrainz'


def test_musicbrainz_cover_sizes_keep_their_translation(qtbot):
    # The docs are silent on translations. The expected words are the German
    # translators' (puddletag_de.ts). These are the sizes MusicBrainz's
    # Configure dialog (the button beside the Source combo) offers.
    from puddlestuff.tagsources.musicbrainz import MusicBrainz
    translator = QTranslator()
    assert translator.load('translations:puddletag_de.qm')
    QApplication.installTranslator(translator)
    try:
        [label, kind, (sizes, default)] = MusicBrainz().preferences[1]
    finally:
        QApplication.removeTranslator(translator)
    assert sizes == ['klein', 'groß', 'Ursprüngliche Größe']
