"""Mass Tagging's matching (tut5.txt, from "Minimum percentage required for
album matches" to "Fields to replace"): which search results match the
selected files' album, which retrieved track goes to which file, and how
several tag sources' tracks are combined. The functions are called the way
the Mass Tagging window's Search button calls them, on synthetic file tags
and synthetic albums shaped as a tag source returns them.
"""
import pytest

from puddlestuff.masstag import (DEFAULT_PATTERN, Result, TagSourceProfile, find_best,
                                 match_files, merge_tsp_tracks, split_files)
from puddlestuff.puddleobjects import ratio


class FileTags(dict):
    """A file's tags as Mass Tagging gets them: a dict that hashes by
    identity, as audioinfo's tags do."""
    __hash__ = object.__hash__


def file_tags(name, **tags):
    """A synthetic file /music/Album/<name> with these tags (lists of
    strings), on the album 'Album' unless the tags name another."""
    return FileTags({'__dirpath': '/music/Album', '__filename': name,
                     '__path': f'/music/Album/{name}', 'album': ['Album'], **tags})


def searched(files, pattern=DEFAULT_PATTERN):
    """The files as Search hands them to the matching: copies that carry the
    fields the pattern finds in the path where the file lacks them, each
    pointing back to its file. The files must share a folder and an album."""
    [group] = split_files(files, pattern)
    return group


def titles(matched):
    """{file name: title of the track the file got}"""
    return {f['__filename']: t['title'] for f, t in matched.items()}


def polled(tracks, fields=None, replace_fields=None, info=None):
    """A tag source's part of a profile once it has retrieved an album: its
    Fields and Fields to replace, and the album's synthetic tracks."""
    tsp = TagSourceProfile(fields=fields, replace_fields=replace_fields)
    tsp.result = Result({} if info is None else info, tracks)
    tsp.matched = [tsp.result]
    return tsp


def abbey_road_files():
    """Three synthetic files of Beatles' Abbey Road."""
    return [FileTags(artist=['Beatles'], album=['Abbey Road'], title=[f'Song {n}'])
            for n in (1, 2, 3)]


def three_tracks():
    """Three synthetic tracks, as many as abbey_road_files()."""
    return [{'title': [f'Track {n}']} for n in (1, 2, 3)]


def test_an_album_at_the_minimum_percentage_matches():
    """tut5.txt, Minimum percentage required for album matches: "An album
    will be considered a match if its **album name** and its **artist** both
    match the files' by at least the percentage specified here." Synthetic
    album 'Abbey Rd' for the files' 'Abbey Road'."""
    files = abbey_road_files()
    result = Result({'album': 'Abbey Rd', 'artist': 'Beatles'}, [])
    minimum = ratio('Abbey Road', 'Abbey Rd')

    assert find_best([result], files, minimum) == [result]
    # One step of the profile editor's percentage box.
    assert find_best([result], files, minimum + 0.01) == []


@pytest.mark.parametrize('artist, album', [('Beatlez', 'Abbey Road'),
                                           ('Beatles', 'Abbey Rd')])
def test_the_worse_of_artist_and_album_decides(artist, album):
    """tut5.txt, Minimum percentage required for album matches: "An album
    will be considered a match if its **album name** and its **artist** both
    match the files' by at least the percentage specified here." Synthetic
    albums that differ from the files' in one of the two."""
    files = abbey_road_files()
    result = Result({'album': album, 'artist': artist}, [])
    worse = min(ratio('Beatles', artist), ratio('Abbey Road', album))

    assert find_best([result], files, worse) == [result]
    # The average of the two fields, which would match if it decided.
    assert find_best([result], files, (worse + 1) / 2) == []


def test_an_album_with_as_many_tracks_as_files_matches_whatever_its_names():
    """tut5.txt, Minimum percentage required for album matches: "A search
    result that already has as many tracks as the files you selected is also
    considered a match, whatever its album name and artist." Synthetic album
    named nothing like the files'."""
    files = abbey_road_files()
    names = {'album': 'Other', 'artist': 'Other'}
    as_many = Result(names, three_tracks())
    too_few = Result(names, three_tracks()[:2])

    assert find_best([as_many], files) == [as_many]
    assert find_best([too_few], files) == []


def test_every_album_with_as_many_tracks_as_files_matches():
    """tut5.txt, Minimum percentage required for album matches: "A search
    result that already has as many tracks as the files you selected is also
    considered a match, whatever its album name and artist." Synthetic
    albums X, Y and Z, named nothing like the files'."""
    files = abbey_road_files()
    x, y, z = (Result({'album': name, 'artist': name}, three_tracks())
               for name in ('X', 'Y', 'Z'))

    assert find_best([x, y, z], files) == [x, y, z]


def test_albums_with_the_same_names_all_match():
    """tut5.txt, Minimum percentage required for album matches: "An album
    will be considered a match if its **album name** and its **artist** both
    match the files' by at least the percentage specified here." Synthetic
    albums that all have the files' names, told apart by the field 'n'."""
    files = abbey_road_files()
    a, b, c = (Result({'album': 'Abbey Road', 'artist': 'Beatles', 'n': n}, [])
               for n in (1, 2, 3))

    assert find_best([a, b, c], files) == [a, b, c]


def test_a_name_match_ranks_before_a_track_count_match():
    """Synthetic: an album named nothing like the files' but with as many
    tracks, given first by the source, and one with the files' names, or
    with names that match at exactly the minimum."""
    files = abbey_road_files()
    count_only = Result({'album': 'X', 'artist': 'X'}, three_tracks())
    good = Result({'album': 'Abbey Road', 'artist': 'Beatles'}, [])
    at_minimum = Result({'album': 'Abbey Rd', 'artist': 'Beatles'}, [])

    assert find_best([count_only, good], files) == [good, count_only]
    minimum = ratio('Abbey Road', 'Abbey Rd')
    assert find_best([count_only, at_minimum], files, minimum) == [at_minimum, count_only]


def test_several_artists_are_compared_as_various_artists(_translated_strings):
    """Synthetic: two files by different artists on the album 'Hits', and a
    result by 'Various Artists', the name the app has once its translations
    load."""
    files = [FileTags(artist=[artist], album=['Hits'], title=[f'Song {n}'])
             for n, artist in enumerate(('Artist One', 'Artist Two'), 1)]
    result = Result({'album': 'Hits', 'artist': 'Various Artists'}, [])

    assert find_best([result], files) == [result]


def test_tracks_match_on_artist_and_title_by_default():
    """tut5.txt (Match tracks using fields): "If no fields are listed,
    **artist** and **title** are used." With no fields given, a file matches
    the track that has its artist and title and none that has another
    artist (synthetic)."""
    same = file_tags('same.mp3', artist=['Artist'], title=['Come Together'])
    other = file_tags('other.mp3', artist=['Someone Else'], title=['Come Together'])
    tracks = [{'artist': ['Artist'], 'title': ['Come Together']}]

    matched = match_files(searched([same, other]), tracks, 0.8, None)

    assert titles(matched) == {'same.mp3': ['Come Together']}


def test_the_field_with_the_lowest_percentage_decides():
    """tut5.txt: "each field will be compared in the file vs each track and
    the field with the **lowest** match percentage will be used to assess
    the track match the file." The artist is the same, the title matches by
    0.5: no match at 0.7 although the average is 0.75 (synthetic)."""
    song = file_tags('song.mp3', artist=['Same Artist'], title=['abcdefghij'])
    tracks = [{'artist': ['Same Artist'], 'title': ['abcdexxxxx']}]

    assert match_files(searched([song]), tracks, 0.7, ['artist', 'title']) == {}


def test_a_track_at_the_minimum_percentage_matches():
    """tut5.txt: "If a track has a **Match Percentage** higher or equal to
    this when compared to a file, then that track will be considered a
    match." Synthetic titles."""
    percentage = ratio('Abbey Road', 'Abbey Rd')
    keys = ['artist', 'title']

    def matching(minimum):
        song = file_tags('song.mp3', artist=['Artist'], title=['Abbey Road'])
        tracks = [{'artist': ['Artist'], 'title': ['Abbey Rd']}]
        return match_files(searched([song]), tracks, minimum, keys)

    assert len(matching(percentage)) == 1
    assert matching(percentage + 0.01) == {}


@pytest.mark.parametrize('order', [(0, 1), (1, 0)])
def test_two_similar_titles_each_get_their_own_track(order):
    """tut5.txt: "puddletag will compare all retrieved tracks against the
    files and choose the one with the highest **Matching Percentage** as a
    match". 'Love Me Do' and 'Love Me Doo' are close enough to match each
    other at 0.7, yet each file gets the track of its own title, whatever
    the order of the files (synthetic)."""
    names = ['Love Me Do', 'Love Me Doo']
    files = [file_tags(f'{names[n]}.mp3', title=[names[n]]) for n in order]
    tracks = [{'title': [name]} for name in names]

    matched = match_files(searched(files), tracks, 0.7, ['title'])

    assert {f['__filename']: t['title'] for f, t in matched.items()} == {
        'Love Me Do.mp3': ['Love Me Do'], 'Love Me Doo.mp3': ['Love Me Doo']}


@pytest.mark.parametrize('order', [(0, 1), (1, 0)])
def test_a_track_two_files_want_goes_to_the_closer_file(order):
    """Two files whose titles are close enough to the one retrieved track
    both want it: the file with the title closest to the track's gets it and
    the other gets nothing (synthetic)."""
    names = ['Love Me Do', 'Love Me Doo']
    files = [file_tags(f'{names[n]}.mp3', title=[names[n]]) for n in order]
    tracks = [{'title': ['Love Me Do']}]

    matched = match_files(searched(files), tracks, 0.7, ['title'])

    assert [f['__filename'] for f in matched] == ['Love Me Do.mp3']


def test_track_is_ignored_beside_other_fields():
    """tut5.txt (Match tracks using fields): "**track** is used only when
    it's the only field listed: beside other fields, it's ignored." The
    track numbers differ and the files still match on the title
    (synthetic)."""
    song = file_tags('song.mp3', title=['Song'], track=['1'])
    tracks = [{'title': ['Song'], 'track': ['9']}]

    matched = match_files(searched([song]), tracks, 0.7, ['title', 'track'])

    assert titles(matched) == {'song.mp3': ['Song']}


def test_update_empty_fields_only():
    """tut5.txt: "If checked, only fields that don't already have values
    will be updated with retrieved data." The file's artist, title and genre
    stay; the album it lacks is filled (synthetic)."""
    song = file_tags('song.mp3', artist=['Artist'], genre=['Rock'], title=['Song'])
    del song['album']
    tracks = [{'album': ['Album X'], 'artist': ['Artist'], 'genre': ['Jazz'],
               'title': ['Song']}]

    matched = match_files(searched([song]), tracks, 0.7, None, existing=True)

    assert matched == {song: {'album': ['Album X']}}


def test_update_empty_fields_only_fills_a_field_the_pattern_found():
    """tut5.txt: "Pattern to match filenames against" gives values that
    steer the lookup only, and "Update empty fields only" updates "fields
    that don't already have values": a title the pattern found in the file
    name is not in the file, so the track's fills it (synthetic)."""
    song = file_tags('Song.mp3', artist=['Artist'])
    tracks = [{'artist': ['Artist'], 'title': ['Song']}]

    matched = match_files(searched([song], '%title%'), tracks, 0.7, None,
                          existing=True)

    assert matched == {song: {'title': ['Song']}}


def test_an_empty_match_fields_box_matches_on_artist_and_title():
    """tut5.txt (Match tracks using fields): "If no fields are listed,
    **artist** and **title** are used." A box emptied by the user is saved as
    the one field '': the outcome is the one with no fields given
    (synthetic)."""
    same = file_tags('same.mp3', artist=['Artist'], title=['Come Together'])
    other = file_tags('other.mp3', artist=['Someone Else'], title=['Come Together'])
    tracks = [{'artist': ['Artist'], 'title': ['Come Together']}]

    matched = match_files(searched([same, other]), tracks, 0.8, [''])

    assert titles(matched) == {'same.mp3': ['Come Together']}


def test_a_track_without_a_match_field_matches_no_file():
    """tut5.txt: "Check if all the fields listed are present in the
    retrieved track." A track without a title is not checked against a file
    titled 'B' (synthetic)."""
    song = file_tags('song.mp3', artist=['x'], title=['B'])
    tracks = [{'artist': ['x']}]

    assert match_files(searched([song]), tracks, 0.7, ['artist', 'title']) == {}


def test_a_file_without_a_match_field_matches_no_track():
    """A file without a title is not compared with a track titled 'A': the
    field can't be compared, so no track matches (synthetic)."""
    song = file_tags('song.mp3', artist=['x'])
    tracks = [{'artist': ['x'], 'title': ['A']}]

    assert match_files(searched([song]), tracks, 0.7, ['artist', 'title']) == {}


def test_the_track_whose_lowest_field_is_highest_wins():
    """tut5.txt: "the field with the **lowest** match percentage will be used
    to assess the track match the file", and puddletag will "choose the one
    with the highest **Matching Percentage**". Track A's fields match by 0.8
    and 0.875, track B's by 1.0 and 0.75: A's lowest is higher, though B's
    sum is (synthetic)."""
    song = file_tags('song.mp3', artist=['aaaaa'], title=['bbbbbbbb'])
    tracks = [{'artist': ['aaaax'], 'title': ['bbbbbbbx']},
              {'artist': ['aaaaa'], 'title': ['bbbbbbxx']}]

    matched = match_files(searched([song]), tracks, 0.7, ['artist', 'title'])

    assert titles(matched) == {'song.mp3': ['bbbbbbbx']}


def brute_forced(files, tracks, pattern=DEFAULT_PATTERN, **kwargs):
    """The titles Search gives the files with default keys and minimum 0.8,
    brute force on unless the test turns it off."""
    kwargs.setdefault('jfdi', True)
    return titles(match_files(searched(files, pattern), tracks, 0.8, **kwargs))


def two_discs(per_disc):
    """Synthetic tracks of a two-disc album, `per_disc` tracks each."""
    return [{'artist': ['Artist'], 'discnumber': [str(disc)],
             'title': [f'Disc {disc} Track {n}'], 'track': [str(n)]}
            for disc in (1, 2) for n in range(1, per_disc + 1)]


def track_files(count):
    """Synthetic files 01.mp3, 02.mp3, ... numbered straight through."""
    return [file_tags(f'{n:02}.mp3', artist=['Artist'], track=[str(n)])
            for n in range(1, count + 1)]


def unlike_files():
    """Synthetic files that match no track on their own."""
    return [file_tags('p.mp3', artist=['Artist'], title=['Track02'], track=['2']),
            file_tags('q.mp3', artist=['Artist'], title=['Track01'], track=['1'])]


def unlike_tracks():
    """Synthetic tracks that match none of unlike_files' files on their own."""
    return [{'artist': ['Artist'], 'title': ['Come Together'], 'track': ['1']},
            {'artist': ['Artist'], 'title': ['Something'], 'track': ['2']}]


def test_brute_force_pairs_unmatched_files_by_track():
    """tut5.txt, Brute force unmatched files: "If no matches were found for
    some files, then the files will be sorted by **discnumber**, then
    **track** (if they're not present, **__filename**), as found in the tag
    used to poll Tag Sources. The retrieved data will also be sorted using
    **discnumber**, then **track**. Each retrieved track will then be paired
    with a file (in order) provided that file hasn't been matched
    previously." Synthetic."""
    assert brute_forced(unlike_files(), unlike_tracks()) == {
        'p.mp3': ['Something'], 'q.mp3': ['Come Together']}


def test_brute_force_falls_back_to_the_file_name():
    """tut5.txt, Brute force unmatched files: "the files will be sorted by
    **discnumber**, then **track** (if they're not present, **__filename**)".
    Synthetic."""
    files = [file_tags('b.mp3', artist=['Artist']), file_tags('a.mp3', artist=['Artist'])]
    assert brute_forced(files, unlike_tracks()) == {
        'a.mp3': ['Come Together'], 'b.mp3': ['Something']}


def test_brute_force_pairs_only_the_files_left_unmatched():
    """tut5.txt, Brute force unmatched files: "Each retrieved track will then
    be paired with a file (in order) provided that file hasn't been matched
    previously." Synthetic."""
    files = [file_tags(f'{name}.mp3', artist=['Artist'], title=[title])
             for name, title in (('01', 'Track01'), ('02', 'Something'), ('03', 'Track03'))]
    tracks = [{'artist': ['Artist'], 'title': [title], 'track': [str(n)]}
              for n, title in enumerate(('Come Together', 'Something', 'Maxwell'), 1)]
    assert brute_forced(files, tracks) == {
        '01.mp3': ['Come Together'], '02.mp3': ['Something'], '03.mp3': ['Maxwell']}


def test_without_brute_force_unmatched_files_get_nothing():
    """tut5.txt, Brute force unmatched files: "Check to enable brute force
    matching." Synthetic."""
    assert brute_forced(unlike_files(), unlike_tracks(), jfdi=False) == {}


def test_brute_force_uses_the_track_number_the_pattern_found():
    """tut5.txt, Pattern to match filenames against: "The tag used to poll Tag
    Sources will then be **artist=Bongo Maffin, album=Bonglut, genre=Kwaito,
    track=02, title=Way Kungakhona**." The files carry their track number
    only in their names. Synthetic."""
    files = [file_tags('b - 1.mp3', artist=['Artist']), file_tags('a - 2.mp3', artist=['Artist'])]
    assert brute_forced(files, unlike_tracks(), '%title% - %track%') == {
        'a - 2.mp3': ['Something'], 'b - 1.mp3': ['Come Together']}


def test_brute_force_keeps_a_two_disc_album_in_order():
    """tut5.txt, Brute force unmatched files: "The retrieved data will also be
    sorted using **discnumber**, then **track**." Three files for a
    four-track album. Synthetic."""
    files = [file_tags(f'{n}.mp3', artist=['Artist']) for n in (1, 2, 3)]
    assert brute_forced(files, two_discs(2)) == {
        '1.mp3': ['Disc 1 Track 1'], '2.mp3': ['Disc 1 Track 2'], '3.mp3': ['Disc 2 Track 1']}


def test_matching_by_track_renumbers_a_two_disc_album():
    """tut5.txt, Match tracks using fields: "If **track** is the only field
    listed, the album has several discs and there are as many files as
    retrieved tracks, files numbered straight through the album are
    renumbered disc by disc before they're compared: with two discs of two
    tracks each, file 3 is compared with disc 2's track 1." Synthetic."""
    assert brute_forced(track_files(4), two_discs(2), keys=['track'], jfdi=False) == {
        '01.mp3': ['Disc 1 Track 1'], '02.mp3': ['Disc 1 Track 2'],
        '03.mp3': ['Disc 2 Track 1'], '04.mp3': ['Disc 2 Track 2']}


def test_matching_by_track_renumbers_discs_of_more_than_nine_files():
    """tut5.txt, Match tracks using fields: "files numbered straight through
    the album are renumbered disc by disc before they're compared". Two discs
    of six tracks: file 7 is compared with disc 2's track 1. Synthetic."""
    assert brute_forced(track_files(12), two_discs(6), keys=['track'], jfdi=False) == (
        {f'{n:02}.mp3': [f'Disc 1 Track {n}'] for n in range(1, 7)}
        | {f'{n + 6:02}.mp3': [f'Disc 2 Track {n}'] for n in range(1, 7)})


def test_fields_cut_the_retrieved_tracks():
    """tut5.txt, Fields: "The retrieved tracks are cut to these fields before
    they're matched against the files. If the match fields aren't among them,
    no track will match a file, and the tracks can only be paired by brute
    force." Synthetic tracks and files."""
    def tracks():
        return [{'artist': ['Artist'], 'genre': ['Rock'], 'title': [f'Song {n}']}
                for n in (1, 2)]

    def files():
        return [file_tags(f'0{n}.mp3', artist=['Artist'], title=[f'Song {n}'])
                for n in (1, 2)]

    cut = merge_tsp_tracks([polled(tracks(), fields=['genre'])])
    assert [dict(t) for t in cut] == [{'genre': ['Rock']}] * 2
    assert match_files(searched(files()), cut, 0.8, None, jfdi=False) == {}

    paired = match_files(searched(files()), cut, 0.8, None, jfdi=True)
    assert [dict(t) for t in paired.values()] == [{'genre': ['Rock']}] * 2


def test_fields_with_a_tilde_leave_those_out():
    """tut4.txt, Deciding what to retrieve: "if you entered ~genre,album and
    the Tag Source returned a tag with artist, title, album, track, genre
    fields. Only the artist, title, track fields would be written to the
    files." Synthetic track."""
    track = {'album': ['Album X'], 'artist': ['Artist'], 'genre': ['Rock'],
             'title': ['Song'], 'track': ['1']}
    [cut] = merge_tsp_tracks([polled([track], fields=['~genre', 'album'])])
    assert set(cut) == {'artist', 'title', 'track'}


def test_an_empty_fields_box_keeps_every_field():
    """tut4.txt, Deciding what to retrieve: "Leave it empty and all metadata
    from the Tag Source will be retrieved." Synthetic track and album."""
    track = {'artist': ['Artist'], 'title': ['Song'], 'track': ['1']}
    [cut] = merge_tsp_tracks([polled([track], fields=[], info={'album': ['Album X']})])
    assert dict(cut) == {'album': ['Album X'], 'artist': ['Artist'],
                         'title': ['Song'], 'track': ['1']}


def freedb():
    """tut5.txt's FreeDB: "artist=TKZee, title=Felakai, genre=Dance"."""
    return polled([{'artist': ['TKZee'], 'genre': ['Dance'], 'title': ['Felakai']}])


def discogs():
    """tut5.txt's Discogs: "artist=TKZee, title=Felakai, genre=Kwaito\\Rap"."""
    return polled([{'artist': ['TKZee'], 'genre': ['Kwaito', 'Rap'],
                    'title': ['Felakai']}])


def test_several_sources_combine_the_last_polled_first():
    """tut5.txt, Fields: "Since Discogs was polled last it's values will be
    listed first, giving the final tag. artist=TKZee, title=Felakai,
    genre=Kwaito\\Rap\\Dance". Synthetic tracks, as the docs give them."""
    [merged] = merge_tsp_tracks([freedb(), discogs()])
    assert dict(merged) == {'artist': ['TKZee'], 'genre': ['Kwaito', 'Rap', 'Dance'],
                            'title': ['Felakai']}


def test_fields_to_replace_take_that_sources_value():
    """tut5.txt, Fields to replace: "Instead of the artist field being
    combined in the final tag to TKZ\\TKZee, only the value from MusicBrainz
    will be used. ... artist=TKZ, title=Felakai, genre=Kwaito\\Rap\\Dance".
    Synthetic tracks, as the docs give them."""
    musicbrainz = polled([{'artist': ['TKZ'], 'title': ['Felakai']}],
                         replace_fields=['artist'])
    [merged] = merge_tsp_tracks([freedb(), discogs(), musicbrainz])
    assert dict(merged) == {'artist': ['TKZ'], 'genre': ['Kwaito', 'Rap', 'Dance'],
                            'title': ['Felakai']}


def test_the_last_source_replacing_a_field_wins():
    """tut5.txt, Fields to replace: "If a later tag source replaces the same
    fields as any previous tag source, that tag source's field will be used."
    Synthetic tracks."""
    family = polled([{'artist': ['TKZee Family'], 'title': ['Felakai']}],
                    replace_fields=['artist'])
    musicbrainz = polled([{'artist': ['TKZ'], 'title': ['Felakai']}],
                         replace_fields=['artist'])
    [merged] = merge_tsp_tracks([freedb(), family, musicbrainz])
    assert merged['artist'] == ['TKZ']


def test_combined_tracks_reach_the_files():
    """tut5.txt, Fields: "Fields from different tag sources will be combined
    into multiple values where they differ." The combined track is matched
    to the file like any retrieved track. Synthetic file and tracks."""
    merged = merge_tsp_tracks([freedb(), discogs()])
    file = file_tags('Felakai.mp3', artist=['TKZee'], title=['Felakai'])
    matched = match_files(searched([file]), merged, 0.8, None)
    assert {f: t['genre'] for f, t in matched.items()} == {file: ['Kwaito', 'Rap', 'Dance']}
