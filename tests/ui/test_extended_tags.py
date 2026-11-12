"""Extended Tags (Edit->Extended Tags, Ctrl+E) and the Extended Tags
plugin's dock, used as a user uses them: the list's buttons and its Edit
Field dialog, the picture's buttons, OK and Cancel, then the File-View and
the files checked. menus.txt: "Open's the Extended Tags Dialog. With it
you can edit/see all the supported fields in a file." Synthetic files and
images.
"""
import mutagen.flac
import mutagen.id3
import pytest
from PyQt6.QtCore import QBuffer, QIODevice, Qt
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication, QMessageBox, QPushButton

from puddlestuff import audioinfo
from puddlestuff.helperwin import EditField, ExTags
from puddlestuff.mainwin.artwork import ArtworkWidget
from puddlestuff.puddleobjects import PuddleConfig

pytestmark = pytest.mark.ui

Key = Qt.Key
Alt = Qt.KeyboardModifier.AltModifier
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier
No = QMessageBox.StandardButton.No

ADDED = (255, 255, 0)
EDITED = (0, 255, 0)
REMOVED = (255, 0, 0)


def image(width):
    """A real PNG, so that its MIME type can be told from its data; the
    width tells images apart."""
    picture = QImage(width, 1, QImage.Format.Format_RGB32)
    picture.fill(0)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert picture.save(buffer, 'PNG')
    return bytes(buffer.data())


FRONT = {'data': image(10), 'description': 'Front', 'imagetype': 3, 'mime': 'image/png'}
BACK = {'data': image(20), 'description': 'Back', 'imagetype': 4, 'mime': 'image/png'}


def put(path, *covers):
    """Covers as another program writes them, with mutagen (MP3)."""
    tags = mutagen.id3.ID3(str(path))
    for cover in covers:
        tags.add(mutagen.id3.APIC(encoding=3, mime=cover['mime'], type=cover['imagetype'],
                                  desc=cover['description'], data=cover['data']))
    tags.save()


def stored(path):
    """The covers an MP3 keeps, as mutagen reads them."""
    return [{'data': p.data, 'description': p.desc, 'imagetype': p.type, 'mime': p.mime}
            for p in mutagen.id3.ID3(str(path)).getall('APIC')]


def in_file(path):
    return audioinfo.usertags(audioinfo.Tag(str(path)))


@pytest.fixture
def load(mainwin, make_audio, tmp_path, qtbot, user):
    """load({'title': 'T1'}, {'title': 'T2', 'covers': [FRONT]}) makes one
    MP3 per dict (01.mp3, 02.mp3, ...) with its tags and covers, loads them
    and selects them all. Synthetic."""
    def load(*files):
        music = tmp_path / 'music'
        paths = []
        for number, tags in enumerate(files, 1):
            tags = dict(tags)
            covers = tags.pop('covers', [])
            path = make_audio(f'0{number}.mp3', music, **tags)
            if covers:
                put(path, *covers)
            paths.append(path)
        mainwin.openDir(str(music), False)
        qtbot.waitUntil(lambda: mainwin._table.model().rowCount() == len(paths))
        user.activate()
        user.click_cell(user.cell(0, 'title'))
        if len(paths) > 1:
            user.click_cell(user.cell(len(paths) - 1, 'title'), Shift)
        return paths
    return load


def opened(qtbot, kind=ExTags):
    """The visible window of this kind (Extended Tags, or its Edit Field
    dialog) once it shows; closed ones stay among the top-level widgets."""
    qtbot.waitUntil(lambda: any(isinstance(w, kind) and w.isVisible()
                                for w in QApplication.topLevelWidgets()))
    [window] = [w for w in QApplication.topLevelWidgets() if isinstance(w, kind) and w.isVisible()]
    return window


def open_window(user, qtbot):
    """Ctrl+E on the File-View's selection; the window, active."""
    user.press(Key.Key_E, Ctrl)
    window = opened(qtbot)
    user.activate(window)
    return window


def rows(window):
    """(field, value) per row, top to bottom; a list's value is the entry
    it shows."""
    return [window.get_field(row) for row in range(window.table.rowCount())]


def row_of(window, field, value=None):
    [row] = [r for r in range(window.table.rowCount()) if window.get_field(r)[0] == field
             and value in (None, window.get_field(r)[1])]
    return row


def entries(window, field):
    """The entries of the field's list (its values differ between files)."""
    combo = window.table.cellWidget(row_of(window, field), 1)
    return [combo.itemText(i) for i in range(combo.count())]


def colour(window, row):
    """The row's background as Preferences > Colours sets it."""
    return window.table.item(row, 0).background().color().getRgb()[:3]


def click_row(user, window, row, modifier=Qt.KeyboardModifier.NoModifier):
    item = window.table.item(row, 0)
    user.click(window.table.viewport(), window.table.visualItemRect(item).center(), modifier)


def double_click_row(user, window, row):
    item = window.table.item(row, 0)
    user.double_click(window.table.viewport(), window.table.visualItemRect(item).center())


def fill_field(user, qtbot, field=None, value=None, button='A&dd'):
    """In the Edit Field dialog that just opened: types field over the
    Field box's text (Alt+F) and value over the Value box's (Alt+V), then
    clicks the button ('A&dd' for Add and Duplicate, 'E&dit' for Edit)."""
    dialog = opened(qtbot, EditField)
    user.activate(dialog)
    if field is not None:
        user.press(Key.Key_F, Alt)
        user.press(Key.Key_A, Ctrl)
        user.type(field)
    if value is not None:
        user.press(Key.Key_V, Alt)
        user.press(Key.Key_A, Ctrl)
        user.type(value)
    [ok] = [b for b in dialog.findChildren(QPushButton) if b.text() == button]
    user.click(ok)


def pick(user, qtbot, combo, text):
    """Opens the list and clicks the entry, as test_plugins.py does."""
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


def shown(user, row, field):
    """A File-View cell's text and how it's shown: bold, italic or plain."""
    model = user.table.model()
    index = user.cell(row, field)
    font = model.data(index, Qt.ItemDataRole.FontRole)
    return model.data(index), 'bold' if font.bold() else 'italic' if font.italic() else 'plain'


def style(window, row):
    """How the window shows the row's value: bold, italic or plain."""
    font = window.table.item(row, 1).font()
    return 'bold' if font.bold() else 'italic' if font.italic() else 'plain'


def add_field(user, qtbot, window, field, value):
    """The Add button, then the Edit Field dialog filled and added."""
    user.click(window.listbuttons.addButton)
    fill_field(user, qtbot, field, value)


def edit_field(user, qtbot, window, field, value):
    """Double-clicks the field's row and types value over the dialog's."""
    double_click_row(user, window, row_of(window, field))
    fill_field(user, qtbot, value=value, button='E&dit')


def test_add_field(load, user, qtbot, mainwin):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can
    # edit/see all the supported fields in a file." Docs silent on the
    # row: the maintainer's call is a new row, coloured as added, written
    # on OK.
    [path] = load({'album': 'Album', 'title': 'T1'})
    win = open_window(user, qtbot)
    add_field(user, qtbot, win, 'genre', 'Rock')
    assert rows(win) == [('album', 'Album'), ('genre', 'Rock'), ('title', 'T1')]
    assert colour(win, 1) == ADDED
    user.activate(win)
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: 'genre' in in_file(path))
    assert in_file(path) == {'album': ['Album'], 'genre': ['Rock'], 'title': ['T1']}
    assert mainwin._table.model().taginfo[0]['genre'] == ['Rock']


def test_edit_field_with_the_edit_button(load, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can
    # edit/see all the supported fields in a file." Docs silent on the
    # colour: the maintainer's call is an edited row is coloured as edited.
    [path] = load({'album': 'Album', 'title': 'T1'})
    win = open_window(user, qtbot)
    click_row(user, win, row_of(win, 'album'))
    user.click(win.listbuttons.editButton)
    fill_field(user, qtbot, value='New', button='E&dit')
    assert ('album', 'New') in rows(win)
    assert colour(win, row_of(win, 'album')) == EDITED
    user.activate(win)
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: in_file(path)['album'] == ['New'])
    assert in_file(path)['title'] == ['T1']


def test_duplicate_field(load, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can
    # edit/see all the supported fields in a file." Docs silent; the
    # maintainer's call: Duplicate copies the field and value into Edit
    # Field and the value typed is added as another value of the field.
    [path] = load({'genre': 'Rock', 'title': 'T1'})
    win = open_window(user, qtbot)
    click_row(user, win, row_of(win, 'genre'))
    user.click(win.listbuttons.duplicateButton)
    dialog = opened(qtbot, EditField)
    assert dialog.tagcombo.currentText() == 'genre'
    assert dialog.value.toPlainText() == 'Rock'
    fill_field(user, qtbot, value='Jazz')
    assert [row for row in rows(win) if row[0] == 'genre'] == [('genre', 'Rock'), ('genre', 'Jazz')]
    user.activate(win)
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: in_file(path).get('genre') == ['Rock', 'Jazz'])


@pytest.mark.parametrize('how', ['button', 'Delete'])
def test_remove_field(how, load, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can
    # edit/see all the supported fields in a file." Docs silent; the
    # maintainer's call: a removed row stays, marked, until OK.
    [path] = load({'album': 'Album', 'genre': 'Rock', 'title': 'T1'})
    win = open_window(user, qtbot)
    click_row(user, win, row_of(win, 'genre'))
    if how == 'button':
        user.click(win.listbuttons.removeButton)
    else:
        user.press(Key.Key_Delete)
    # A shortcut presses the button with animateClick: a moment later.
    qtbot.waitUntil(lambda: colour(win, row_of(win, 'genre')) == REMOVED)
    assert ('genre', 'Rock') in rows(win)
    user.activate(win)
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: 'genre' not in in_file(path))
    assert in_file(path) == {'album': ['Album'], 'title': ['T1']}


def test_remove_added_field(load, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can
    # edit/see all the supported fields in a file." Docs silent; the
    # maintainer's call: a row added in the window disappears at once.
    [path] = load({'album': 'Album', 'title': 'T1'})
    win = open_window(user, qtbot)
    add_field(user, qtbot, win, 'genre', 'Rock')
    click_row(user, win, row_of(win, 'genre'))
    user.click(win.listbuttons.removeButton)
    assert rows(win) == [('album', 'Album'), ('title', 'T1')]
    user.activate(win)
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: not win.isVisible())
    assert 'genre' not in in_file(path)


def test_reset_edited_field(load, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can
    # edit/see all the supported fields in a file." Docs silent; the
    # maintainer's call: Reset puts back what the window opened with.
    [path] = load({'album': 'Album', 'title': 'T1'})
    win = open_window(user, qtbot)
    plain = colour(win, row_of(win, 'title'))
    edit_field(user, qtbot, win, 'album', 'New')
    assert colour(win, row_of(win, 'album')) == EDITED
    user.activate(win)
    click_row(user, win, row_of(win, 'album'))
    user.click(win._reset)
    assert ('album', 'Album') in rows(win)
    assert colour(win, row_of(win, 'album')) == plain
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: not win.isVisible())
    assert in_file(path)['album'] == ['Album']


def test_reset_added_field(load, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can
    # edit/see all the supported fields in a file." Docs silent; the
    # maintainer's call: Reset deletes an added row.
    load({'album': 'Album', 'title': 'T1'})
    win = open_window(user, qtbot)
    add_field(user, qtbot, win, 'genre', 'Rock')
    click_row(user, win, row_of(win, 'genre'))
    user.click(win._reset)
    assert rows(win) == [('album', 'Album'), ('title', 'T1')]
    win.close()


def test_reset_removed_field(load, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can
    # edit/see all the supported fields in a file." Docs silent; the
    # maintainer's call: Reset puts a removed row back.
    [path] = load({'album': 'Album', 'genre': 'Rock', 'title': 'T1'})
    win = open_window(user, qtbot)
    plain = colour(win, row_of(win, 'album'))
    click_row(user, win, row_of(win, 'genre'))
    user.click(win.listbuttons.removeButton)
    assert colour(win, row_of(win, 'genre')) == REMOVED
    click_row(user, win, row_of(win, 'genre'))
    user.click(win._reset)
    assert colour(win, row_of(win, 'genre')) == plain
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: not win.isVisible())
    assert in_file(path)['genre'] == ['Rock']


def test_reset_renamed_field(load, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can
    # edit/see all the supported fields in a file." Docs silent; the
    # maintainer's call: resetting a renamed field's old row also drops
    # the row the rename added.
    [path] = load({'album': 'Album', 'genre': 'Rock', 'title': 'T1'})
    win = open_window(user, qtbot)
    plain = colour(win, row_of(win, 'album'))
    double_click_row(user, win, row_of(win, 'genre'))
    fill_field(user, qtbot, field='style', button='E&dit')
    assert rows(win) == [('album', 'Album'), ('genre', 'Rock'), ('style', 'Rock'), ('title', 'T1')]
    assert colour(win, row_of(win, 'genre')) == REMOVED
    assert colour(win, row_of(win, 'style')) == ADDED
    user.activate(win)
    click_row(user, win, row_of(win, 'genre'))
    user.click(win._reset)
    assert rows(win) == [('album', 'Album'), ('genre', 'Rock'), ('title', 'T1')]
    assert colour(win, row_of(win, 'genre')) == plain
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: not win.isVisible())
    assert in_file(path) == {'album': ['Album'], 'genre': ['Rock'], 'title': ['T1']}


def test_cancel_writes_nothing(load, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can
    # edit/see all the supported fields in a file." Docs silent; the
    # maintainer's call: Cancel closes and writes nothing.
    [path] = load({'album': 'Album', 'title': 'T1'})
    win = open_window(user, qtbot)
    edit_field(user, qtbot, win, 'album', 'New')
    user.activate(win)
    user.click(win.okcancel.cancelButton)
    qtbot.waitUntil(lambda: not win.isVisible())
    assert in_file(path)['album'] == ['Album']
    assert not user.action('&Undo').isEnabled()


def test_several_rows_grey_edit_and_duplicate(load, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can
    # edit/see all the supported fields in a file." Docs silent; the
    # maintainer's call: with several rows selected Edit and Duplicate
    # grey out and Remove acts on all of them.
    [path] = load({'album': 'Album', 'genre': 'Rock', 'title': 'T1'})
    win = open_window(user, qtbot)
    click_row(user, win, 0)
    click_row(user, win, 1, Ctrl)
    assert not win.listbuttons.editButton.isEnabled()
    assert not win.listbuttons.duplicateButton.isEnabled()
    assert win.listbuttons.removeButton.isEnabled()
    user.click(win.listbuttons.removeButton)
    assert colour(win, 0) == REMOVED
    assert colour(win, 1) == REMOVED
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: in_file(path) == {'title': ['T1']})


def test_file_without_fields(load, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can
    # edit/see all the supported fields in a file." Docs silent; the
    # maintainer's call: a file with no fields greys the list, Add still
    # works and brings it back.
    [path] = load({})
    win = open_window(user, qtbot)
    assert not win.table.isEnabled()
    assert not win.listbuttons.editButton.isEnabled()
    assert not win.listbuttons.duplicateButton.isEnabled()
    assert not win.listbuttons.removeButton.isEnabled()
    assert not win._reset.isEnabled()
    assert win.listbuttons.addButton.isEnabled()
    add_field(user, qtbot, win, 'title', 'T1')
    assert win.table.isEnabled()
    user.activate(win)
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: in_file(path) == {'title': ['T1']})


def test_add_field_differing_only_by_case(load, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can
    # edit/see all the supported fields in a file." Docs silent; the
    # maintainer's call: a field that differs only by case from a shown
    # one renames the shown rows to the new spelling and one field is
    # written.
    [path] = load({'album': 'Album', 'title': 'T1'})
    win = open_window(user, qtbot)
    add_field(user, qtbot, win, 'Album', 'Second')
    assert rows(win)[:2] == [('Album', 'Album'), ('Album', 'Second')]
    assert colour(win, 0) == EDITED
    assert colour(win, 1) == ADDED
    user.activate(win)
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: in_file(path).get('album') == ['Album', 'Second'])
    assert 'Album' not in in_file(path)
    tags = mutagen.id3.ID3(str(path))
    assert tags.getall('TALB')[0].text == ['Album', 'Second']
    assert tags.getall('TXXX') == []


def test_flac_names_differing_only_by_case(mainwin, make_audio, tmp_path, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can
    # edit/see all the supported fields in a file." Docs silent; the
    # maintainer's call: Vorbis comment names that differ only by case
    # (Mood, MOOD: synthetic) show as one field with both values and are
    # saved under one key.
    path = make_audio('01.flac', tmp_path / 'music', album='Album', title='T1')
    audio = mutagen.flac.FLAC(str(path))
    audio.tags.append(('Mood', 'Happy'))
    audio.tags.append(('MOOD', 'Sad'))
    audio.save()
    mainwin.openDir(str(tmp_path / 'music'), False)
    qtbot.waitUntil(lambda: mainwin._table.model().rowCount() == 1)
    user.activate()
    user.click_cell(user.cell(0, 'title'))
    win = open_window(user, qtbot)
    assert rows(win) == [('album', 'Album'), ('mood', 'Happy'), ('mood', 'Sad'), ('title', 'T1')]
    edit_field(user, qtbot, win, 'title', 'T2')
    user.activate(win)
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: in_file(path)['title'] == ['T2'])
    assert in_file(path)['mood'] == ['Happy', 'Sad']
    raw = [(k.lower(), v) for k, v in mutagen.flac.FLAC(str(path)).tags]
    assert raw.count(('mood', 'Happy')) == 1
    assert raw.count(('mood', 'Sad')) == 1


def test_field_with_two_values_of_one_file(load, user, qtbot):
    # tut3.txt: "Like in the file-view multiple values are shown like
    # value1\\value2. Entering any value like that will automatically
    # split it." Docs silent on the window; the maintainer's call: one row
    # per value of a field.
    [path] = load({'artist': ['A', 'B'], 'title': 'T1'})
    win = open_window(user, qtbot)
    assert [row for row in rows(win) if row[0] == 'artist'] == [('artist', 'A'), ('artist', 'B')]
    edit_field(user, qtbot, win, 'title', 'T2')
    user.activate(win)
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: in_file(path)['title'] == ['T2'])
    assert in_file(path)['artist'] == ['A', 'B']


SEVERAL = ({'album': 'Album', 'artist': ['A', 'B'], 'genre': 'Rock', 'title': 'T1'},
           {'album': 'Album', 'artist': ['A', 'B'], 'title': 'T2'})


def test_several_files_show_each_field_once(load, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can edit/see
    # all the supported fields in a file." Synthetic: two files that share
    # some values and differ in others.
    load(*SEVERAL)
    win = open_window(user, qtbot)
    assert win.windowTitle() == 'Different files.'
    assert rows(win) == [('album', 'Album'), ('artist', 'A'), ('artist', 'B'),
                         ('genre', '<keep>'), ('title', '<keep>')]
    assert entries(win, 'genre') == ['<keep>', 'Rock']
    assert entries(win, 'title') == ['<keep>', 'T1', 'T2', 'T1\\\\T2']
    win.close()


def test_ok_without_changes_writes_nothing(load, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can edit/see
    # all the supported fields in a file." Seeing a file's fields isn't
    # changing them. Synthetic.
    paths = load(*SEVERAL)
    win = open_window(user, qtbot)
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: not win.isVisible())
    assert not user.action('&Undo').isEnabled()
    assert in_file(paths[0])['title'] == ['T1']
    assert in_file(paths[1])['title'] == ['T2']
    assert in_file(paths[0])['genre'] == ['Rock']
    assert 'genre' not in in_file(paths[1])


def test_picked_value_goes_to_every_file(load, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can edit/see
    # all the supported fields in a file." Synthetic: the value picked in a
    # field's list is written to every selected file.
    paths = load(*SEVERAL)
    win = open_window(user, qtbot)
    pick(user, qtbot, win.table.cellWidget(row_of(win, 'title'), 1), 'T1')
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: [in_file(p)['title'] for p in paths] == [['T1'], ['T1']])
    assert in_file(paths[0])['genre'] == ['Rock']
    assert 'genre' not in in_file(paths[1])
    user.activate()


def test_all_values_entry_gives_every_file_both(load, user, qtbot):
    # tut3.txt: "Entering any value like that will automatically split it".
    # Synthetic: the list's last entry holds every value joined with two
    # backslashes.
    paths = load(*SEVERAL)
    win = open_window(user, qtbot)
    pick(user, qtbot, win.table.cellWidget(row_of(win, 'title'), 1), 'T1\\\\T2')
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: all(in_file(p)['title'] == ['T1', 'T2'] for p in paths))
    user.activate()


def test_edit_keep_row(load, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can edit/see
    # all the supported fields in a file." Synthetic: a value typed over a
    # field that differs goes to every file.
    paths = load(*SEVERAL)
    win = open_window(user, qtbot)
    double_click_row(user, win, row_of(win, 'title'))
    fill_field(user, qtbot, value='New', button='E&dit')
    user.activate(win)
    assert entries(win, 'title')[1] == 'New'
    assert ('title', 'New') in rows(win)
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: in_file(paths[0])['title'] == ['New'])
    qtbot.waitUntil(lambda: in_file(paths[1])['title'] == ['New'])
    user.activate()


def test_edit_after_picking_a_value(load, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can edit/see
    # all the supported fields in a file." Synthetic: editing a picked value
    # replaces it.
    paths = load(*SEVERAL)
    win = open_window(user, qtbot)
    pick(user, qtbot, win.table.cellWidget(row_of(win, 'title'), 1), 'T2')
    double_click_row(user, win, row_of(win, 'title'))
    fill_field(user, qtbot, value='New', button='E&dit')
    user.activate(win)
    assert entries(win, 'title') == ['<keep>', 'T1', 'New', 'T1\\\\T2']
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: in_file(paths[0])['title'] == ['New'])
    qtbot.waitUntil(lambda: in_file(paths[1])['title'] == ['New'])
    user.activate()


def test_remove_keep_row(load, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can edit/see
    # all the supported fields in a file." Synthetic: Remove on a field that
    # differs removes it from every file.
    paths = load(*SEVERAL)
    win = open_window(user, qtbot)
    click_row(user, win, row_of(win, 'genre'))
    user.click(win.listbuttons.removeButton)
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: all('genre' not in in_file(p) for p in paths))
    assert in_file(paths[0])['title'] == ['T1']
    assert in_file(paths[1])['title'] == ['T2']
    user.activate()


def test_add_case_of_a_keep_row(load, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can edit/see
    # all the supported fields in a file." On one file the same Add keeps the
    # file's value and adds the new one; several files do the same for each
    # file's own values. Synthetic.
    paths = load(*SEVERAL)
    win = open_window(user, qtbot)
    user.click(win.listbuttons.addButton)
    fill_field(user, qtbot, field='Title', value='X')
    user.activate(win)
    assert ('Title', '<keep>') in rows(win)
    assert colour(win, row_of(win, 'Title', '<keep>')) == EDITED
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: [in_file(p)['title'] for p in paths] == [['T1', 'X'], ['T2', 'X']])
    user.activate()


def test_rename_then_remove_keep_row(load, user, qtbot):
    # Docs silent; the maintainer's call: renaming a field marks its old row
    # removed, and removing the new row leaves it so: OK removes the field
    # from every file. Synthetic files.
    paths = load({'genre': 'Rock', 'title': 'T1'}, {'genre': 'Jazz', 'title': 'T2'})
    win = open_window(user, qtbot)
    double_click_row(user, win, row_of(win, 'genre'))
    fill_field(user, qtbot, field='style', button='E&dit')
    user.activate(win)
    click_row(user, win, row_of(win, 'style'))
    user.click(win.listbuttons.removeButton)
    assert 'style' not in [field for field, _ in rows(win)]
    assert colour(win, row_of(win, 'genre')) == REMOVED
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: not win.isVisible())
    user.activate()
    qtbot.waitUntil(lambda: all('genre' not in in_file(p) for p in paths))
    assert all('style' not in in_file(p) for p in paths)
    assert [in_file(p)['title'] for p in paths] == [['T1'], ['T2']]


def test_same_cover_in_every_file(load, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can edit/see
    # all the supported fields in a file." Synthetic: files with the same
    # cover show it, and keep it when a field is edited.
    paths = load({'album': 'Album', 'covers': [FRONT], 'title': 'T1'},
                 {'album': 'Album', 'covers': [FRONT], 'title': 'T2'})
    win = open_window(user, qtbot)
    assert win.piclabel.images[0]['description'] == 'Front'
    double_click_row(user, win, row_of(win, 'album'))
    fill_field(user, qtbot, value='New', button='E&dit')
    user.activate(win)
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: all(in_file(p)['album'] == ['New'] for p in paths))
    assert [stored(p) for p in paths] == [[FRONT], [FRONT]]
    user.activate()


def test_remove_cover_when_covers_differ(load, user, qtbot):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can edit/see
    # all the supported fields in a file." Synthetic: Remove on the picture
    # removes every file's cover, whatever they were.
    paths = load({'album': 'Album', 'covers': [FRONT], 'title': 'T1'},
                 {'album': 'Album', 'covers': [BACK], 'title': 'T2'})
    win = open_window(user, qtbot)
    assert win.piclabel.context == 'Cover Varies'
    user.click(win.piclabel.removepic)
    assert win.piclabel.context == 'No Images'
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: all(stored(p) == [] for p in paths))
    assert [in_file(p)['title'] for p in paths] == [['T1'], ['T2']]
    user.activate()


def type_cell(user, qtbot, row, field, text):
    """Types text into the File-View's cell for the field."""
    user.double_click_cell(user.cell(row, field))
    QApplication.focusWidget().selectAll()
    user.type(text)
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: user.table.model().data(user.cell(row, field)) == text)
    user.press(Key.Key_Escape)  # the next row's cell, which Enter opened


def test_ok_in_preview_mode_stages_previews(load, user, qtbot):
    # menus.txt, Preview Mode: "When enabled any changes you make will not
    # get written. Instead any values you change that differ from the
    # original will be shown as emboldened text in the File-View and
    # Extended Tags dialog." Write Previews: "they'll get written to the
    # files".
    paths = load({'album': 'Album', 'title': 'T1'}, {'album': 'Album', 'title': 'T2'})
    user.press(Key.Key_P, Ctrl | Shift)
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(1, 'title'), Shift)
    win = open_window(user, qtbot)
    double_click_row(user, win, row_of(win, 'title'))
    fill_field(user, qtbot, value='New', button='E&dit')
    user.activate(win)
    user.click(win.okcancel.okButton)

    qtbot.waitUntil(lambda: shown(user, 1, 'title') == ('New', 'bold'))
    assert shown(user, 0, 'title') == ('New', 'bold')
    assert [in_file(p)['title'] for p in paths] == [['T1'], ['T2']]

    user.activate()
    user.click_menu('&Write Previews')
    qtbot.waitUntil(lambda: [in_file(p)['title'] for p in paths] == [['New'], ['New']])


def test_previews_of_several_files_in_the_window(load, user, qtbot):
    # menus.txt: "When enabled any changes you make will not get written";
    # the window shows what the previews hold. Synthetic: the same values
    # typed in both files.
    paths = load({'album': 'Album', 'title': 'T1'}, {'album': 'Album', 'title': 'T2'})
    user.press(Key.Key_P, Ctrl | Shift)
    for row in (0, 1):
        type_cell(user, qtbot, row, 'album', 'X')
        type_cell(user, qtbot, row, 'album', 'Album')
        type_cell(user, qtbot, row, 'title', 'Same')
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(1, 'title'), Shift)
    win = open_window(user, qtbot)

    assert win.get_field(row_of(win, 'title')) == ('title', 'Same')
    assert style(win, row_of(win, 'title')) == 'bold'
    assert style(win, row_of(win, 'album')) == 'italic'
    win.close()
    assert [(in_file(p)['album'], in_file(p)['title']) for p in paths] == [
        (['Album'], ['T1']), (['Album'], ['T2'])]


def test_staged_cover_shown(load, mainwin, user, qtbot, dialogs, tmp_path):
    # menus.txt, Preview Mode: "When enabled any changes you make will not
    # get written." The window shows the staged cover. Synthetic cover.
    [path] = load({'title': 'T1'})
    source = tmp_path / 'cover.png'
    source.write_bytes(FRONT['data'])
    user.click_menu('Artwork')
    [artwork] = mainwin.findChildren(ArtworkWidget)
    qtbot.waitUntil(artwork.isVisible)
    pic = artwork.picwidget
    user.click_cell(user.cell(0, 'title'))
    user.press(Key.Key_P, Ctrl | Shift)
    dialogs.answer('QFileDialog.getOpenFileName', (str(source), ''))
    user.right_click(pic.label, pic.label.rect().center(), '&Add cover')
    user.activate()
    user.click_menu('&Save')
    assert mainwin._table.model().taginfo[0].preview['__image']

    win = open_window(user, qtbot)

    assert win.piclabel.images[0]['data'] == FRONT['data']
    assert stored(path) == []
    win.close()


def test_untouched_fields_stay_unstaged(load, mainwin, user, qtbot):
    # menus.txt, Preview Mode: "Values that you've changed, but are the same
    # as the underlying value will be shown in italics." Only the added
    # field is a change.
    load({'album': 'Album', 'title': 'T1'})
    user.press(Key.Key_P, Ctrl | Shift)
    win = open_window(user, qtbot)
    add_field(user, qtbot, win, 'genre', 'Rock')
    user.activate(win)
    user.click(win.okcancel.okButton)

    qtbot.waitUntil(lambda: 'genre' in mainwin._table.model().taginfo[0].preview)
    assert mainwin._table.model().taginfo[0].preview == {'genre': ['Rock']}

    user.activate()
    win = open_window(user, qtbot)
    assert style(win, row_of(win, 'album')) == 'plain'
    assert style(win, row_of(win, 'genre')) == 'bold'
    win.close()


def test_field_added_in_preview_mode_is_bold(load, user, qtbot):
    # menus.txt, Preview Mode: "any values you change that differ from the
    # original will be shown as emboldened text in the File-View and
    # Extended Tags dialog."
    load({'title': 'T1'})
    user.press(Key.Key_P, Ctrl | Shift)
    win = open_window(user, qtbot)
    add_field(user, qtbot, win, 'genre', 'Rock')

    assert style(win, row_of(win, 'genre')) == 'bold'
    win.close()


@pytest.fixture
def dock(clean_profile):
    """The Extended Tags plugin ticked on the Plugins page in an earlier
    session. Name it before mainwin in a test's arguments, so the profile
    holds it when the window is built."""
    PuddleConfig().set('plugins', 'to_load', ['extended_tags'])


def show_dock(user, qtbot, mainwin):
    """Windows->Extended Tags; the dock's widget."""
    from puddlestuff.plugins.extended_tags import ExTagsPlugin
    user.click_menu('Extended Tags')
    [widget] = mainwin.findChildren(ExTagsPlugin)
    qtbot.waitUntil(widget.isVisible)
    return widget


def reselect(user, count):
    """Selects the first count files again: the dock fills on a change of
    the selection."""
    user.click_cell(user.cell(0, 'title'))
    if count > 1:
        user.click_cell(user.cell(count - 1, 'title'), Shift)


def test_dock_shows_the_selection(dock, mainwin, load, user, qtbot):
    # The plugin's own words: "Allows using the Extended Tags dialog as a
    # dockable window."
    load({'album': 'Album', 'title': 'T1'}, {'album': 'Album', 'title': 'T2'})
    widget = show_dock(user, qtbot, mainwin)
    reselect(user, 2)
    assert rows(widget) == [('album', 'Album'), ('title', '<keep>')]
    user.click_cell(user.cell(0, 'title'))
    assert rows(widget) == [('album', 'Album'), ('title', 'T1')]
    user.click(user.table.viewport(), user.table.viewport().rect().bottomRight())
    assert rows(widget) == []
    assert not widget.listbuttons.addButton.isEnabled()


@pytest.mark.parametrize('how', ['menu', 'shortcut'])
def test_save_extended_writes_every_selected_file(dock, mainwin, load, user, qtbot, how):
    # The plugin's own words: "Uses Plugins->Save Extended (Ctrl+Shift+S) to
    # save."
    paths = load({'title': 'T1'}, {'title': 'T2'})
    widget = show_dock(user, qtbot, mainwin)
    reselect(user, 2)
    user.click(widget.listbuttons.addButton)
    fill_field(user, qtbot, 'genre', 'Rock')
    user.activate()
    if how == 'menu':
        user.click_menu('Save Extended')
    else:
        user.press(Key.Key_S, Ctrl | Shift)
    qtbot.waitUntil(lambda: all(in_file(p).get('genre') == ['Rock'] for p in paths))
    assert [in_file(p)['title'] for p in paths] == [['T1'], ['T2']]


def test_dock_edit_keep_row(dock, mainwin, load, user, qtbot):
    # The plugin's own words: "Uses Plugins->Save Extended (Ctrl+Shift+S) to
    # save." Docs silent about editing a <keep> row; the maintainer's call:
    # the typed value is written to every file.
    paths = load({'title': 'T1'}, {'title': 'T2'})
    widget = show_dock(user, qtbot, mainwin)
    reselect(user, 2)
    double_click_row(user, widget, row_of(widget, 'title'))
    fill_field(user, qtbot, value='New', button='E&dit')
    user.activate()
    user.click_menu('Save Extended')
    qtbot.waitUntil(lambda: all(in_file(p).get('title') == ['New'] for p in paths))


def test_dock_in_preview_mode(dock, mainwin, load, user, qtbot):
    # menus.txt: "When enabled any changes you make will not get written.
    # Instead any values you change that differ from the original will be
    # shown as emboldened text in the File-View and Extended Tags dialog."
    paths = load({'title': 'T1'}, {'title': 'T2'})
    user.press(Key.Key_P, Ctrl | Shift)
    widget = show_dock(user, qtbot, mainwin)
    reselect(user, 2)
    user.click(widget.listbuttons.addButton)
    fill_field(user, qtbot, 'genre', 'Rock')
    assert style(widget, row_of(widget, 'genre')) == 'bold'
    user.activate()
    user.click_menu('Save Extended')
    taginfo = mainwin._table.model().taginfo
    qtbot.waitUntil(lambda: all(audio.preview.get('genre') == ['Rock'] for audio in taginfo))
    assert all('genre' not in in_file(p) for p in paths)


def test_dock_drops_edits_on_a_new_selection(dock, mainwin, load, user, qtbot):
    # Docs silent; the maintainer's call: a change of the selection drops
    # the dock's unsaved edits.
    paths = load({'title': 'T1'}, {'title': 'T2'})
    widget = show_dock(user, qtbot, mainwin)
    reselect(user, 2)
    user.click(widget.listbuttons.addButton)
    fill_field(user, qtbot, 'genre', 'Rock')
    user.activate()
    user.click_cell(user.cell(0, 'title'))
    user.press(Key.Key_S, Ctrl | Shift)
    assert not user.action('&Undo').isEnabled()
    assert all('genre' not in in_file(p) for p in paths)


@pytest.mark.xfail(strict=True, reason="Delete is ambiguous between the dock's Remove shortcut "
                                       "and Move to Trash, so neither fires")
def test_delete_moves_files_to_the_trash_with_the_dock_shown(dock, mainwin, load, user, qtbot, dialogs):
    # menus.txt: "Move to Trash (Del)": "Moves the selected files to the
    # trash ... puddletag asks first". With the dock shown, Del on the
    # File-View still does; the dock's Remove (Delete) acts while its list
    # has focus.
    paths = load({'genre': 'Rock', 'title': 'T1'}, {'genre': 'Rock', 'title': 'T2'})
    widget = show_dock(user, qtbot, mainwin)
    reselect(user, 2)
    user.click_cell(user.cell(0, 'title'))
    dialogs.answer('QMessageBox.question', No)
    user.press(Key.Key_Delete)
    assert len([c for c in dialogs.calls if c[0] == 'QMessageBox.question']) == 1
    assert all(p.exists() for p in paths)
    reselect(user, 2)
    row = row_of(widget, 'genre')
    click_row(user, widget, row)
    user.press(Key.Key_Delete)
    assert colour(widget, row) == REMOVED


def test_save_extended_keeps_the_field_list(dock, mainwin, load, user, qtbot):
    # Docs silent; the maintainer's call: the Edit Field list keeps the saved
    # field names after the dock saves.
    paths = load({'title': 'T1'}, {'title': 'T2'})
    widget = show_dock(user, qtbot, mainwin)
    reselect(user, 2)
    user.click(widget.listbuttons.addButton)
    fill_field(user, qtbot, 'genre', 'Rock')
    user.activate()
    user.click_menu('Save Extended')
    qtbot.waitUntil(lambda: all(in_file(p).get('genre') == ['Rock'] for p in paths))
    user.activate()
    user.press(Key.Key_E, Ctrl)
    # The dock is an ExTags too.
    qtbot.waitUntil(lambda: any(isinstance(w, ExTags) and w.isVisible() and w is not widget
                                for w in QApplication.topLevelWidgets()))
    [window] = [w for w in QApplication.topLevelWidgets()
                if isinstance(w, ExTags) and w.isVisible() and w is not widget]
    user.activate(window)
    user.click(window.listbuttons.addButton)
    dialog = opened(qtbot, EditField)
    names = [dialog.tagcombo.itemText(i) for i in range(dialog.tagcombo.count())]
    [cancel] = [b for b in dialog.findChildren(QPushButton) if b.text() == 'Cancel']
    user.click(cancel)
    user.click(window.okcancel.cancelButton)
    assert 'composer' in names


@pytest.mark.xfail(strict=True, reason="Save Extended writes the Artwork window's last covers "
                                       'to the saved files')
def test_save_extended_leaves_covers_alone(dock, mainwin, load, user, qtbot):
    # The plugin's own words: "Uses Plugins->Save Extended (Ctrl+Shift+S) to
    # save." Docs silent about covers; the maintainer's call: covers are the
    # Artwork window's job, saving fields leaves them alone.
    paths = load({'covers': [FRONT], 'title': 'T1'}, {'title': 'T2'})
    user.click_cell(user.cell(0, 'title'))
    user.click_menu('Artwork')
    [artwork] = mainwin.findChildren(ArtworkWidget)
    qtbot.waitUntil(artwork.isVisible)
    user.click_menu('Artwork')
    qtbot.waitUntil(lambda: not artwork.isVisible())
    widget = show_dock(user, qtbot, mainwin)
    user.click_cell(user.cell(1, 'title'))
    user.click(widget.listbuttons.addButton)
    fill_field(user, qtbot, 'genre', 'Rock')
    user.activate()
    user.click_menu('Save Extended')
    qtbot.waitUntil(lambda: in_file(paths[1]).get('genre') == ['Rock'])
    assert stored(paths[1]) == []
    assert stored(paths[0]) == [FRONT]


@pytest.mark.xfail(strict=True, reason="Delete is ambiguous with the picture's Remove shortcut when a "
                   "cover is shown, so neither removes anything")
def test_delete_removes_the_field_when_a_cover_is_shown(load, user, qtbot):
    # Docs silent; the maintainer's call: Delete removes the selected field
    # even when the file shows a cover, and the cover stays.
    [path] = load({'covers': [FRONT], 'genre': 'Rock', 'title': 'Title'})
    win = open_window(user, qtbot)
    assert win.piclabel.images[0]['description'] == 'Front'

    click_row(user, win, row_of(win, 'genre'))
    user.press(Key.Key_Delete)
    # A shortcut clicks its button a moment later.
    qtbot.waitUntil(lambda: colour(win, row_of(win, 'genre')) == REMOVED)
    user.click(win.okcancel.okButton)

    qtbot.waitUntil(lambda: 'genre' not in in_file(path))
    assert stored(path) == [FRONT]


@pytest.mark.xfail(strict=True, reason="Preferences shows the added colour green and the edited one "
                   "yellow, the reverse of the colours the window paints on a fresh profile")
def test_window_colours_match_preferences(mainwin, user):
    # preferences.txt: "Defines the background colours to used in various
    # puddletag dialogs." The Extended Tags window paints added rows yellow,
    # edited ones green and removed ones red on a fresh profile; the Colours
    # page shows the same.
    window = user.open_preferences('Colours')
    page = window.stack.currentWidget()

    assert [page.listbox.item(r, 0).background().color().getRgb()[:3] for r in (2, 3, 4)] == [
        ADDED, EDITED, REMOVED]
    user.close_preferences(window, 'Cancel')


def move_button(window, text):
    [button] = [b for b in window.findChildren(QPushButton) if b.text() == text]
    return button


def test_previous_and_next_step_through_the_files(load, user, qtbot):
    # Synthetic files. The first row selected alone is the case #597
    # reported: the window showed every file's fields instead of that
    # one's. Docs silent on the buttons; the maintainer's call: one
    # selected file opens with Previous and Next, which step through the
    # files and select the row shown.
    paths = load({'title': 'T1'}, {'title': 'T2'}, {'title': 'T3'})
    user.click_cell(user.cell(0, 'title'))
    win = open_window(user, qtbot)

    assert rows(win) == [('title', 'T1')]
    assert win.windowTitle() == str(paths[0])
    assert move_button(win, '&>>').isVisible()

    user.click(move_button(win, '&>>'))
    assert rows(win) == [('title', 'T2')]
    assert win.windowTitle() == str(paths[1])
    assert user.table.selectedRows == [1]

    user.click(move_button(win, '&<<'))
    assert rows(win) == [('title', 'T1')]
    assert win.windowTitle() == str(paths[0])
    win.close()


def test_next_writes_the_edit_first(load, user, qtbot):
    # Synthetic files. Docs silent; the maintainer's call: Next writes the
    # edit made to the file shown before it shows the next one.
    paths = load({'album': 'Album', 'title': 'T1'}, {'album': 'Album', 'title': 'T2'})
    user.click_cell(user.cell(0, 'title'))
    win = open_window(user, qtbot)
    edit_field(user, qtbot, win, 'album', 'New')
    user.activate(win)
    user.click(move_button(win, '&>>'))

    qtbot.waitUntil(lambda: in_file(paths[0])['album'] == ['New'])
    assert rows(win) == [('album', 'Album'), ('title', 'T2')]
    assert in_file(paths[1])['album'] == ['Album']
    win.close()


def test_second_row_of_a_field_is_split(load, user, qtbot):
    # tut3.txt (Tag Panel): "Entering any value like that will
    # automatically split it." Synthetic: Duplicate artist with B\\C.
    [path] = load({'artist': 'A', 'title': 'T1'})
    win = open_window(user, qtbot)
    click_row(user, win, row_of(win, 'artist'))
    user.click(win.listbuttons.duplicateButton)
    fill_field(user, qtbot, value='B\\\\C')
    user.activate(win)
    user.click(win.okcancel.okButton)

    qtbot.waitUntil(lambda: len(in_file(path).get('artist', [])) > 1)
    assert in_file(path)['artist'] == ['A', 'B', 'C']
