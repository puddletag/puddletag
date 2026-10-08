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
