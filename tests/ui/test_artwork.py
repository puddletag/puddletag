"""Covers in the Artwork window and in Extended Tags, edited as a user
edits them: right-click the picture or use the buttons beside it, then
File->Save (tut3.txt: "covers you modify aren't saved automatically. You
still need to use Save from the File menu"), and the fields Extended
Tags shows (menus.txt: "With it you can edit/see all the supported
fields in a file"). Each change is checked in the window and in the
file. Synthetic files and images.
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

pytestmark = pytest.mark.ui

Key = Qt.Key
Alt = Qt.KeyboardModifier.AltModifier
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier


def image(form, width):
    """A real image, so that its MIME type can be told from its data; the
    width tells images apart."""
    picture = QImage(width, 1, QImage.Format.Format_RGB32)
    picture.fill(0)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert picture.save(buffer, form)
    return bytes(buffer.data())


FRONT = {'data': image('PNG', 10), 'description': 'Front', 'imagetype': 3, 'mime': 'image/png'}
BACK = {'data': image('PNG', 20), 'description': 'Back', 'imagetype': 4, 'mime': 'image/png'}


def put(path, *covers):
    """Covers as another program writes them, with mutagen."""
    if path.suffix == '.flac':
        audio = mutagen.flac.FLAC(str(path))
        for cover in covers:
            picture = mutagen.flac.Picture()
            picture.data, picture.desc, picture.mime, picture.type = (
                cover['data'], cover['description'], cover['mime'], cover['imagetype'])
            audio.add_picture(picture)
        audio.save()
    else:
        tags = mutagen.id3.ID3(str(path))
        for cover in covers:
            tags.add(mutagen.id3.APIC(encoding=3, mime=cover['mime'], type=cover['imagetype'],
                                      desc=cover['description'], data=cover['data']))
        tags.save()


def stored(path):
    """The covers the file keeps, as mutagen reads them."""
    if path.suffix == '.flac':
        pictures = mutagen.flac.FLAC(str(path)).pictures
    else:
        pictures = mutagen.id3.ID3(str(path)).getall('APIC')
    return [{'data': p.data, 'description': p.desc, 'imagetype': p.type, 'mime': p.mime}
            for p in pictures]


def in_file(path):
    return audioinfo.usertags(audioinfo.Tag(str(path)))


@pytest.fixture
def load(mainwin, make_audio, tmp_path, qtbot, user):
    """load('mp3', [FRONT], []) makes one file per list of covers, each
    with album 'Album' and its own title, and loads them."""
    def load(ext, *covers_per_file, **tags):
        music = tmp_path / 'music'
        paths = []
        for number, covers in enumerate(covers_per_file, 1):
            path = make_audio(f'0{number}.{ext}', music,
                              **{'album': 'Album', 'title': f'Title {number}', **tags})
            put(path, *covers)
            paths.append(path)
        mainwin.openDir(str(music), False)
        qtbot.waitUntil(lambda: mainwin._table.model().rowCount() == len(paths))
        user.activate()
        return paths
    return load


def select(user, count):
    user.click_cell(user.cell(0, 'title'))
    if count > 1:
        user.click_cell(user.cell(count - 1, 'title'), Shift)


def artwork(user, mainwin, qtbot):
    """Windows->Artwork; the picture and its controls."""
    user.click_menu('Artwork')
    [window] = mainwin.findChildren(ArtworkWidget)
    qtbot.waitUntil(window.isVisible)
    return window.picwidget


def right_click(user, pic, name):
    user.right_click(pic.label, pic.label.rect().center(), name)


def describe(user, pic, text):
    user.click(pic._image_desc)
    user.press(Key.Key_A, Ctrl)
    user.type(text)


def pick_type(user, qtbot, pic, text):
    """The cover type button's menu, e.g. '[CB] Cover (back)'."""
    button = pic._image_type
    user.click(button)
    menu = button.menu()
    qtbot.waitUntil(menu.isVisible)
    [action] = [a for a in menu.actions() if a.text() == text]
    user.click(menu, menu.actionGeometry(action).center())


def shown_cover(pic):
    return pic.context, pic.images[pic.currentImage]['description']


def extended_tags(qtbot):
    qtbot.waitUntil(lambda: any(isinstance(w, ExTags) and w.isVisible()
                                for w in QApplication.topLevelWidgets()))
    [window] = [w for w in QApplication.topLevelWidgets() if isinstance(w, ExTags) and w.isVisible()]
    return window


def rows(window):
    return [(window.table.item(row, 0).text(), window.get_field(row)[1])
            for row in range(window.table.rowCount())]


def edit_value(user, qtbot, window, field, text, column=1):
    """Double-clicks the field's row (its value, or with column=0 its
    name) and types text over what the Edit Field dialog holds."""
    [row] = [r for r in range(window.table.rowCount()) if window.table.item(r, 0).text() == field]
    item = window.table.item(row, column)
    user.double_click(window.table.viewport(), window.table.visualItemRect(item).center())
    qtbot.waitUntil(lambda: any(isinstance(w, EditField) and w.isVisible()
                                for w in QApplication.topLevelWidgets()))
    [dialog] = [w for w in QApplication.topLevelWidgets() if isinstance(w, EditField) and w.isVisible()]
    user.activate(dialog)
    user.press(Key.Key_A, Ctrl)
    user.type(text)
    [button] = [b for b in dialog.findChildren(QPushButton) if b.text() == 'E&dit']
    user.click(button)


THIRD = {'data': image('PNG', 30), 'description': 'Artist', 'imagetype': 8, 'mime': 'image/png'}


def add_cover(user, dialogs, pic, path):
    dialogs.answer('QFileDialog.getOpenFileName', (str(path), ''))
    right_click(user, pic, '&Add cover')


@pytest.mark.parametrize('ext', ['flac', 'mp3'])
def test_add_cover(mainwin, user, load, qtbot, dialogs, tmp_path, ext):
    # tut3.txt: "right click on the shown picture container to get a menu.
    # With it you can add/remove/edit artwork", "For ID3, be sure to
    # always add descriptions for your covers in the text box just below"
    # and "Choose a cover type by clicking the button next to the
    # description box."
    [path] = load(ext, [])
    png = tmp_path / 'cover.png'
    png.write_bytes(image('PNG', 10))
    pic = artwork(user, mainwin, qtbot)
    select(user, 1)
    assert pic.context == '2/2'
    assert pic.currentImage == 1

    add_cover(user, dialogs, pic, png)
    assert pic.context == '3/3'
    assert pic._image_type.text() == 'CF'
    assert pic._image_desc.text() == ''

    describe(user, pic, 'Back')
    pick_type(user, qtbot, pic, '[CB] Cover (back)')
    user.activate()
    user.click_menu('&Save')
    qtbot.waitUntil(lambda: bool(stored(path)))

    cover = {'data': image('PNG', 10), 'description': 'Back', 'imagetype': 4, 'mime': 'image/png'}
    assert stored(path) == [cover]
    [shown] = mainwin._table.model().taginfo[0].images
    assert (shown['description'], shown['imagetype']) == ('Back', 4)


def test_cover_not_saved_until_save(mainwin, user, load, qtbot, dialogs, tmp_path):
    # tut3.txt: "covers you modify aren't saved automatically. You still
    # need to use Save from the File menu."
    [path] = load('mp3', [])
    png = tmp_path / 'cover.png'
    png.write_bytes(image('PNG', 10))
    pic = artwork(user, mainwin, qtbot)
    select(user, 1)
    add_cover(user, dialogs, pic, png)
    assert pic.context == '3/3'
    qtbot.wait(200)
    assert stored(path) == []

    user.click_menu('&Save')
    qtbot.waitUntil(lambda: bool(stored(path)))
    [cover] = stored(path)
    assert (cover['description'], cover['imagetype']) == ('', 3)


def test_remove_cover(mainwin, user, load, qtbot):
    # tut3.txt: "options for adding/removing artwork".
    [path] = load('mp3', [FRONT, BACK])
    pic = artwork(user, mainwin, qtbot)
    select(user, 1)
    assert shown_cover(pic) == ('3/4', 'Front')

    right_click(user, pic, '&Remove cover')
    assert shown_cover(pic) == ('3/3', 'Back')

    user.click_menu('&Save')
    qtbot.waitUntil(lambda: len(stored(path)) == 1)
    assert stored(path) == [BACK]


def test_remove_last_cover(mainwin, user, load, qtbot):
    # tut3.txt: "options for adding/removing artwork".
    [path] = load('mp3', [FRONT])
    pic = artwork(user, mainwin, qtbot)
    select(user, 1)
    assert pic.context == '3/3'

    right_click(user, pic, '&Remove cover')
    assert pic.currentImage == 1

    user.click_menu('&Save')
    qtbot.waitUntil(lambda: stored(path) == [])


def test_keep_leaves_each_cover(mainwin, user, load, qtbot):
    from puddlestuff.mainwin.tagpanel import FrameCombo
    # tut3.txt: "<keep> will leave artwork unmodified for each file."
    paths = load('mp3', [FRONT], [BACK])
    pic = artwork(user, mainwin, qtbot)
    select(user, 2)
    assert pic.context == 'Cover Varies'
    assert pic.currentImage == 0

    [panel] = mainwin.findChildren(FrameCombo)
    user.click(panel.combos['album'].lineEdit())
    user.press(Key.Key_A, Ctrl)
    user.type('New')
    user.click_menu('&Save')
    qtbot.waitUntil(lambda: all(in_file(p).get('album') == ['New'] for p in paths))

    assert stored(paths[0]) == [FRONT]
    assert stored(paths[1]) == [BACK]


def test_blank_removes_covers(mainwin, user, load, qtbot):
    # tut3.txt: "If the picture should <blank> artwork will be removed
    # upon saving."
    paths = load('mp3', [FRONT], [BACK])
    pic = artwork(user, mainwin, qtbot)
    select(user, 2)
    user.click(pic.next)
    assert pic.currentImage == 1
    assert pic.images[1]['description'] == '<blank>'

    user.click_menu('&Save')
    qtbot.waitUntil(lambda: all(stored(p) == [] for p in paths))


def test_blank_removes_several_covers_of_one_file(mainwin, user, load, qtbot):
    # tut3.txt: "If the picture should <blank> artwork will be removed
    # upon saving." (#416: a file with several covers.)
    [path] = load('mp3', [FRONT, BACK, THIRD])
    pic = artwork(user, mainwin, qtbot)
    select(user, 1)
    assert pic.context == '3/5'

    user.click(pic.prev)
    assert pic.currentImage == 1

    user.click_menu('&Save')
    qtbot.waitUntil(lambda: stored(path) == [])


def test_two_covers_without_descriptions(mainwin, user, load, qtbot, dialogs, tmp_path):
    # tut3.txt: "For ID3, be sure to always add descriptions for your
    # covers ... since the ID3 standard doesn't allow for covers to have
    # the same description".
    [path] = load('mp3', [])
    first, second = tmp_path / 'first.png', tmp_path / 'second.png'
    first.write_bytes(image('PNG', 10))
    second.write_bytes(image('PNG', 20))
    pic = artwork(user, mainwin, qtbot)
    select(user, 1)
    add_cover(user, dialogs, pic, first)
    add_cover(user, dialogs, pic, second)
    assert pic.context == '4/4'

    user.click_menu('&Save')
    qtbot.waitUntil(lambda: len(stored(path)) == 2)
    assert {c['description']: c['data'] for c in stored(path)} == {
        '': image('PNG', 10), ' ': image('PNG', 20)}


@pytest.mark.xfail(strict=True, reason='the Artwork window edits the covers of the table in place, '
                                       'so Save finds nothing changed')
def test_change_description_and_type_of_existing_cover(mainwin, load, qtbot, user):
    # tut3.txt: "right click on the shown picture container to get a menu.
    # With it you can add/remove/edit artwork" and "covers you modify aren't
    # saved automatically. You still need to use Save from the File menu."
    old = dict(FRONT, description='Old')
    paths = load('mp3', [old], [old])
    pic = artwork(user, mainwin, qtbot)
    select(user, 2)
    describe(user, pic, 'New')
    pick_type(user, qtbot, pic, '[CB] Cover (back)')
    user.activate()
    user.click_menu('&Save')
    expected = [dict(FRONT, description='New', imagetype=4)]
    qtbot.waitUntil(lambda: all(stored(path) == expected for path in paths))


@pytest.mark.xfail(strict=True, reason="Change cover resets the description and type, and isn't saved")
def test_change_cover(mainwin, load, tmp_path, dialogs, qtbot, user):
    # tut3.txt: "right click on the shown picture container to get a menu.
    # With it you can add/remove/edit artwork".
    [path] = load('mp3', [FRONT])
    pic = artwork(user, mainwin, qtbot)
    select(user, 1)
    new = tmp_path / 'new.png'
    new.write_bytes(image('PNG', 20))
    dialogs.answer('QFileDialog.getOpenFileName', (str(new), ''))
    right_click(user, pic, '&Change cover')
    user.activate()
    user.click_menu('&Save')
    expected = [dict(FRONT, data=image('PNG', 20))]
    qtbot.waitUntil(lambda: stored(path) == expected)


def test_cover_in_preview_mode(load, mainwin, user, qtbot, dialogs, tmp_path):
    # menus.txt: "Be aware if previews have been enabled ... then nothing
    # will get written. Only the preview will get updated." and Write
    # Previews: "they'll get written to the files".
    [path] = load('mp3', [])
    source = tmp_path / 'cover.png'
    source.write_bytes(image('PNG', 10))
    pic = artwork(user, mainwin, qtbot)
    select(user, 1)
    user.press(Key.Key_P, Ctrl | Shift)
    dialogs.answer('QFileDialog.getOpenFileName', (str(source), ''))
    right_click(user, pic, '&Add cover')
    user.activate()
    user.click_menu('&Save')

    assert stored(path) == []
    assert mainwin._table.model().taginfo[0].preview['__image'][0]['data'] == image('PNG', 10)

    user.click_menu('&Write Previews')
    qtbot.waitUntil(lambda: bool(stored(path)))
    [cover] = stored(path)
    assert (cover['imagetype'], cover['mime']) == (3, 'image/png')


@pytest.mark.xfail(strict=True, reason='Paste re-encodes the copied cover as JPEG, so its bytes '
                                       'and MIME type differ from the original PNG')
def test_copy_and_paste_cover(load, mainwin, user, qtbot):
    # Synthetic: the docs (tut3.txt) list adding, removing and editing a
    # cover only; copy and paste come from issues #428 and #1042.
    paths = load('mp3', [FRONT], [])
    pic = artwork(user, mainwin, qtbot)
    user.click_cell(user.cell(0, 'title'))
    right_click(user, pic, 'C&opy cover')
    user.click_cell(user.cell(1, 'title'))
    assert user.action('&Paste cover').isEnabled()
    right_click(user, pic, '&Paste cover')
    user.activate()
    user.click_menu('&Save')
    qtbot.waitUntil(lambda: len(stored(paths[1])) == 1)

    assert len(stored(paths[1])) == 1
    pasted = stored(paths[1])[0]
    assert (pasted['data'], pasted['mime']) == (FRONT['data'], FRONT['mime'])


@pytest.mark.xfail(strict=True, reason="Save cover to file writes Qt's re-encoding of the shown "
                                       "picture, not the cover's own bytes")
def test_save_cover_to_file(load, mainwin, user, qtbot, dialogs, tmp_path):
    # Synthetic: the docs don't describe Save cover to file; issue #457
    # ("Mp3tag preserves image quality") reports it.
    # The padding after the image keeps Qt's re-encoding from being identical.
    data = image('JPEG', 30) + bytes(16)
    load('mp3', [dict(FRONT, data=data, mime='image/jpeg')])
    pic = artwork(user, mainwin, qtbot)
    select(user, 1)
    out = tmp_path / 'saved.jpg'
    dialogs.answer('QFileDialog.getSaveFileName', (str(out), ''))
    right_click(user, pic, '&Save cover to file')

    assert out.exists()
    assert QImage(str(out)).width() == 30
    assert out.read_bytes() == data


def test_oversized_flac_cover_is_reported(load, mainwin, user, qtbot, dialogs, tmp_path):
    # Issue #937: "Puddletag should recognize that the file is too big,
    # stop the process and inform the user about it". Synthetic: a PNG
    # followed by zero bytes, over the 16 MiB a FLAC metadata block holds.
    [path] = load('flac', [])
    big = tmp_path / 'big.png'
    big.write_bytes(image('PNG', 10) + bytes(2 ** 24))
    pic = artwork(user, mainwin, qtbot)
    select(user, 1)
    dialogs.answer('QFileDialog.getOpenFileName', (str(big), ''))
    right_click(user, pic, '&Add cover')
    dialogs.answer('QMessageBox.warning', QMessageBox.StandardButton.Ok)
    user.activate()
    user.click_menu('&Save')
    qtbot.waitUntil(lambda: any(call[0] == 'QMessageBox.warning' for call in dialogs.calls))

    [call] = [call for call in dialogs.calls if call[0] == 'QMessageBox.warning']
    assert str(path) in call[1][2]
    assert 'block is too long to write' in call[1][2]
    assert stored(path) == []
    assert mainwin._table.model().taginfo[0].images == []
    assert mainwin.isVisible()


def rename_field(user, qtbot, window, field, name):
    """Double-clicks the field's name and types the new one into the Edit
    Field dialog's Field box, which Alt+F focuses."""
    [row] = [r for r in range(window.table.rowCount()) if window.table.item(r, 0).text() == field]
    item = window.table.item(row, 0)
    user.double_click(window.table.viewport(), window.table.visualItemRect(item).center())
    qtbot.waitUntil(lambda: any(isinstance(w, EditField) and w.isVisible()
                                for w in QApplication.topLevelWidgets()))
    [dialog] = [w for w in QApplication.topLevelWidgets() if isinstance(w, EditField) and w.isVisible()]
    user.activate(dialog)
    user.press(Key.Key_F, Alt)
    user.press(Key.Key_A, Ctrl)
    user.type(name)
    [button] = [b for b in dialog.findChildren(QPushButton) if b.text() == 'E&dit']
    user.click(button)


def edit_cell(user, qtbot, row, field, text):
    """Types text into the row's cell for the field."""
    user.double_click_cell(user.cell(row, field))
    QApplication.focusWidget().selectAll()
    user.type(text)
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: user.table.model().data(user.cell(row, field)) == text)
    user.press(Key.Key_Escape)  # the next row's cell, which Enter opened


@pytest.mark.parametrize('how', ['menu', 'right-click', 'shortcut'])
def test_open_extended_tags(load, user, qtbot, how):
    # menus.txt: "Open's the Extended Tags Dialog. With it you can edit/see
    # all the supported fields in a file."
    [path] = load('mp3', [FRONT])
    user.click(user.table.viewport(), user.table.viewport().rect().bottomRight())
    assert user.table.selectedRows == []
    assert not user.action('E&xtended Tags').isEnabled()
    user.click_cell(user.cell(0, 'title'))
    assert user.action('E&xtended Tags').isEnabled()
    if how == 'menu':
        user.click_menu('E&xtended Tags')
    elif how == 'shortcut':
        user.press(Key.Key_E, Ctrl)
    else:
        user.right_click_cell(user.cell(0, 'title'), 'E&xtended Tags')
    win = extended_tags(qtbot)
    assert rows(win) == [('album', 'Album'), ('title', 'Title 1')]
    assert win.piclabel.images[0]['description'] == 'Front'
    assert win.windowTitle() == str(path)
    win.close()


def test_edit_field_in_every_selected_file(load, user, qtbot):
    # #218. menus.txt: "With it you can edit/see all the supported fields in
    # a file."
    paths = load('mp3', [], [], [])
    user.click_cell(user.cell(0, 'title'))
    user.press(Key.Key_A, Ctrl)
    assert user.table.selectedRows == [0, 1, 2]
    user.press(Key.Key_E, Ctrl)
    win = extended_tags(qtbot)
    edit_value(user, qtbot, win, 'album', 'New')
    assert ('album', 'New') in rows(win)
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: all(in_file(p)['album'] == ['New'] for p in paths))
    assert [in_file(p)['title'] for p in paths] == [['Title 1'], ['Title 2'], ['Title 3']]


@pytest.mark.parametrize('ext', ['flac', 'mp3'])
def test_add_cover_in_extended_tags(load, user, qtbot, dialogs, tmp_path, ext):
    # tut3.txt: "Extended tags has buttons for these operations next to the
    # picture."
    [path] = load(ext, [])
    picture = tmp_path / 'front.png'
    picture.write_bytes(image('PNG', 10))
    user.click_cell(user.cell(0, 'title'))
    user.press(Key.Key_E, Ctrl)
    win = extended_tags(qtbot)
    user.activate(win)
    pic = win.piclabel
    dialogs.answer('QFileDialog.getOpenFileName', (str(picture), ''))
    user.click(pic.addpic)
    describe(user, pic, 'Front')
    user.press(Key.Key_T, Alt)
    user.press(Key.Key_Down)
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: bool(stored(path)))
    assert stored(path) == [{'data': image('PNG', 10), 'description': 'Front',
                             'imagetype': 4, 'mime': 'image/png'}]


def test_edit_keeps_covers_that_differ(load, user, qtbot):
    # #656: "Editing tags via 'extended tags' deletes embedded album art if
    # multiple files with different covers are selected".
    paths = load('mp3', [FRONT], [BACK])
    select(user, 2)
    user.press(Key.Key_E, Ctrl)
    win = extended_tags(qtbot)
    assert win.piclabel.context == 'Cover Varies'
    edit_value(user, qtbot, win, 'album', 'New')
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: all(in_file(p)['album'] == ['New'] for p in paths))
    assert stored(paths[0]) == [FRONT]
    assert stored(paths[1]) == [BACK]


def test_preview_shown_bold(load, user, qtbot):
    # menus.txt, Preview Mode: "any values you change that differ from the
    # original will be shown as emboldened text in the File-View and
    # Extended Tags dialog."
    load('mp3', [])
    user.click_cell(user.cell(0, 'title'))
    user.press(Key.Key_P, Ctrl | Shift)
    edit_cell(user, qtbot, 0, 'title', 'New')
    user.click_cell(user.cell(0, 'title'))
    user.press(Key.Key_E, Ctrl)
    win = extended_tags(qtbot)
    [title] = [r for r in range(win.table.rowCount()) if win.table.item(r, 0).text() == 'title']
    [album] = [r for r in range(win.table.rowCount()) if win.table.item(r, 0).text() == 'album']
    assert win.table.item(title, 1).font().bold()
    assert not win.table.item(album, 1).font().bold()
    win.close()


def test_rename_field_of_one_file(load, user, qtbot):
    # #466: renaming a field in Extended Tags moves its value. menus.txt:
    # "With it you can edit/see all the supported fields in a file."
    [path] = load('flac', [], bailable='Yes')
    user.click_cell(user.cell(0, 'title'))
    user.press(Key.Key_E, Ctrl)
    win = extended_tags(qtbot)
    rename_field(user, qtbot, win, 'bailable', 'quodlibet::bailable')
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: 'quodlibet::bailable' in in_file(path))
    tags = in_file(path)
    assert tags['quodlibet::bailable'] == ['Yes']
    assert 'bailable' not in tags


@pytest.mark.xfail(strict=True, reason='Extended Tags shows a value changed and set back as plain '
                   'text; the File-View shows it in italics')
def test_value_set_back_shown_in_italics(mainwin, user, load, qtbot):
    # menus.txt, Preview Mode: "Values that you've changed, but are the
    # same as the underlying value will be shown in italics."
    load('mp3', [])
    user.press(Key.Key_P, Ctrl | Shift)
    edit_cell(user, qtbot, 0, 'album', 'X')
    edit_cell(user, qtbot, 0, 'album', 'Album')
    select(user, 1)
    user.press(Key.Key_E, Ctrl)
    window = extended_tags(qtbot)
    [row] = [r for r in range(window.table.rowCount()) if window.table.item(r, 0).text() == 'album']
    assert window.table.item(row, 1).font().italic()
    window.close()


@pytest.mark.xfail(strict=True, reason='Extended Tags tells that the covers differ by comparing '
                   "the label's translated text with 'Cover Varies', so in a translated window "
                   'it saves an empty cover list and removes every selected file\'s cover')
def test_edit_keeps_covers_that_differ_in_a_translated_window(load, mainwin, qtbot, user):
    # menus.txt: "With it you can edit/see all the supported fields in a
    # file", and tut3.txt: "<keep> will leave artwork unmodified for each
    # file." (#656: editing a field must not delete the covers.) Synthetic
    # files; the German translation is one of the program's own.
    from PyQt6.QtCore import QTranslator
    translator = QTranslator()
    assert translator.load('translations:puddletag_de.qm')
    QApplication.installTranslator(translator)
    try:
        paths = load('mp3', [FRONT], [BACK])
        select(user, 2)
        user.press(Key.Key_E, Ctrl)
        win = extended_tags(qtbot)
        assert win.piclabel.context == 'Coverauswahl'
        user.activate(win)
        # edit_value presses the English 'E&dit'; the dialog's button
        # is German here, so the dialog is driven by hand.
        [row] = [r for r in range(win.table.rowCount()) if win.table.item(r, 0).text() == 'album']
        item = win.table.item(row, 1)
        user.double_click(win.table.viewport(), win.table.visualItemRect(item).center())
        qtbot.waitUntil(lambda: any(isinstance(w, EditField) and w.isVisible()
                                    for w in QApplication.topLevelWidgets()))
        [dialog] = [w for w in QApplication.topLevelWidgets()
                    if isinstance(w, EditField) and w.isVisible()]
        user.activate(dialog)
        user.press(Key.Key_A, Ctrl)
        user.type('New')
        [button] = [b for b in dialog.findChildren(QPushButton) if b.text() == '&Bearbeiten']
        user.click(button)
        assert ('album', 'New') in rows(win)
        user.click(win.okcancel.okButton)
        qtbot.waitUntil(lambda: all(in_file(p)['album'] == ['New'] for p in paths))
        assert stored(paths[0]) == [FRONT]
        assert stored(paths[1]) == [BACK]
    finally:
        QApplication.removeTranslator(translator)


def load_values(mainwin, make_audio, tmp_path, qtbot, user, values, covers=()):
    """One FLAC per value, with that value in 'bailable' and the cover of
    its number if any; all selected."""
    music = tmp_path / 'music'
    paths = [make_audio(f'0{number}.flac', music, album='Album', title=f'Title {number}',
                        bailable=value)
             for number, value in enumerate(values, 1)]
    for path, cover in zip(paths, covers):
        put(path, cover)
    mainwin.openDir(str(music), False)
    qtbot.waitUntil(lambda: mainwin._table.model().rowCount() == len(paths))
    user.activate()
    select(user, len(paths))
    return paths


@pytest.mark.xfail(strict=True, reason='renaming a row that shows <keep> writes nothing under the '
                   'new name and removes the old field from every file, so each file loses its value')
def test_rename_field_of_several_files(mainwin, make_audio, tmp_path, qtbot, user):
    # No docs sentence covers renaming; the report is #466. Synthetic: two
    # files with different values of the same field.
    paths = load_values(mainwin, make_audio, tmp_path, qtbot, user, ['Yes', 'No'])
    user.press(Key.Key_E, Ctrl)
    win = extended_tags(qtbot)
    assert ('bailable', '<keep>') in rows(win)
    rename_field(user, qtbot, win, 'bailable', 'quodlibet::bailable')
    user.click(win.okcancel.okButton)
    qtbot.waitUntil(lambda: all('quodlibet::bailable' in in_file(p) for p in paths))
    assert [in_file(p)['quodlibet::bailable'] for p in paths] == [['Yes'], ['No']]
    assert all('bailable' not in in_file(p) for p in paths)
