"""Undo after removing tags (menus.txt), run as a user runs it. Remove Tag:
"although this operation can be undone, the tag is not restored as it was
before: a new one is created, and only supported fields are restored." The
Tag Tools: "Deleting 'official' tags can be undone though. And by undo, I
don't mean the tag will be restored as before. A new tag will be created
with the fields puddletag remembers", but "if you delete a tag not
considered the 'official' tag (eg. When you delete APEv2 from and mp3 file)
there'll be no way to undo that action." Each undo is checked in the table
and on disk. Synthetic files.
"""
import mutagen.apev2
import mutagen.id3
import pytest
from PyQt6.QtCore import QBuffer, QIODevice, Qt
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication

from puddlestuff import audioinfo

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier

# Every format puddletag registers, as the kinds of file make_audio makes.
FORMATS = ['aiff', 'ape', 'apl', 'dff', 'dsf', 'flac', 'm4a', 'mp3', 'mpc', 'ogg', 'opus', 'wma', 'wv']
TOOLS = {
    'apev2': 'Remove &APEv2 Tag',
    'id3': 'Remove All &ID3 Tags',
    'id3v1': 'Remove ID3v&1 Tag',
    'id3v2': 'Remove ID3v&2 Tag',
}


def in_file(path):
    return audioinfo.usertags(audioinfo.Tag(str(path)))


def in_table(table):
    return [audioinfo.usertags(audio) for audio in table.model().taginfo]


def tags_listed(path):
    """The file's tags, as __tag lists them ("Comma-Separated list of tags
    found in file", tags.txt)."""
    return audioinfo.Tag(str(path))['__tag']


def mp3(make_audio, name, directory, **fields):
    """An MP3 with ID3v2.4 and ID3v1 tags, as puddletag saves it, and an
    APEv2 tag before the ID3v1 one, which ends the file. ID3v1 has no
    composer."""
    path = make_audio(name, directory, **fields)
    apev2 = mutagen.apev2.APEv2()
    apev2['Album'] = 'APE album'
    apev2.save(str(path))
    audioinfo.Tag(str(path)).save()  # adds ID3v1, "the option of including ID3v1.1" (preferences.txt)
    return path


def flac(make_audio, name, directory, **fields):
    """A FLAC file with an ID3v2.4 tag before its VorbisComment."""
    path = make_audio(name, directory, **fields)
    id3 = mutagen.id3.ID3()
    id3.add(mutagen.id3.TIT2(encoding=3, text=['ID3 title']))
    id3.save(str(path))
    return path


def png():
    """A real PNG, so that its MIME type can be told from its data."""
    picture = QImage(10, 1, QImage.Format.Format_RGB32)
    picture.fill(0)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert picture.save(buffer, 'PNG')
    return bytes(buffer.data())


def covers(audio):
    return [cover['data'] for cover in audio.get('__image', [])]


def load(mainwin, qtbot, user, paths):
    """Opens the files' folder, with the window active and the File-View
    focused."""
    mainwin.openDir(str(paths[0].parent), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == len(paths))
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]
    user.activate()
    table.setFocus()
    return table


def select(user, rows):
    """Clicks the first row's Title cell and Shift-clicks the last row's."""
    user.click_cell(user.cell(rows[0], 'title'))
    if len(rows) > 1:
        user.click_cell(user.cell(rows[-1], 'title'), Shift)


def edit(user, qtbot, row, text, path):
    """Types text into the row's Title cell (two rows or more loaded)."""
    user.double_click_cell(user.cell(row, 'title'))
    QApplication.focusWidget().selectAll()
    user.type(text)
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: in_file(path)['title'] == [text])
    user.press(Key.Key_Escape)  # the next row's cell, which Enter opened


# Each way the window offers Remove Tag; its other cases press Ctrl+R.
REMOVE_TAG = {
    'Ctrl+R': lambda user: user.press(Key.Key_R, Ctrl),
    'Edit menu': lambda user: user.click_menu('&Remove Tag'),
    'right-click menu': lambda user: user.right_click_cell(user.cell(0, 'title'), '&Remove Tag'),
}


@pytest.mark.parametrize('remove', REMOVE_TAG.values(), ids=REMOVE_TAG.keys())
def test_remove_tag_undone(mainwin, make_audio, tmp_path, qtbot, user, remove):
    # "although this operation can be undone, the tag is not restored as it
    # was before: a new one is created, and only supported fields are
    # restored." (Remove Tag), and "When there's nothing left to undo, Undo
    # is greyed out." (Undo). The MP3 has no APEv2 tag, which Remove Tag
    # would leave.
    music = tmp_path / 'music'
    path = make_audio('01.mp3', music, artist='Artist 1', title='Title 1')
    table = load(mainwin, qtbot, user, [path])
    select(user, [0])

    remove(user)

    assert in_file(path) == {}
    assert in_table(table) == [{}]
    assert user.action('&Undo').isEnabled()

    user.press(Key.Key_Z, Ctrl)

    assert in_file(path) == {'artist': ['Artist 1'], 'title': ['Title 1']}
    assert in_table(table) == [{'artist': ['Artist 1'], 'title': ['Title 1']}]
    assert not user.action('&Undo').isEnabled()


@pytest.mark.parametrize('ext', FORMATS)
def test_remove_tag_undone_in_every_format(mainwin, make_audio, tmp_path, qtbot, user, ext):
    # "although this operation can be undone, the tag is not restored as it
    # was before: a new one is created, and only supported fields are
    # restored." (Remove Tag), in every format puddletag registers.
    music = tmp_path / 'music'
    paths = [make_audio(f'0{i}.{ext}', music, artist=f'Artist {i}', title=f'Title {i}') for i in (1, 2)]
    original = [{'artist': [f'Artist {i}'], 'title': [f'Title {i}']} for i in (1, 2)]
    table = load(mainwin, qtbot, user, paths)
    select(user, [0, 1])

    user.press(Key.Key_R, Ctrl)
    user.activate()

    assert [in_file(p) for p in paths] == [{}, {}]
    assert in_table(table) == [{}, {}]

    user.press(Key.Key_Z, Ctrl)

    assert [in_file(p) for p in paths] == original
    assert in_table(table) == original
    assert not user.action('&Undo').isEnabled()


def test_remove_tag_undone_without_unsupported_frames(mainwin, make_audio, tmp_path, qtbot, user):
    # "the tag is not restored as it was before ... only supported fields
    # are restored": a PRIV frame is not among the supported frames
    # (id3.txt), so it is gone after the undo.
    music = tmp_path / 'music'
    path = make_audio('01.mp3', music, artist='Artist 1', title='Title 1')
    tag = mutagen.id3.ID3(str(path))
    tag.add(mutagen.id3.PRIV(owner='example.org', data=b'private'))
    tag.save()
    table = load(mainwin, qtbot, user, [path])
    assert in_table(table) == [{'artist': ['Artist 1'], 'title': ['Title 1']}]
    select(user, [0])

    user.press(Key.Key_R, Ctrl)
    user.press(Key.Key_Z, Ctrl)

    assert sorted(mutagen.id3.ID3(str(path)).keys()) == ['TIT2', 'TPE1']
    assert in_file(path) == {'artist': ['Artist 1'], 'title': ['Title 1']}
    assert in_table(table) == [{'artist': ['Artist 1'], 'title': ['Title 1']}]


# The file kind, the tool, and __tag once the tool removed its tag.
OFFICIAL = {
    'ape-apev2': ('ape', 'apev2', None),
    'apl-apev2': ('apl', 'apev2', None),
    'mp3-id3': ('mp3', 'id3', 'APEv2'),
    'mp3-id3v1': ('mp3', 'id3v1', 'ID3v2.4, APEv2'),
    'mp3-id3v2': ('mp3', 'id3v2', 'ID3v1.1, APEv2'),
    'mpc-apev2': ('mpc', 'apev2', None),
    'wv-apev2': ('wv', 'apev2', None),
}


@pytest.mark.parametrize('kind, tool, listed', OFFICIAL.values(), ids=OFFICIAL.keys())
def test_official_tag_undone(mainwin, make_audio, qtbot, user, tmp_path, kind, tool, listed):
    # "Deleting 'official' tags can be undone though. And by undo, I don't
    # mean the tag will be restored as before. A new tag will be created
    # with the fields puddletag remembers." Remove APEv2 Tag: "Undoable for
    # files that use APEv2 as the default tag (ie. Musepack, Wavpack and
    # Monkey's Audio)"; Remove All ID3 Tags and Remove ID3v2 Tag: "Undoable
    # for files that use ID3 as the default tag (ie. MP3, AIFF, DSF and
    # DSDIFF)"; Remove ID3v1 Tag: "Undoable only for mp3 files".
    music = tmp_path / 'music'
    paths = []
    fields = []
    for i in (1, 2):
        original = {'artist': [f'Artist {i}'], 'title': [f'Title {i}']}
        if kind == 'mp3':
            original['composer'] = ['Composer']
            paths.append(mp3(make_audio, f'0{i}.mp3', music, artist=f'Artist {i}', composer='Composer', title=f'Title {i}'))
        else:
            paths.append(make_audio(f'0{i}.{kind}', music, artist=f'Artist {i}', title=f'Title {i}'))
        fields.append(original)
    table = load(mainwin, qtbot, user, paths)
    select(user, [0, 1])
    user.click_menu(TOOLS[tool])
    user.activate()
    if kind == 'mp3':
        assert tags_listed(paths[0]) == listed
    else:
        assert in_file(paths[0]) == {}

    user.press(Key.Key_Z, Ctrl)

    assert [in_file(p) for p in paths] == fields
    assert in_table(table) == fields
    if kind == 'mp3':
        assert [tags_listed(p) for p in paths] == ['ID3v2.4, ID3v1.1, APEv2'] * 2
    assert not user.action('&Undo').isEnabled()


@pytest.mark.parametrize('tool', ['id3', 'id3v2'])
@pytest.mark.parametrize('ext', ['aiff', 'dff', 'dsf'])
def test_id3_chunk_tag_undone(mainwin, user, qtbot, make_audio, tmp_path, ext, tool):
    # "Deleting 'official' tags can be undone though." and, for these tools,
    # "Undoable for files that use ID3 as the default tag (ie. MP3, AIFF,
    # DSF and DSDIFF)."
    music = tmp_path / 'music'
    paths = [make_audio(f'0{i}.{ext}', music, artist=f'Artist {i}', title=f'Title {i}') for i in (1, 2)]
    original = [{'artist': [f'Artist {i}'], 'title': [f'Title {i}']} for i in (1, 2)]
    table = load(mainwin, qtbot, user, paths)
    select(user, [0, 1])
    user.click_menu(TOOLS[tool])
    user.activate()
    assert [in_file(p) for p in paths] == [{}, {}]

    user.press(Key.Key_Z, Ctrl)

    assert [in_file(p) for p in paths] == original
    assert in_table(table) == original
    assert not user.action('&Undo').isEnabled()


# The file, the tool, the fields and __tag the file keeps.
UNOFFICIAL = {
    'flac-id3': (flac, 'id3', {'title': ['Vorbis title']}, 'VorbisComment'),
    'mp3-apev2': (mp3, 'apev2', None, 'ID3v2.4, ID3v1.1'),
}


@pytest.mark.parametrize('count', [1, 2], ids=['1 file', '2 files'])
@pytest.mark.parametrize('kind, tool, fields, listed', UNOFFICIAL.values(), ids=UNOFFICIAL.keys())
def test_unofficial_tag_stays_removed(kind, tool, fields, listed, count, mainwin, make_audio, tmp_path, qtbot, user):
    # "if you delete a tag not considered the 'official' tag (eg. When you
    # delete APEv2 from and mp3 file) there'll be no way to undo that action."
    music = tmp_path / 'music'
    if kind is mp3:
        paths = [mp3(make_audio, f'0{i}.mp3', music, artist=f'Artist {i}', composer='Composer', title=f'Title {i}')
                 for i in range(1, count + 1)]
        expected = [{'artist': [f'Artist {i}'], 'composer': ['Composer'], 'title': [f'Title {i}']}
                    for i in range(1, count + 1)]
    else:
        paths = [flac(make_audio, f'0{i}.flac', music, title='Vorbis title') for i in range(1, count + 1)]
        expected = [fields] * count
    table = load(mainwin, qtbot, user, paths)

    select(user, list(range(count)))
    user.click_menu(TOOLS[tool])
    user.activate()
    user.press(Key.Key_Z, Ctrl)

    for path in paths:
        assert tags_listed(path) == listed
        if kind is mp3:
            with pytest.raises(mutagen.apev2.APENoHeaderError):
                mutagen.apev2.APEv2(str(path))
    assert [in_file(path) for path in paths] == expected
    assert in_table(table) == expected


# The file kind and the tool.
ONE_FILE = {
    'ape-apev2': ('ape', 'apev2'),
    'mp3-id3': ('mp3', 'id3'),
    'mp3-id3v1': ('mp3', 'id3v1'),
    'mp3-id3v2': ('mp3', 'id3v2'),
}
NOTHING_TO_UNDO = {
    'aiff-id3v1': ('aiff', 'id3v1'),
    'ape-id3': ('ape', 'id3'),
    'flac-apev2': ('flac', 'apev2'),
    'mp3-apev2': ('mp3', 'apev2'),
}


@pytest.mark.parametrize('kind, tool', ONE_FILE.values(), ids=ONE_FILE.keys())
def test_official_tag_undone_on_one_file(mainwin, make_audio, tmp_path, qtbot, user, kind, tool):
    # "Deleting 'official' tags can be undone though. ... A new tag will be
    # created with the fields puddletag remembers." (Remove APEv2 Tag:
    # "Undoable for files that use APEv2 as the default tag"; the ID3 tools:
    # "Undoable for files that use ID3 as the default tag" and, for ID3v1,
    # "Undoable only for mp3 files".)
    music = tmp_path / 'music'
    if kind == 'mp3':
        path = mp3(make_audio, '01.mp3', music, artist='Artist 1', composer='Composer', title='Title 1')
        fields = {'artist': ['Artist 1'], 'composer': ['Composer'], 'title': ['Title 1']}
    else:
        path = make_audio('01.' + kind, music, artist='Artist 1', title='Title 1')
        fields = {'artist': ['Artist 1'], 'title': ['Title 1']}
    table = load(mainwin, qtbot, user, [path])

    select(user, [0])
    user.click_menu(TOOLS[tool])

    assert user.action('&Undo').isEnabled()
    user.press(Key.Key_Z, Ctrl)

    assert in_file(path) == fields
    assert in_table(table) == [fields]
    if kind == 'mp3':
        assert tags_listed(path) == 'ID3v2.4, ID3v1.1, APEv2'
    assert not user.action('&Undo').isEnabled()


def test_one_file_tag_tool_undone_before_the_edit_before_it(mainwin, make_audio, tmp_path, qtbot, user):
    # "Undo's the last edit": the removal is the last edit, so Undo restores
    # the tag first, with "the fields puddletag remembers" ("Deleting
    # 'official' tags can be undone though"), and only then the edit.
    music = tmp_path / 'music'
    paths = [mp3(make_audio, f'0{i}.mp3', music, artist=f'Artist {i}', composer='Composer', title=f'Title {i}')
             for i in (1, 2)]
    table = load(mainwin, qtbot, user, paths)

    edit(user, qtbot, 0, 'Edited', paths[0])
    select(user, [0])
    user.click_menu('Remove All &ID3 Tags')

    user.press(Key.Key_Z, Ctrl)
    assert in_file(paths[0]) == {'artist': ['Artist 1'], 'composer': ['Composer'], 'title': ['Edited']}

    user.press(Key.Key_Z, Ctrl)
    original = {'artist': ['Artist 1'], 'composer': ['Composer'], 'title': ['Title 1']}
    assert in_file(paths[0]) == original
    assert in_table(table)[0] == original
    assert not user.action('&Undo').isEnabled()


@pytest.mark.parametrize('kind, tool', NOTHING_TO_UNDO.values(), ids=NOTHING_TO_UNDO.keys())
def test_tag_tool_with_nothing_to_undo(mainwin, make_audio, tmp_path, qtbot, user, kind, tool):
    # "When there's nothing left to undo, Undo is greyed out." and, for a tag
    # that isn't the 'official' one, "there'll be no way to undo that action."
    music = tmp_path / 'music'
    if kind == 'mp3':
        paths = [mp3(make_audio, f'0{i}.mp3', music, artist=f'Artist {i}', composer='Composer', title=f'Title {i}')
                 for i in (1, 2)]
    else:
        paths = [make_audio(f'0{i}.{kind}', music, artist=f'Artist {i}', title=f'Title {i}') for i in (1, 2)]
    load(mainwin, qtbot, user, paths)

    select(user, [0, 1])
    user.click_menu(TOOLS[tool])
    user.activate()

    assert not user.action('&Undo').isEnabled()


def test_edit_undone_after_a_tag_tool_with_no_undo(mainwin, make_audio, tmp_path, qtbot, user):
    # "Undo's the last edit": a removal that "there'll be no way to undo"
    # isn't an edit, so Undo still reaches the edit before it.
    music = tmp_path / 'music'
    paths = [mp3(make_audio, f'0{i}.mp3', music, artist=f'Artist {i}', composer='Composer', title=f'Title {i}')
             for i in (1, 2)]
    table = load(mainwin, qtbot, user, paths)

    edit(user, qtbot, 0, 'Edited', paths[0])
    select(user, [0, 1])
    user.click_menu('Remove &APEv2 Tag')
    user.activate()

    user.press(Key.Key_Z, Ctrl)
    assert in_file(paths[0])['title'] == ['Title 1']
    assert in_table(table)[0]['title'] == ['Title 1']
    assert tags_listed(paths[0]) == 'ID3v2.4, ID3v1.1'
    assert not user.action('&Undo').isEnabled()


def add_cover(path):
    """Gives the file a front cover."""
    tag = audioinfo.Tag(str(path))
    tag.update({'__image': [{'data': png(), 'description': 'Front', 'imagetype': 3, 'mime': 'image/png'}]})
    tag.save()


def check_covers_back(table, paths, fields):
    """Both files hold their fields and the cover again, on disk and in the
    table."""
    assert [in_file(p) for p in paths] == fields
    assert in_table(table) == fields
    for row, path in enumerate(paths):
        assert covers(audioinfo.Tag(str(path))) == [png()]
        assert covers(table.model().taginfo[row]) == [png()]


@pytest.mark.parametrize('ext', FORMATS)
def test_remove_tag_undone_with_cover(mainwin, make_audio, tmp_path, qtbot, user, ext):
    # "although this operation can be undone, the tag is not restored as it
    # was before: a new one is created, and only supported fields are
    # restored." (menus.txt); tags.txt lists the cover among the fields.
    music = tmp_path / 'music'
    fields = [{'artist': [f'Artist {i}'], 'title': [f'Title {i}']} for i in (1, 2)]
    paths = [make_audio(f'0{i}.{ext}', music, artist=f'Artist {i}', title=f'Title {i}') for i in (1, 2)]
    for path in paths:
        add_cover(path)
    table = load(mainwin, qtbot, user, paths)
    select(user, [0, 1])

    user.press(Key.Key_R, Ctrl)
    user.activate()
    assert covers(audioinfo.Tag(str(paths[0]))) == []

    user.press(Key.Key_Z, Ctrl)
    check_covers_back(table, paths, fields)


@pytest.mark.parametrize('kind, tool', [('ape', 'apev2'), ('mp3', 'id3')], ids=['ape-apev2', 'mp3-id3'])
def test_official_tag_undone_with_cover(mainwin, make_audio, tmp_path, qtbot, user, kind, tool):
    # "Deleting 'official' tags can be undone though. And by undo, I don't
    # mean the tag will be restored as before. A new tag will be created
    # with the fields puddletag remembers" (menus.txt); tags.txt lists the
    # cover among the fields.
    music = tmp_path / 'music'
    if kind == 'mp3':
        fields = [{'artist': [f'Artist {i}'], 'composer': ['Composer'], 'title': [f'Title {i}']} for i in (1, 2)]
        paths = [mp3(make_audio, f'0{i}.mp3', music, artist=f'Artist {i}', composer='Composer', title=f'Title {i}')
                 for i in (1, 2)]
    else:
        fields = [{'artist': [f'Artist {i}'], 'title': [f'Title {i}']} for i in (1, 2)]
        paths = [make_audio(f'0{i}.{kind}', music, artist=f'Artist {i}', title=f'Title {i}') for i in (1, 2)]
    for path in paths:
        add_cover(path)
    table = load(mainwin, qtbot, user, paths)
    select(user, [0, 1])

    user.click_menu(TOOLS[tool])
    user.activate()
    assert covers(audioinfo.Tag(str(paths[0]))) == []

    user.press(Key.Key_Z, Ctrl)
    check_covers_back(table, paths, fields)
