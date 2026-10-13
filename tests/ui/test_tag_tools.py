"""The Tag Tools menu (menus.txt), run from the main window on a selected
file: Delete APEv2 Tag, Delete All ID3 Tags, Remove ID3v2 Tag and Remove
ID3v1 Tag. Each removes its own tag from the file ("Removes any ID3 tags
found in the selected files", "Removes the ID3v1 tag from the selected
files") and leaves the others; the table then shows what the file holds,
and a later edit saves only that. Synthetic files and tags.
"""
import mutagen.apev2
import mutagen.id3
import pytest

from puddlestuff import audioinfo
from puddlestuff.mainwin import tagtools

pytestmark = pytest.mark.ui


def mp3(make_audio):
    """An MP3 with ID3v2.4 and ID3v1 tags, as puddletag saves it, and an
    APEv2 tag before the ID3v1 one, which ends the file. ID3v1 has no
    composer."""
    path = make_audio('song.mp3', title='Title', artist='Artist', composer='Composer')
    apev2 = mutagen.apev2.APEv2()
    apev2['Album'] = 'APE album'
    apev2.save(str(path))
    audioinfo.Tag(str(path)).save()  # adds ID3v1, "Create an ID3v1 tag" (preferences.txt)
    return path


def flac(make_audio):
    """A FLAC file with an ID3v2.4 tag before its VorbisComment."""
    path = make_audio('song.flac', title='Vorbis title')
    id3 = mutagen.id3.ID3()
    id3.add(mutagen.id3.TIT2(encoding=3, text=['ID3 title']))
    id3.save(str(path))
    return path


def own(ext):
    """A file whose own tag is the one the tool removes, or another."""
    return lambda make_audio: make_audio('song.' + ext, title='Title', artist='Artist')


FILES = {'flac': flac, 'mp3': mp3}
ALL = {'artist': ['Artist'], 'composer': ['Composer'], 'title': ['Title']}
OWN = {'artist': ['Artist'], 'title': ['Title']}
TOOLS = ['remove_apev2', 'remove_id3', 'remove_id3v1', 'remove_id3v2']


def case(kind, tool, listed, fields):
    return pytest.param(kind, tool, listed, fields, id=kind + '-' + tool)


CASES = [
    # The file, the tool, __tag after it ("Comma-Separated list of tags
    # found in file", tags.txt) where the file has two tags, and the fields
    # the file then holds. An MP3's ID3v1 tag holds the title and artist.
    case('mp3', 'remove_apev2', 'ID3v2.4, ID3v1.1', ALL),
    # Before, after removing ID3v2 the table kept showing its fields, and
    # the next edit saved them back.
    case('mp3', 'remove_id3', 'APEv2', {}),
    case('mp3', 'remove_id3v1', 'ID3v2.4, APEv2', ALL),
    case('mp3', 'remove_id3v2', 'ID3v1.1, APEv2', OWN),
    case('flac', 'remove_id3', 'VorbisComment', {'title': ['Vorbis title']}),
    case('flac', 'remove_id3v2', 'VorbisComment', {'title': ['Vorbis title']}),
]
for ext in ['aiff', 'dff', 'dsf']:
    FILES[ext] = own(ext)
    # Before, the file kept its ID3 tag.
    CASES += [case(ext, tool, None, {}) for tool in ['remove_id3', 'remove_id3v2']]
for ext in ['ape', 'mpc', 'wv']:
    FILES[ext] = own(ext)
    CASES += [case(ext, 'remove_apev2', None, {})]
    # Before, each tool removed the file's APEv2 tag.
    CASES += [case(ext, tool, None, OWN) for tool in TOOLS[1:]]


@pytest.mark.parametrize('kind, tool, listed, fields', CASES)
def test_tag_tool(mainwin, make_audio, qtbot, kind, tool, listed, fields):
    path = FILES[kind](make_audio)
    mainwin.openDir(str(path.parent), False)
    model = mainwin._table.model()
    qtbot.waitUntil(lambda: model.rowCount() == 1)
    mainwin._table.selectAll()
    qtbot.waitUntil(lambda: len(mainwin._table.selectedRows) == 1)
    getattr(tagtools, tool)(mainwin)
    in_file = audioinfo.Tag(str(path))
    assert (in_file['__tag'] if listed else None, audioinfo.usertags(in_file)) == (listed, fields)
    assert audioinfo.usertags(model.taginfo[0]) == fields
    model.setRowData(0, {'genre': ['Edited']}, undo=True)
    assert audioinfo.usertags(audioinfo.Tag(str(path))) == dict(fields, genre=['Edited'])
