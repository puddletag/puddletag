from .constants import *
from .util import *

AbstractTag = MockTag

extensions = {}
options = []

mapping = {}
revmapping = {}


def loadmapping(filepath, default=None):
    try:
        lines = open(filepath, 'r').read().split('\n')
    except (IOError, OSError):
        if default:
            return default
        else:
            return {}
    mappings = {}
    for l in lines:
        tags = [z.strip() for z in l.split(',')]
        if len(tags) == 3:  # Tag, Source, Target
            try:
                mappings[tags[0]].update({tags[1]: tags[2]})
            except KeyError:
                mappings[tags[0]] = ({tags[1]: tags[2]})
    return mappings


def register_tag(mut_obj, tag, tag_name, tag_exts=None):
    if isinstance(tag_exts, str):
        extensions[tag_exts] = [mut_obj, tag, tag_name]
    elif tag_exts is not None:
        for e in tag_exts:
            extensions[e] = [mut_obj, tag, tag_name]

    options.append([mut_obj, tag, tag_name])


def setmapping(m):
    global revmapping
    global mapping

    mapping = m
    for z in mapping:
        revmapping[z] = CaselessDict([(value, key) for key, value in mapping[z].items()])
    for z in extensions.values():
        try:
            if z[2] in mapping:
                z[1].mapping = mapping[z[2]]
                z[1].revmapping = revmapping[z[2]]
            if 'global' in mapping:
                z[1].mapping.update(mapping['global'])
                z[1].revmapping.update(revmapping['global'])
        except IndexError:
            pass


def Tag(filename):
    """Class that operates on audio tags.
    Currently supports ogg, mp3, mp4, apev2 and flac files

    It can be used in two ways.

    >>>tag = audioinfo.Tag(filename)
    Gets the tags in the audio, filename
    as a dictionary in format {tag: value} in Tag._tags.

    On the other hand, if you have already created
    a tag object. Use link like so:

    >>>tag = audioinfo.Tag()
    >>>tag.link(filename)
    {'artist': "Artist", "track":"12", title:"Title", '__length':"5:14"}

    File info tags like length start with '__'.
    Images can be accessed by either the '__image' tag or via Tag.images. Note
    that images aren't included when iterating through Tag.

    Use save to save tags.

    There are caveats associated with each module, so check out their docstrings
    for more info."""

    fileobj = open(filename, "rb")
    ext = splitext(filename)
    try:
        return extensions[ext][1](filename)
    except KeyError:
        pass

    try:
        header = fileobj.read(128)
        results = [Kind[0].score(filename, fileobj, header) for Kind in options]
    finally:
        fileobj.close()
    results = list(zip(results, options))
    results.sort(key=lambda v: v[0])
    score, Kind = results[-1]
    if score > 0:
        return Kind[1](filename)
    else:
        return None


from . import id3, vorbis, apev2, mp4

tag_modules = (id3, vorbis, apev2, mp4)

for m in tag_modules:
    if hasattr(m, 'filetype'):
        register_tag(*m.filetype)
    if hasattr(m, 'filetypes'):
        list(map(lambda x: register_tag(*x), m.filetypes))

setmapping({'VorbisComment': {'tracknumber': 'track', 'date': 'year'}})

_Tag = Tag
model_tag = lambda x: x
