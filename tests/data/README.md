# Public-domain fixtures

Real audio files whose tags other programs wrote, for
`tests/unit/test_real_files.py`. Each one is cut down to its tags, byte for
byte, plus the first 4096 bytes of its audio. `make_fixtures.py` downloads
the sources, checks them against the hashes their sites publish, and cuts
them.

| Fixture | Recording | Source | License | Tags written by |
|---|---|---|---|---|
| `musopen-canon.m4a` | Chopin, Canon in F minor; Aya Higuchi (Musopen, 2015) | [archive.org/details/musopen-chopin](https://archive.org/details/musopen-chopin), the original upload | CC0 1.0, uploaded by Musopen (aaron@musopen.org) | X Lossless Decoder 20140504 |
| `musopen-canon.mp3` | the same | the same item, archive.org's MP3 | CC0 1.0 | archive.org (ID3v2.3 and ID3v1; LAME 3.99.5) |
| `musopen-canon.ogg` | the same | the same item, archive.org's Ogg Vorbis | CC0 1.0 | archive.org |
| `musopen-goldberg-aria.flac` | Bach, Goldberg Variations, Aria; Shelley Katz (Musopen Kickstarter, 2012) | [archive.org/details/MusopenCollectionAsFlac](https://archive.org/details/MusopenCollectionAsFlac) | public domain: Musopen released its Kickstarter recordings into the public domain; this FLAC copy was encoded and tagged by the archive.org uploader | the uploader's tagger (libFLAC 1.2.1) |
| `marine-band-maple-leaf-rag.ogg` | Joplin, Maple Leaf Rag; United States Marine Band (1906) | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:1906_-_Scott_Joplin%27s_Maple_Leaf_Rag_(1899)_played_by_the_United_States_Marine_Band.ogg) | public domain: a US sound recording published before 1926, a work of the US Marine Corps, and a composition whose author died in 1917 | "Sony Ogg Vorbis 1.0 Final" |

How each format is cut:

- MP3: the ID3v2 tag, 4096 bytes of audio, and the 128-byte ID3v1 tag at the
  end.
- FLAC: the `fLaC` marker and every metadata block, then 4096 bytes of audio.
- Ogg: whole pages, up to and including the first page of audio.
- M4A: every atom before `mdat`, unchanged, then `mdat` with 4096 bytes of
  audio and its size field changed to match.

The MP3, FLAC and M4A files keep the length of the whole recording, which
those formats store in a header; an Ogg file's length comes from its last
page, so it's the length of the audio kept.

# Version 33 shortcuts and menus

`v33/shortcuts` and `v33/menus` are the default `shortcuts` and `menus` files
of puddletag 2.3.0, 2.4.0 and 2.5.0 (version 33), copied from `puddlestuff/data/`
of the source tree, without the spaces those files leave at the end of lines.
Every user of those releases has them in their config dir, and a newer
release has to replace them. `tests/ui/test_trash.py` writes them into the
config dir before the window is built, as an existing user's profile has
them, and checks that the File menu then offers Move to Trash.

# MusicBrainz responses

Responses MusicBrainz served, which `tests/unit/test_musicbrainz.py`
serves back from a local web server (the `web_server` fixture in
`tests/conftest.py`). `record_musicbrainz.py` requests them as puddletag
does and cuts them down; the tests never run it.

`musicbrainz/release-<id>.xml` is
`https://musicbrainz.org/ws/2/release/<id>?inc=recordings+artist-credits+labels+puids+isrcs+tags+ratings+artist-rels+recording-rels+release-rels+release-group-rels+url-rels+work-rels+recording-level-rels+work-level-rels`,
the request puddletag sends when a release is chosen in the Tag Sources
window:

| Release id | Release |
|---|---|
| `33eff102-8312-4be2-b3d9-5bd9957f0158` | A Putumayo Blend: Music From the Coffee Lands (Various Artists, 1997); MusicBrainz serves release `b8621ea1-acaf-46b5-b292-3a7c9eba9773`, which it was merged into |
| `6bb3793b-f991-378e-9bff-0bd3117f2298` | Abbey Road (The Beatles; the 1983 Japanese CD) |
| `70516629-7715-41bf-97e1-b7bf11254cb8` | Abbey's Road (Ada Montellanico feat. Giovanni Falzone, 2016) |
| `f0217095-5daf-4293-8f59-6ddec7187707` | 9 Symphonien (Beethoven; Herbert von Karajan, Berliner Philharmoniker; five CDs) |

`musicbrainz/search-abbey-road-the-beatles.xml` is
`https://musicbrainz.org/ws/2/release/?query=release:Abbey+Road%20AND%20artistname:The+Beatles&limit=2&offset=0`,
a search as puddletag sends it.

License: MusicBrainz releases its core data under
[CC0](https://musicbrainz.org/doc/About/Data_License); the rest
(annotations, genres, ratings, tags and search scores) is CC BY-NC-SA
3.0, so the script removes it, along with the Cover Art Archive's
artwork flags and the relationships puddletag doesn't read (to URLs and
works). Where a test needs a rating or a score, it adds a synthetic
one.
