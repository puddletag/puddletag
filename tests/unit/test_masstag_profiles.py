"""Mass Tagging's profiles as Configure Profiles' OK saves them and puddletag
reads them back at start (tut5.txt, "Configuring Profiles"): every option a
profile holds, the order the profiles are listed in, and profile files
puddletag can't read. tut5.txt says nothing on how profiles are kept, so the
expected values are synthetic: a saved profile comes back as it was saved, in
the order it was listed. Synthetic profiles, tag sources and files.
"""
import json
import os

import pytest

from puddlestuff.masstag import CONTINUE, STOP, MassTagProfile, TagSourceProfile
from puddlestuff.masstag.config import load_all_mtps, mtp_from_file, save_mtp


class Source:
    """A tag source as a profile names it: a name and group_by. Synthetic."""
    group_by = ['album', 'artist']

    def __init__(self, name):
        self.name = name


SOURCES = [Source('First Source'), Source('Second Source')]


def source_profile(name, fields=(), if_no_result=CONTINUE, replace_fields=()):
    """A profile's tag source, as Add Tag Source makes it: the source by name,
    its Fields, If no results found and Fields to replace."""
    return TagSourceProfile(None, Source(name), list(fields), if_no_result,
                            list(replace_fields))


def profile(name, sources=None, **options):
    """A synthetic profile with these options (MassTagProfile's keywords), as
    the profile editor's OK builds it. It polls First Source unless sources
    says otherwise."""
    if sources is None:
        sources = [source_profile('First Source')]
    options.setdefault('album_bound', 0.7)
    return MassTagProfile(name, profiles=sources, **options)


def write_profiles(folder, files, order=None):
    """Saves each profile to folder/<file name> as Configure Profiles' OK
    does, then writes the order file's lines, if given. files: {file name:
    profile}."""
    for filename, mtp in files.items():
        save_mtp(mtp, os.path.join(folder, filename))
    if order is not None:
        with open(os.path.join(folder, 'order'), 'w') as f:
            f.write('\n'.join(order))


def listed(folder, sources=SOURCES):
    """The profiles as puddletag lists them at start: (name, description)."""
    return [(mtp.name, mtp.desc) for mtp in load_all_mtps(str(folder), sources)]


def loaded_sources(mtp):
    """(tag source, Fields, If no results found, Fields to replace) of each
    of a loaded profile's tag sources."""
    return [(t.tag_source, t.fields, t.if_no_result, t.replace_fields)
            for t in mtp.profiles]


def test_every_option_survives_a_save_and_a_load(tmp_path):
    """Synthetic expectation (tut5.txt says nothing on how profiles are
    kept): a profile comes back from its file as it was saved. tut5.txt, Tag
    Sources: "Each tag source will be polled in the order listed here." """
    mtp = profile('Every Option', desc='Für Ελληνικά', fields=['title', 'track'],
                  file_pattern='%album%/%track% - %title%', album_bound=0.6,
                  track_bound=0.9, jfdi=True, leave_existing=True,
                  sources=[source_profile('Second Source', ['genre', 'year'], STOP, ['genre']),
                           source_profile('First Source')])
    path = str(tmp_path / 'Every Option.mtp')
    save_mtp(mtp, path)

    loaded = mtp_from_file(path, SOURCES)

    assert loaded.name == 'Every Option'
    assert loaded.desc == 'Für Ελληνικά'
    assert loaded.fields == ['title', 'track']
    assert loaded.file_pattern == '%album%/%track% - %title%'
    assert loaded.album_bound == 0.6
    assert loaded.track_bound == 0.9
    assert loaded.jfdi is True
    assert loaded.leave_existing is True
    assert loaded_sources(loaded) == [(SOURCES[1], ['genre', 'year'], STOP, ['genre']),
                                      (SOURCES[0], [], CONTINUE, [])]


def test_a_profile_file_as_puddletag_writes_it_loads(tmp_path):
    """Synthetic expectation (tut5.txt says nothing on how profiles are
    kept): users have these files on disk, so the form puddletag writes keeps
    loading. tut5.txt, Name: "The name of the profile." """
    data = {'info': {'name': 'Disk', 'desc': 'd', 'file_pattern': '%album%/%title%',
                     'fields': ['title'], 'jfdi': False, 'leave_existing': True,
                     'album_bound': 60, 'track_bound': 90, 'numsources': 2},
            'config0': {'source': 'First Source', 'if_no_result': 1,
                        'fields': 'genre,year', 'replace_fields': 'genre'},
            'config1': {'source': 'Second Source', 'if_no_result': 0,
                        'fields': '', 'replace_fields': ''}}
    path = tmp_path / 'Disk.mtp'
    path.write_text(json.dumps(data))

    loaded = mtp_from_file(str(path), SOURCES)

    assert loaded.name == 'Disk'
    assert loaded.desc == 'd'
    assert loaded.fields == ['title']
    assert loaded.file_pattern == '%album%/%title%'
    assert loaded.album_bound == 0.6
    assert loaded.track_bound == 0.9
    assert loaded.jfdi is False
    assert loaded.leave_existing is True
    assert loaded_sources(loaded) == [(SOURCES[0], ['genre', 'year'], STOP, ['genre']),
                                      (SOURCES[1], [], CONTINUE, [])]


def test_profiles_are_listed_in_the_saved_order(tmp_path):
    """Synthetic expectation (tut5.txt says nothing on how profiles are
    kept): the profiles are listed in the order Configure Profiles showed
    them. tut5.txt, Name: "The name of the profile." """
    write_profiles(tmp_path, {'Alpha.mtp': profile('Alpha'),
                              'Beta.mtp': profile('Beta'),
                              'Gamma.mtp': profile('Gamma')},
                   order=['Gamma', 'Alpha', 'Beta'])

    assert [n for n, _ in listed(tmp_path)] == ['Gamma', 'Alpha', 'Beta']


def test_profiles_the_order_file_lacks_come_last(tmp_path):
    """Synthetic expectation (tut5.txt says nothing on how profiles are
    kept): the profiles the order file names come first in its order, a line
    naming no profile is ignored and a line's spaces don't count. tut5.txt,
    Name: "The name of the profile." """
    write_profiles(tmp_path, {'Alpha.mtp': profile('Alpha'),
                              'Beta.mtp': profile('Beta'),
                              'Delta.mtp': profile('Delta'),
                              'Gamma.mtp': profile('Gamma')},
                   order=['Gamma', 'Gone', ' Alpha ', ''])

    names = [n for n, _ in listed(tmp_path)]

    assert names[:2] == ['Gamma', 'Alpha']
    assert sorted(names[2:]) == ['Beta', 'Delta']


def test_without_an_order_file_every_profile_loads(tmp_path):
    """Synthetic expectation (tut5.txt says nothing on how profiles are
    kept): a folder with no order file still lists every profile. tut5.txt,
    Name: "The name of the profile." """
    write_profiles(tmp_path, {'Alpha.mtp': profile('Alpha'),
                              'Beta.mtp': profile('Beta')})

    assert sorted(n for n, _ in listed(tmp_path)) == ['Alpha', 'Beta']


def test_a_tag_source_puddletag_lacks_is_kept_by_name(tmp_path):
    """tut5.txt, Tag Sources: "A tag source puddletag doesn't have (one
    removed in an update, say) is listed with **(not found)** after its
    name. It's kept when the profile is saved, and searches skip it." So the
    profile loads with the source's name kept in its place, and the other
    sources stay."""
    path = str(tmp_path / 'Old.mtp')
    save_mtp(profile('Old', [source_profile('Gone Source'),
                             source_profile('First Source')]), path)

    loaded = mtp_from_file(path, SOURCES)

    assert loaded.profiles[0].tag_source is None
    assert loaded.profiles[0].missing_source == 'Gone Source'
    assert loaded.profiles[1].tag_source is SOURCES[0]


@pytest.mark.xfail(strict=True, reason='two profiles with one name: the order file names it '
                   'twice and only one of them loads, listed twice')
def test_profiles_with_one_name_all_load_in_their_order(tmp_path):
    """Synthetic expectation (tut5.txt says nothing on how profiles are
    kept): profiles that share a name, as Duplicate then OK saves them, all
    load, in the order the profile list had. tut5.txt, Name: "The name of
    the profile." """
    write_profiles(tmp_path, {'Same.mtp': profile('Same', desc='first'),
                              'Same_0.mtp': profile('Same', desc='second'),
                              'Same_1.mtp': profile('Same', desc='third'),
                              'Other.mtp': profile('Other')},
                   order=['Same', 'Other', 'Same', 'Same'])
    assert listed(tmp_path) == [('Same', 'first'), ('Other', ''),
                                ('Same', 'second'), ('Same', 'third')]


@pytest.mark.xfail(strict=True, reason='two profiles with one name: the order file names it '
                   'twice and only one of them loads, listed twice')
def test_twelve_profiles_with_one_name_keep_their_order(tmp_path):
    """Synthetic expectation (tut5.txt says nothing on how profiles are
    kept): profiles that share a name load in the order the profile list
    had, also past ten, where Same_10 comes after Same_9. tut5.txt, Name:
    "The name of the profile." """
    write_profiles(tmp_path, {'Same.mtp': profile('Same', desc='0'),
                              **{f'Same_{n}.mtp': profile('Same', desc=str(n + 1))
                                 for n in range(11)}},
                   order=['Same'] * 12)
    assert [desc for _, desc in listed(tmp_path)] == [str(n) for n in range(12)]


@pytest.mark.xfail(strict=True, reason="a profile file puddletag can't read is listed as a "
                   'nameless profile, or its error stops the loading')
@pytest.mark.parametrize('text', [
    '',
    '[1, 2]',
    'not json',
    '{"info": 5}',
    '{"info": {"name": "Bad", "album_bound": "abc"}}',
    '{"info": {"name": "Bad", "fields": "artist"}}',
    '{"info": {"name": "Bad", "numsources": "two"}}',
    '{"info": {"name": "Bad", "numsources": 1}, "config0": 5}',
    '{}',
])
def test_a_profile_file_puddletag_cannot_read_is_skipped(tmp_path, text):
    """tut5.txt, How to use it: "A profile whose file puddletag can't read
    isn't listed: the **Masstagging** window's log names the file instead."
    The other profiles still load."""
    (tmp_path / 'Broken.mtp').write_text(text)
    write_profiles(tmp_path, {'Good.mtp': profile('Good')})
    assert listed(tmp_path) == [('Good', '')]


@pytest.mark.xfail(strict=True, reason="saving a profile again writes an empty name "
                                       "for a tag source puddletag doesn't have")
def test_a_tag_source_puddletag_lacks_keeps_its_name_when_saved_again(tmp_path):
    """tut5.txt, Tag Sources: "A tag source puddletag doesn't have (one
    removed in an update, say) is listed with **(not found)** after its
    name. It's kept when the profile is saved, and searches skip it." OK in
    Configure Profiles saves every profile again, and the source keeps its
    name, so it's polled again once puddletag has it."""
    save_mtp(profile('Old', [source_profile('Gone Source'), source_profile('First Source')]),
             str(tmp_path / 'a.mtp'))
    loaded = mtp_from_file(str(tmp_path / 'a.mtp'), SOURCES)
    save_mtp(loaded, str(tmp_path / 'b.mtp'))
    with open(tmp_path / 'b.mtp') as f:
        data = json.load(f)
    assert [data['config0']['source'], data['config1']['source']] == ['Gone Source', 'First Source']


@pytest.mark.xfail(strict=True, reason='29, 57 and 58 percent are saved one lower')
def test_every_percentage_survives_a_save_and_a_load(tmp_path):
    """Synthetic expectation (tut5.txt says nothing on how profiles are
    kept): a percentage set in the profile editor comes back as it was,
    whatever its value. tut5.txt, Minimum percentage required for album
    matches: "An album will be considered a match if its **album name** and
    its **artist** both match the files' by at least the percentage specified
    here." Minimum percentage required for track match: "If a track has a
    **Match Percentage** higher or equal to this when compared to a file,
    then that track will be considered a match." """
    changed = []
    for n in range(101):
        path = str(tmp_path / f'{n}.mtp')
        save_mtp(profile('P', album_bound=n / 100.0, track_bound=n / 100.0), path)
        with open(path) as f:
            info = json.load(f)['info']
        loaded = mtp_from_file(path, SOURCES)
        if (info['album_bound'] != n or info['track_bound'] != n
                or loaded.album_bound != n / 100.0 or loaded.track_bound != n / 100.0):
            changed.append(n)
    assert changed == []
