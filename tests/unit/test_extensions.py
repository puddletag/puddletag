"""File extensions: every one puddletag registers (audioinfo.extensions), and
common ones it doesn't but opens by their content. A file of each kind opens
with its format's tag class and keeps a field across a save.

Files are opened both ways puddletag opens them: audioinfo.Tag, and the
replacement the table installs over it (tagmodel._Tag), which wraps each
tag class for preview mode. Synthetic files from make_audio, copied under
each extension.
"""
import shutil
from types import SimpleNamespace

import pytest

from puddlestuff import audioinfo, tagmodel
from puddlestuff.audioinfo import apev2

# Each registered extension and the kind of file make_audio makes for it.
REGISTERED = {'aiff': 'aiff', 'ape': 'ape', 'apl': 'apl', 'dff': 'dff', 'dsf': 'dsf', 'flac': 'flac',
              'm4a': 'm4a', 'm4v': 'm4a', 'mp3': 'mp3', 'mp4': 'm4a', 'mpc': 'mpc', 'ogg': 'ogg',
              'opus': 'opus', 'opus.ogg': 'opus', 'wma': 'wma', 'wmv': 'wma', 'wv': 'wv'}
# Common extensions puddletag doesn't register, and their kind.
UNREGISTERED = {'aif': 'aiff', 'aifc': 'aiff', 'm4b': 'm4a', 'm4p': 'm4a', 'mp2': 'mp3', 'oga': 'ogg'}
CASES = sorted({**REGISTERED, **UNREGISTERED}.items()) + [('ogg', 'opus')]  # Opus encoders write .ogg too


@pytest.fixture(params=['audioinfo.Tag', 'table'])
def open_tag(request):
    if request.param == 'audioinfo.Tag':
        return audioinfo._Tag  # audioinfo.Tag before the table replaces it
    return tagmodel._Tag(SimpleNamespace(previewMode=False))


def test_registered_extensions():
    assert sorted(audioinfo.extensions) == sorted(REGISTERED)


@pytest.mark.parametrize('ext, kind', CASES, ids=[f'{ext}-{kind}' for ext, kind in CASES])
def test_extension_opens_its_kind(make_audio, tmp_path, open_tag, ext, kind):
    made = make_audio('made.' + kind, title='Song')
    path = tmp_path / ('song.' + ext)
    shutil.copy(made, path)
    tag = open_tag(str(path))
    assert isinstance(tag, type(audioinfo._Tag(str(made))))
    tag.update({'title': ['New']})
    tag.save()
    assert open_tag(str(path))['title'] == ['New']


@pytest.mark.parametrize('name', ['song.tta', 'song.xyz'])
def test_generic_apev2_tag(make_audio, tmp_path, open_tag, name):
    # Files of a kind puddletag doesn't know, with an APEv2 tag, are read
    # with the generic APEv2 class: a TrueAudio file (which mutagen knows)
    # and any other file.
    path = make_audio('song.tta', title='Song')
    if name != path.name:
        path = path.rename(tmp_path / name)
    tag = open_tag(str(path))
    assert isinstance(tag, apev2.Tag)
    assert tag['title'] == ['Song']
    tag.update({'title': ['New']})
    tag.save()
    assert open_tag(str(path))['title'] == ['New']
