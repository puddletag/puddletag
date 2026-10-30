import struct

import mutagen.id3
from mutagen.id3 import ParseID3v1

from . import apev2
from . import id3

APEv2_Tag = apev2.Tag

_v2_nums = set([2, 3, 4])

ID3_V1 = 'id3_v1'
ID3_V2 = 'id3_v2'
APEv2 = 'ape_v2'

TAG_TYPES = [ID3_V1, ID3_V2, APEv2]


def apev2_values(fn):
    assert isinstance(fn, str)

    return APEv2_Tag(fn).usertags


def convert_id3_frames(frames):
    mapping = id3.Tag.mapping
    return dict((mapping.get(k, k), v.get_value())
                for k, v in id3.handle(frames).items())


def fullread(fileobj, size):
    data = fileobj.read(size)
    if len(data) != size: raise EOFError
    return data


def has_apev2(fn):
    close_file = isinstance(fn, str)
    fileobj = open(fn, 'rb') if close_file else fn

    try:
        fileobj.seek(-160, 2)
        return b"APETAGEX" in fileobj.read()
    except IOError:
        return False
    finally:
        if close_file:
            fileobj.close()


def has_v1(fn):
    close_file = isinstance(fn, str)
    fileobj = open(fn, 'rb') if close_file else fn

    try:
        fileobj.seek(-128, 2)
        return b"TAG" == struct.unpack("3s", fullread(fileobj, 3))[0]
    except (struct.error, EOFError, EnvironmentError):
        return False
    finally:
        if close_file:
            fileobj.close()


def get_v2(fn):
    close_file = isinstance(fn, str)
    fileobj = open(fn, 'rb') if close_file else fn

    size = 5
    try:
        id3, vmaj, vrev = struct.unpack('>3sBB', fullread(fileobj, size))
    except EOFError:
        return
    finally:
        if close_file:
            fileobj.close()

    if id3 == b'ID3' and vmaj in _v2_nums:
        return (2, vmaj, vrev) if vrev != 0 else (2, vmaj)
    return


def id3v1_values(fn):
    close_file = isinstance(fn, str)
    fileobj = open(fn, 'rb') if close_file else fn

    fileobj.seek(-128, 2)
    frames = ParseID3v1(fileobj.read(128))
    if close_file:
        fileobj.close()
    if frames:
        return convert_id3_frames(frames)


def id3v2_values(fn):
    assert isinstance(fn, str)

    try:
        frames = mutagen.id3.ID3(fn)
    except:
        return None
    if frames:
        return convert_id3_frames(frames)


def id3_tags(fn):
    close_file = isinstance(fn, str)
    fileobj = open(fn, 'rb') if close_file else fn
    version = []

    try:
        version = [(1, 1)] if has_v1(fileobj) else []
    except EOFError:
        if close_file:
            fileobj.close()
        return []

    fileobj.seek(0)
    v2 = get_v2(fileobj)
    if v2:
        version.append(v2)
    if close_file:
        fileobj.close()
    return version


def tags_in_file(fn, to_check=(ID3_V1, ID3_V2, APEv2), known_v2=None):
    close_file = isinstance(fn, str)
    fileobj = open(fn, 'rb') if close_file else fn

    try:
        tags = []
        tail = b""
        check_tail = (ID3_V1 in to_check) or (APEv2 in to_check)
        if check_tail:
            try:
                fileobj.seek(-160, 2)
                tail = fileobj.read(160)
            except (IOError, OSError):
                try:
                    fileobj.seek(0, 2)
                    size = fileobj.tell()
                    fileobj.seek(0)
                    tail = fileobj.read(size)
                except (IOError, OSError):
                    tail = b""

        has_v1_tag = (ID3_V1 in to_check) and len(tail) >= 128 and tail[-128:-125] == b"TAG"
        if has_v1_tag:
            tags.append('ID3v1.1')

        if known_v2 and known_v2.startswith('ID3v2'):
            tags.append(known_v2)
        elif ID3_V2 in to_check:
            fileobj.seek(0)
            v2 = get_v2(fileobj)
            if v2:
                tags.append('ID3v' + '.'.join(map(str, v2)))

        if (APEv2 in to_check) and (b"APETAGEX" in tail):
            tags.append('APEv2')

        return tags
    finally:
        if close_file:
            fileobj.close()


_value_types = {
    APEv2: apev2_values,
    ID3_V1: id3v1_values,
    ID3_V2: id3v2_values, }


def tag_values(fn, tag):
    tag = tag.lower()
    if tag.startswith('id3v1'):
        tag = ID3_V1
    elif tag.startswith('id3v2'):
        tag = ID3_V2
    elif tag.startswith('ape'):
        tag = APEv2

    if tag not in TAG_TYPES:
        return {}

    return _value_types[tag](fn)


if __name__ == '__main__':
    import sys

    filename = sys.argv[1]
    # f = open(filename, 'rb')
    print(tags_in_file(filename))
    print(id3v1_values(filename))
    print(id3v2_values(filename))
    print(apev2_values(filename))
