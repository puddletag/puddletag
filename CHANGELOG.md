<!--
This file follows Keep a Changelog 1.1.0:
https://keepachangelog.com/en/1.1.0/
Newest release first. New lines go under [Unreleased], in Added,
Changed, Deprecated, Removed, Fixed or Security; CONTRIBUTING.md
("Changelog") says what gets a line.
-->
# Changelog

All notable changes to puddletag, newest first. GitHub's
[releases feed](https://github.com/puddletag/puddletag/releases.atom)
announces each new release.

## [Unreleased]

### Added

- File → Remove from List (also in the right-click menu, with no key)
  takes the selected files out of the list without asking and leaves
  them as they are on disk; their edits drop out of the undo history
  (#1091, #804).
- File→Tag patterns can contain functions (#210). A function matches
  any text; one with a single field sets that field, so the default
  pattern `%artist% - $num(%track%,2) - %title%` now works for File→Tag
  too (`track=01`). Before, any pattern with a function matched
  nothing. Applies to the "Filename to Tag" action, mass tagging and
  Text File→Tag as well.
- An error puddletag doesn't handle no longer closes it without a word:
  it shows the error in a message (the full traceback under Show
  Details), writes it to the log, and keeps running. The message's
  Report a problem button, like Help > Report a problem, opens a report
  to review and edit before it goes to GitHub, filled in with the
  system, the error and the last 20 steps taken in puddletag, with the
  home folder, user and computer names, email addresses and tag-source
  keys left out.
- The ID3 GRP1 frame (Mp3tag's GROUPING, iTunes' grouping) shows as the
  new field itunesgrouping; grouping is still TIT1 (#1056).
- Load artwork takes absolute paths and paths relative to the file's
  folder (`../covers/*.jpg`), and loads the images in the order the list
  names them, each wildcard's matches by name (#312).
- Number arguments of scripting functions read fields, so
  `$sub(%track%,1)` and `$num(%track%,%n%)` work (#612).
- `__filename_no_ext` can be written: Format into it, or typing into
  its cell, renames the file and keeps its extension.
- MusicBrainz also returns `albumartist` (#836), each track's
  `discnumber` and ISRC (`isrc`, #134), and `label`, `catalognumber`
  and `mbrainz_label_id` when a release is chosen (#307, #729).

### Changed

- Delete is now Move to Trash (Del, the File menu and the right-click
  menu): the selected files go to the trash, where your file manager
  can restore them, instead of being deleted permanently (#223, #1105;
  started by WatDuhHekBro in #801). The question before it is asked
  again, even if you had turned it off. This update resets customized
  shortcuts and menus to the defaults. puddletag now needs Send2Trash
  (`python3-send2trash` on Debian and Ubuntu).
- A Replace (or a function) whose result holds the value separator
  writes several values: " & " replaced with the separator in "Brandi
  Carlile & Dylan LeBlanc" gives two artists (#873).
- M4A files show their fields under the names other formats use:
  `discnumber`, `performersortorder`, `itunescomposersortorder`,
  `itunescompilationflag`, `unsyncedlyrics` (before: `disc`,
  `artistsortorder`, `composersortorder`, `partofcompilation`,
  `lyrics`, which still write). M4A's flags (compilation, gapless,
  podcast) read `1` or `0` instead of `Yes` or `No`, as in Picard and
  Mp3tag, and `0` now turns one off (it turned it on). Patterns that
  read the old names, or compare M4A flags with `Yes`, need updating.
- Monkey's Audio, Musepack and WavPack files show `discnumber` and
  `albumartist` (before, in puddletag: `disc` and `album artist`);
  they're saved under the file's own key, or as Disc and Album Artist.
  Patterns reading `%disc%` or `%album artist%` from these files need
  the new names; writing the old names still works. If you mapped
  APEv2's disc or album artist yourself (Preferences → Mappings),
  remove those mappings.
- Nine WMA fields take the names MP3 uses (setsubtitle,
  encodingsettings, organization, filename, author, arranger, version,
  wwwsource) or Picard's (producer); the old names still write, but
  patterns that read them need updating.
- MusicBrainz gives a track the title, length and artist the release
  gives it, as Picard does; before, they were its recording's, so a
  German release came back with English titles (#760). Re-tagging such
  a release changes those fields.
- Discogs genres and styles come as `genre` and `style`, the names the
  docs give (#522), so the Genre column is filled; actions that read
  `genres` or `styles` need the new names.
- AcoustID's `acoustid_id` now holds AcoustID's own id, as the docs say
  and as Picard writes it, and the MusicBrainz recording id goes to
  `mbrainz_track_id`; files already tagged keep the old value.
- puddletag now needs Python 3.14 or newer; pip no longer installs it
  on Python 3.13.
- Open Folder and Add Folder use the desktop's own folder dialog, which
  lists mounted drives and, in the Flatpak, can open folders outside
  Downloads (#1088, #1089).
- Playlists are read and written in UTF-8 on every system. On Windows,
  a playlist saved by an older puddletag with accented names in it no
  longer loads: save it again.
- `__md5sig` shows a FLAC file's MD5 signature as 32 hexadecimal
  digits, as metaflac does, not as a 39-digit decimal number; patterns
  that read it give a different result.

### Removed

- The Amazon and AllMusic tag sources are removed: Amazon's API is gone
  and AllMusic blocks programs. If you entered your own AWS keys in
  Amazon's settings, they are still in
  `~/.config/puddletag/tagsources.conf`, in plain text: delete its
  `Amazon` section. A Mass Tagging profile that uses one skips it, with
  a line in the Mass Tagging log, and polls its other sources.
- The duplicate finder's code (`puddlestuff/duplicates/`) is removed:
  no menu has opened it since 2010. The older `functions.finddups` and
  `puddleobjects.dupes` went with it, so a plugin that used any of them
  needs its own copy.

### Fixed

- In Tag→File and Rename Directories, a `/` written inside a function
  makes a folder too, so `$if(%album%,%album%/,)%title%` adds an album
  folder only when the file has an album; it used to give
  `AlbumSong.mp3` (#475). A `/` in a field's value is still dropped
  (AC/DC gives ACDC).
- Tag→File no longer makes a folder named `""` when part of the pattern
  comes out empty:
  `/music/%album%/$if(%discnumber%,Disc %discnumber%,)/%title%` puts a
  file without a disc number in `/music/Album/`, not `/music/Album/""/`
  (discussion #1028). Running Tag→File again moves files out of
  existing `""` folders. Tag→Dir and Rename Directories do the same
  when the pattern's last folder comes out empty. A relative pattern
  (not starting with `/`) moves a file up one folder per folder it
  makes, no longer per slash, so such a file stays in its album folder
  instead of leaving the library folder above it.
- Format no longer moves folders (#636). With every cell selected
  (Ctrl+A), it wrote the pattern into the Dirpath cell too, so a
  pattern like `%track% - %title%` moved the music folder into the
  working folder (the home folder or the drive's root). Format now
  leaves the folder cells alone; a selected Filename cell still renames
  the file, without an extension.
- Saved patterns and actions can give a different result after these
  fixes: `$meta_sep(artist," & ")` gives `A & B`, not `A" & "B`;
  `$to_ascii` leaves no stray spaces after Chinese/Japanese characters
  (`藏經` gives `Cang Jing`, not `Cang Jing `, so files named with
  those spaces get new names if Tag→File is run again); `$regex` and
  Replace with RegExp insert a group's text as it is, without `\` before
  commas (#941, #241); a backslash before a quoted argument's closing
  quote is kept (`$upper("a\")` gives `A\`, not `A"`); Replace with
  "only as whole word" ticked, and `$replace`, replace every whole word
  ("song song" becomes "tune tune", not "tune song"); `$regex(text,
  regex)` with two arguments removes the matches, where it closed
  puddletag (#559).
- `__bitrate` is in whole kb/s again, as before the Python 3 port and
  as the docs say: `320 kb/s`, not `320.0 kb/s`; a VBR file shows
  `51 kb/s`, not `51.3 kb/s`. Patterns and filters that match the
  decimals give a different result.
- Saving a FLAC, Ogg, Opus, Monkey's Audio, Musepack or WavPack file
  keeps each tag name's case, so players that don't ignore case (MPD
  with `R128_TRACK_GAIN`, #419) still find them; new names are saved as
  `TITLE` (Vorbis) or `Title` (APEv2). Before, every name was rewritten
  in lower case.
- Saving a WMA file no longer deletes the attributes puddletag doesn't
  show (store and player attributes like WM/Provider, ratings,
  Picard's compilation flag); before, every save removed them. WMA's
  comment shows as `comment` and can be written (before: `comment:`,
  and writing was ignored); fields of your own are saved.
- Saving a Monkey's Audio, Musepack or WavPack file no longer deletes
  the pictures puddletag doesn't show, like foobar2000's Artist Picture
  and Cover Art (Disc) or Mp3tag's Cover Art (Artist); since 2.3.0,
  every save removed them.
- An MP4 track written as `3/12` sets track and totaltracks (`1/2` does
  the same for the disc); before, the track number was deleted.
- Tag Tools → Remove ID3v1 Tag, Remove ID3v2 Tag and Remove All ID3
  Tags no longer delete the APEv2 tag of Monkey's Audio, Musepack and
  WavPack files; before (since 1.0.0), they removed every field and
  cover of those files. After removing an MP3's ID3v2 tag, the table
  shows what the file still holds; before, the next edit to the file
  saved the removed fields back.
- Convert from non-standard encoding leaves a value unchanged when it
  has a character beyond Latin-1, such as text already in Cyrillic,
  Greek or CJK. Before (since 2010), it turned those characters into
  `?`, so running it on a selection where only some files needed it
  destroyed the others' text.
- Rolling the mouse wheel over a Tag Panel field no longer changes its
  value unless the field was clicked first; before, one notch could
  turn a value into `<blank>`, which Save then deleted (#1094).
- Renaming a field in Extended Tags for files whose values differ keeps
  each file's value under the new name; before, every file lost it
  (#466). In a translated puddletag, editing a field there for files
  whose covers differ no longer deletes all their covers (#656).
- In the Artwork window, changing the description or type of a cover
  the file already has is saved (#209), and Change cover keeps them.
  Save cover to file, Copy and Paste keep a cover's bytes and type;
  before, Paste turned every cover into a JPEG (#457, #1042).
- An unexpected error while saving a file, from mutagen or a format
  module (such as a FLAC cover over 16 MB, #937), is now reported like a
  file that can't be written, and puddletag keeps running; with several
  files, you can choose to go on with the others. Before, puddletag
  closed (#989, #1060, #1066, #1086 report such crashes). MP4 files
  with a number atom puddletag has no field for (season and episode
  numbers, as yt-dlp's files carry, #1066) and ID3 files with a
  `TXXX:YEAR` frame (#989) can be saved again.
- Undo no longer closes puddletag when the last edit included a file
  that has since left the table (one the Filter hides, reloaded,
  deleted, or after Unload Everything). A function whose arguments
  don't parse, such as an invalid regular expression in Replace with
  RegExp, shows the error and changes nothing; before, it closed
  puddletag, in Preview Mode too (#576).
- In the Filter panel: `NOT word` and an invalid `MATCHES` expression
  no longer crash; `albumartist has "Various"` works on profiles whose
  tag list lacks albumartist (#1026); a quoted search like `"Bongo
  Maffin"` now finds files containing the text (before, it found
  nothing); words with letters outside A-Z work without quotes (before,
  `artist IS Björk` showed nothing, #463).
- DSDIFF (`.dff`) files open; before, every one failed with "DSF dsd
  header not found". An Opus file named `.ogg` (as Opus encoders also
  write) loads; before, it was skipped with an error in the log.
  Musepack (`.mpc`) files show their length, bitrate, frequency,
  channels and mode; before (since 2011), every one showed `00:00` and
  `0 kb/s`.
- The main window no longer grows taller than the screen. On a fresh
  profile, Tag Sources and Mass Tagging share their place as tabs, and
  so do Functions and Actions (#768; saved layouts are kept); the Tag
  Panel scrolls when it has more rows than fit (#1092, #1097); an
  action's preview in the Actions dock stops at 10 lines and scrolls
  (#467, #608, #1059).
- Plugins in the user's plugin folder load again (#639).
- puddletag starts again when the `EMAIL` environment variable isn't a
  single address (`EMAIL=joe`, or set empty), and as root without
  `USER` set (in a container, say).
- Discogs returns the movements under an index track as tracks of their
  own (#725), a two-disc release's position "2-5" gives `discnumber` 2
  and `track` 5, and covers are retrieved again.
- Searching and retrieving with Mp3tag scripts works again; every
  search failed, because the downloaded page reached the parser as
  bytes. Searching the selected files searches every selected album,
  once each, by all the fields the script's `[SearchBy]` names.
  Scripts' track lists come out as Mp3tag's do (the last track no
  longer twice, the album's fields no longer in the first track), and a
  script stops where a FindLine finds nothing instead of reading on
  into nonsense. A script using a command puddletag doesn't have is no
  longer loaded: the Tag Sources window names the command and its line.
- FreeDB lookups find the album again instead of unrelated ones (#872):
  puddletag sends the CD's real disc ID, computed from each file's
  exact length, and lists gnudb's exact matches, which it used to drop.
  Lossless rips of a whole CD match exactly; other files may still get
  gnudb's guesses.
- Mass Tagging no longer deletes the files' track and disc numbers when
  the tag source returned none. An error in a tag source no longer
  closes puddletag: it's shown in the window's log, and the next album
  goes on (#483, #520).
- Mass Tagging keeps every search result that matches the files' album;
  of several with as many tracks as the files, only the last was kept.
  Track matching follows the docs, so some files may get a different
  track than before, and a two-disc album is paired in disc, then track
  order; it was interleaved.
- AcoustID's `acoustid_fingerprint` is written as one value, not one
  per byte. A match whose title isn't on the release gets its own row;
  it used to take over the last track, and the file was tagged as that
  track.
- AcoustID's Submit Tags works again: a file without a stored
  fingerprint stopped the submit with an error. A refused submit or a
  lost connection now shows in the window and stops it, where it used
  to say the submit completed, and "No files were submitted." shows
  when nothing went. Track, disc and year go as plain numbers. A search
  or submit reads the fingerprint Picard stores in an MP3 instead of
  calculating it again.
- A broken plugin (an info file puddletag can't read, a comma in its
  name, a tag source that fails to start) no longer stops puddletag
  from starting: it's left out and the reason logged, and a failed tag
  source is named in the Tag Sources window. The docs' example tag
  source plugin works again, and the docs name the right plugin folder.
- The Modtime + 2sec plugin on one selected file no longer crashes
  (#619), and an error while files are written no longer leaves the
  progress window open.
- Undo of a file that can't be written (a read-only file) no longer
  closes puddletag: it says so as any write does, goes on with the
  other files, and keeps the file in the undo history to undo once it
  can be written.
- The sort order picked with Tools > Sort By or a header click is used
  again after a restart, as the docs promise (#243, #558).
- A shortcut cleared in Preferences > Shortcuts stays cleared after a
  restart instead of coming back (#255); that was also how Play and
  Preferences ended up sharing Ctrl+P (#1090).
- A key typed in Preferences > Shortcuts that another command holds now
  moves to the new command, and a line under the table says so, instead
  of the two commands' keys being swapped silently (#387). A command's
  second key (Paste's Shift+Ins) is kept, and clearing a key, giving it
  away and then taking a held one no longer brings puddletag down.
- Replace with RegExp no longer joins the values of a multi-valued
  field into one, even when nothing matched: each value is replaced on
  its own (#642).
- A plugin's function can be run from the Functions window again: OK
  raised an error and wrote nothing.
- Edit Action keeps its size and maximized state after Cancel, and
  every window that remembers its size now does so after Esc too
  (#379).
- Saving no longer deletes or changes what puddletag doesn't show: ID3
  chapters (CHAP, CTOC), PRIV, GEOB and SYLT frames, a UFID that isn't
  UTF-8 and a second comment that differs only by language, MP4
  freeform atoms that aren't text, hold a number, or share a name (also
  one that differs only by case, or matches a field puddletag shows),
  MP4 GIF and BMP covers, and a FLAC file's picture comment. FLAC, Ogg
  Vorbis and Opus files keep their comments' order, so an Opus file's
  chapter titles survive an edit (#611, #1072).
- Saving as ID3v2.3 no longer deletes musiciancredits when
  involvedpeople is set: ID3v2.3 has one frame for both, so they're
  saved together and read back as involvedpeople. AIFF, DSF and DSDIFF
  files saved as ID3v2.3 keep their sort fields (albumsortorder,
  performersortorder, titlesortorder, setsubtitle), as MP3s do.
- Writing `__total` to a file that has no track number no longer fails
  with an error on FLAC, Ogg, Opus, APEv2 and ID3 files; nothing is
  written, as on WMA, and MP4 no longer shows track 0.
- `%__total%` in patterns (Format, Tag to Filename, actions) now gives
  the track total, as the docs say; it was always empty, so a Format
  that wrote it emptied the field.
- `$geql`, `$grtr`, `$leql` and `$less` no longer crash when comparing
  a number with text (`$less(abc,5)`, or an empty field against a
  number): both are compared as numbers when both are numbers, else as
  text. `$grtr` no longer counts an empty value as 0, so `$grtr(,-1)`
  is now false. `$div`, `$mod` and `$mul` give plain numbers:
  `$div(100,1)` is `100`, not `1E+2`.
- Sorting by Length, Size or a number column goes by value: `01:18`
  before `01:04:17`, `16 KB` before `1.26 MB`; sorting a number column
  such as `__frequency_num` no longer crashes (#465).
- Dragging files out of the table to move them no longer sends the
  selected files the drop didn't move to the trash; the moved files
  just leave the list.
- Write Previews also writes the files the Filter hides, under the same
  single Undo.
- Renaming a file to a name that differs only in case works on
  case-insensitive filesystems (macOS, Windows, some network shares)
  instead of saying "File exists" (#966).
- Tag to Dir (Convert > Rename Directories) no longer deletes the
  folders its move leaves empty, the loaded folder included.
- Extended Tags on one selected file has Previous and Next again, and
  in Preview Mode shows the edits typed in it in bold; OK stages only
  the fields you changed.
- Picking `<keep>` in the Tag Panel in Preview Mode keeps each file's
  own value. Before, Write Previews wrote the text `<keep>` into every
  selected file.
- OK in Preferences no longer deselects the files and empties the Tag
  Panel.
- Refresh Directory in the Filesystem dock reads the folder again. It
  did nothing for a folder already listed, so changes the file watcher
  missed (common on network shares) never showed. The expanded folders
  stay open.
- In the Tag Sources window, an album whose tracks couldn't be
  retrieved can be expanded again; it used to stay stuck, ignoring
  clicks and keys.
- Save no longer deletes a file's unreadable cover when the Artwork
  window was open and the file before it had a good one.
- Cancel in Write Previews no longer throws away the previews of the
  files it hadn't written yet; Preview Mode stays on with them.
- Quitting while the Filesystem dock is still selecting the folder just
  opened no longer crashes puddletag.
- The Default language is English again on any system; on a
  right-to-left system it laid the window out right to left, with Qt's
  own texts translated.
- A pip install now includes the plugins that come with puddletag;
  until now they were only in the source tree.
- Dupe highlight colours every selected file that shares the field's
  value with another, not only a file whose neighbour above has it;
  Cancel leaves it off.
- With Show all fields on, OK in Preferences or quitting no longer
  replaces your own columns with the all-fields view.
- Update to ID3v2.4 writes ID3v2.4 even when Preferences are set to
  ID3v2.3, and ID3 Tools warn about a read-only file instead of
  crashing.
- Add 2 seconds to modified time adds exactly two seconds.
- A plugin of yours named like one that comes with puddletag is left
  out, with a warning in the log.
- Load playlist keeps names with quotes in them and the folders already
  open.
- Mass Tagging matches albums for files numbered 1/12 or 01,
  compilations by "Various" or a translated "Various Artists", and
  polls sources again with every selected file.
- An MP3 with no album gain stored no longer shows `__albumgain` as
  `None`.

### Security

- Paste no longer runs code another program puts on the clipboard. Copy
  writes the tags as JSON and Paste reads only that, so tags copied in
  an older puddletag don't paste into this one, or the other way round.
- AcoustID's requests, with the user's key, now go over https.

## [2.5.0] - 2025-07-27

### Added

- Add keywords to the .desktop entry to improve findability
  (#921, by mmvanheusden)

### Fixed

- Fix a crash in the filter (#930, by corubba)
- Fix an empty drop on Wayland (#973, by corubba)
- Fix error handling when a function in a pattern fails to parse
  (#974, by corubba)
- Fix columns that show the same tag field (#976, by corubba)
- Fix the wrong MusicBrainz album id (#995, by corubba)
- Fix a crash in the tag source widget (#994, by corubba)

## [2.4.0] - 2024-06-23

### Added

- Allow the .desktop file to open folders and audio and video files
  (#896, by freshgum-bubbles)
- Enable WMA support (#889, by corubba)
- Add more iTunes mappings for MP4 files (#902, by corubba)

### Fixed

- Fix a `RuntimeError` when loading a folder that cannot be listed
  (#887, by istvan-andrasi)
- Fix a typo in the error handler of the tag sources that hid the real
  error (#910, by willp)
- Fix a crash when deleting files (#911, by corubba)

## [2.3.0] - 2024-03-04

### Added

- Expose the Vorbis comment vendor string (#790, by corubba)

### Changed

- Use unidecode for `$to_ascii`, which converts more characters
  (#792, by corubba)
- Rework the custom icons to match the look of the others
  (#809, by corubba)
- Ship icons and data files directly instead of through the Qt
  resource system (#860, by corubba)
- Drop the wrongly added `chromaprint` and the unneeded `audioread`
  dependencies (#855, by corubba)
- Small music library improvements: Rhythmbox is always available and
  QuodLibet loads (#811, by corubba)

### Removed

- Remove the "Delete without confirmation" menu entry
  (#793, by absolutelynothinghere)
- Remove support for the Amarok and Prokyon music libraries
  (#811, by corubba)

### Fixed

- Fix the window icon under Wayland (#769, by corubba)
- Fix the `__reference_time` error in the Discogs tag source
  (#767, by beurotta)
- Fix the Swedish translation (#779, by corubba)
- Update the translations (#810, by corubba)
- Fix reading of MP4 freeform tags (#789, by corubba)
- Fix cover art for APEv2 (#791, by corubba)
- Improve natural sorting (#794, by corubba)
- Fix the image mimetype (#787, by corubba)
- Fix the "Import text file" function (#807, by corubba)
- Fix the progress window when there is nothing to do
  (#803, by corubba)
- Fix a crash in the mass tagger when there are no files or profiles,
  and when setting its percentages (#802, by corubba)
- Fix the shortcuts file being overwritten at every start, and use
  icon names for all icons (#799, by corubba)
- Fix sorting by multi-value fields (#817, by corubba)
- Pass multi-value fields to and from functions properly
  (#858, by corubba)
- Fix the mass tagger log output in the GUI (#859, by corubba)
- Fix an error when joining multi-value fields (#861, by corubba)
- Fix file path changes in preview mode (#862, by corubba)
- Fix iTunes tags in MP4 and ID3 files (#865, by corubba)

## [2.2.0] - 2022-07-04

### Added

- Add Help > Report a problem, which opens a bug report pre-filled
  with the system and library versions (#730, by corubba)
- Build with `pyproject.toml` and PEP 517 (#714, by corubba)
- Preserve column sizes when the column layout changes
  (#697, by corubba)
- Add some German translations (#689, by Zomtir)
- Update the Brazilian Portuguese translation (#738)

### Changed

- Show a more explicit message when a file is not UTF-8
  (#688, by Zomtir)
- Improve the About dialog (#698, by corubba)

### Fixed

- Fix the filter, which accepted every file, and a crash on
  unparsable filter input (#690, by corubba)
- Fix scrolling (#691, by corubba)
- Fix the ID3 UFID frame and other MusicBrainz problems
  (#693, by corubba)
- Use a valid fallback language for ID3 USLT frames
  (#696, by corubba)
- Fix crashes in "Format value" (#702, by nipsufn)
- Fix a crash when changing shortcuts in the settings
  (#706, by corubba)
- Fix the function combobox and the artwork font and window
  (#707, by corubba)
- Restore compatibility with Qt 5.12 (#711, by corubba)
- Fix the refresh of the folder view and hide the expand arrow on
  folders without subfolders (#710, by corubba)
- Remove a ghost window (#716, by corubba)

## [2.1.1] - 2022-02-04

### Changed

- Enable or disable the paste image menu entry according to the
  clipboard contents (#678, by pedrobaeza)

### Fixed

- Fix the AllMusic tag source (#677, by bernd-wechner)

## [2.1.0] - 2022-01-31

### Added

- Add an action to navigate to the parent folder of the selected file
  (#539, by vlad-te-87)
- Accept multiple file and folder names on the command line
  (#567, by GeoffRichards)
- Add clipboard copy and paste support for covers
  (#652, by pedrobaeza)
- Release puddletag to PyPI (#672, by sandrotosi)

### Changed

- Do not use native dialogs for folder open (#536, by tonurics)
- Rewrite the autonumbering function (#591, by terbshaeusser)
- Ask whether to discard changes when refreshing with previews active
  (#651, by poelzi)
- Correct the Spanish translation (#625, by josevidalrt)

### Fixed

- Fix a crash in "Update from tag" (#543, by blueblots)
- Fix a crash of the mass tagging search button (#545, by blueblots)
- Fix a crash in `$to_ascii` (#554, by blueblots)
- Fix a `TypeError` crash when querying MusicBrainz
  (#562, by blueblots)
- Fix a crash when adding a custom tag with a lyrics language
  (#574, by blueblots)
- Fix a bug in the extended tags view (#603, by blueblots)
- Fix a crash when searching with AcoustId (#604, by blueblots)
- Fix an index error in the action dialog (#561, by blueblots)
- Fix a crash when exporting artwork to a file in an action
  (#551, by blueblots)
- Fix a crash on read-only files (#547, by blueblots)
- Fix the Shift+Enter behavior (#627, by grlee77)
- Fix crashes in the action dialog (#550, by blueblots)
- Fix an `ImportError` in the View All Fields plugin
  (#544, by blueblots)
- Fix a crash in the split field function with an empty separator
  (#649, by k0mmsussert0d)
- Add `lxml`, which the AllMusic tag source needs, to the
  requirements (#667, by bernd-wechner)
- Fix a bug in the AllMusic tag source (#669, by bernd-wechner)
- Fix `get_encoding` in the tag sources (#671, by bernd-wechner)

## [2.0.1] - 2020-08-29

Python3 and PyQt5!

## [2.0.0] - 2020-08-29

It's finally here!

(I [Keith] personally had nothing to do with it). This release is
thanks to Sandro Tosi and the amazing people below.

- blueblots
- Elizabeth M
- elsabio
- klslz
- Marko Hauptvogel
- Pedro M. Baeza
- Steven Saus

There are no new features, but probably a bit more bugs. This release
is purely about updating puddletag to Python3 and PyQt5.

Cheers!

### Changed

- Python 3!

## [1.2.0] - 2016-11-27

Minor fixes were made over the course of the year. This release is so
that package maintainers can update their repos.

A Debian package is no longer supplied, supporting two versions of
Ubuntu and Debian from a single .deb would take way too much time. For
Ubuntu users, [WebUpd8](http://www.webupd8.org/) keeps their
[PPA](https://launchpad.net/~nilarimogard/+archive/ubuntu/webupd8) up
to date.

### Added

- CJK Encoding for Encoding Conversion Function (XIE Dongping)
- Swedish translation (Åke Engelbrektson)
- Spanish translation (José Vidal)

### Changed

- Improved Amazon tag source album matching.
- Czech translation (Pavel Fric)

### Removed

- Compiling Ubuntu deb

### Fixed

- #280 Turn off auto-saving "Enter description here" description for
  cover art
- Parsing tracks in Discogs if only a single artist (Frank
  Sachsenheim)
- Setting user-agent for Tag Sources (Frank Sachsenheim)
- Support for latest mutagen (Bruno Bergot)

## [1.1.1] - 2016-01-31

There was a bug where puddletag would not start if you didn't have git
installed. v1.1.1 released as a result.

### Fixed

- Fixes issue starting puddletag without having git installed.

## [1.1.0] - 2016-01-31

puddletag v1.1.0 is out. This release contains minor changes made over
more than a year.

This will be the last release on SourceForge. All future downloads will
point to GitHub. Documentation can be found at the new URL
<http://docs.puddletag.net>.

I'm still looking at different options re the forum. I'll close it
towards new posts within the next month.

### Added

- Autonumbering has a bunch of new options. Explained
  [here](https://docs.puddletag.net/source/menus.html#autonumbering-wizard).

### Changed

- Modified date is updated by default when saving

### Fixed

- Playlists not getting loaded in certain cases
- Discogs changed their API to allow OAuth. As a result you can now
  only lookup releases using their Discogs release id.
- Plugins are now included in default install
- Padding of total tracks number follows the same rules as padding a
  track number #269
- Improved matching of Amazon resources
- Filtering 'simple' values works again #253
- Bug in regex functions where extra `\` can get added

## [1.0.5] - 2014-11-15

This is a bug fix which fixes an issue in Actions where floating point
values were handled incorrectly.

[.tar.gz download](http://sourceforge.net/projects/puddletag/files/puddletag-1.0.5.tar.gz)
|
[.deb download](http://sourceforge.net/projects/puddletag/files/puddletag_1.0.5-1_all.deb)

### Fixed

- A bug in actions where floating point values weren't getting handled
  correctly. Could cause puddletag to lock up.

## [1.0.4] - 2014-11-09

This one has been a long time coming. Not much new except bugfixes,
but they should lessen some of the pain that some users have been
experiencing.

[.tar.gz download](http://sourceforge.net/projects/puddletag/files/puddletag-1.0.4.tar.gz)
|
[.deb download](http://sourceforge.net/projects/puddletag/files/puddletag_1.0.4-1_all.deb)

### Added

- `$to_num` scripting function. Converts text to numbers for easy
  comparison.
- AIFF support.
- Configuration is stored using XDG dirs. Settings are in
  `~/.config/puddletag` and `~/.local/share/puddletag`

### Changed

- All config options are stored as JSON. Should fix issues with not
  being able to store certain values.

### Fixed

- Regular expression parsing
- Discogs API no longer working. Fixed it so that searches can be done
  using Discogs release id only.
- Fixed comparison of boolean values in format strings.
- Scripting function escaping wasn't working.

## [1.0.3] - 2014-03-11

### Fixed

- Placeholder causing puddletag to not start up for Qt < 4.7.
- New version of configobj library not saving unicode objects.
- `__num_images` count for mp3 and ogg.

## [1.0.2] - 2013-11-07

Well, it's been more than a month and now major new issues have been
report.

There's not much to tell, but here's some things anyway.

### Added

- Opus support.
- Artwork windows list JPG + PNG's at the same time.

### Fixed

- Escaped chars in functions weren't being escaped correctly. Check
  your functions if they make use of this odd behaviour.

## [1.0.2RC1] - 2013-07-14

I've been using this release since forever and consider it to work
pretty well.

Still an RC though, just in case there are any showstoppers. Use the
forum link above if you run into any issues. The list of changes is
larger than usual. Checkout the changelog for more.

If no new issues are reported I'll just rename it to 1.0.2 within a
month. ;-)

[Debian Package](http://sourceforge.net/projects/puddletag/files/dev/puddletag_1.0.2RC1-1_all.deb)
(SHA1 36b9d63504e95cba47667b48158b0a2132e39bf7)

[Source Tarball](http://sourceforge.net/projects/puddletag/files/dev/puddletag-1.0.2RC1.tar.gz)
(SHA1 fd832e627cc49aa0379021a7b777c08f23b92550)

### Added

- Dropdown in Extended Tags that works like Tag Panel. Useful for
  editing multiple valued fields.
- You can now submit your tags containing MusicBrainz IDs to AcoustID.
  I suggest you do this.
- Russian and Czech translations (Czech by Pavel Fric). Compiled
  translations are also included in default install.
- `__total` can be edited in Tag Panel and other places.
- Multiple-valued fields can be added using `\\` in extended tags.
- Confirmation dialog if copying large amounts of data.
- In field selection dialog for columns, fields are listed in combo
  box.
- Support for MusicBrainz cover art.
- Directory modified date is force-changed if files are modified.
- Disambiguation to album title for MusiBrainz so that album titles
  would be "Somaro (Deluxe Edition)" instead of just "Somaro".
- `catno` field to Discogs tag source.

### Changed

- Column settings take ordering made by user (by dragging, etc) into
  account.
- Discogs multiple artists are concatenated using &.

### Fixed

- MP4 tagging not working at all. I cannot believe no one picked this
  up.
- Discogs didn't return all album info.
- Directory renaming not stripping invalid chars.
- `$validate` scripting function failing when '/' in arguments.
- Unable to delete fields if `__total` populated.
- Album art can be dragged from browser. If link can be resolved,
  image will be loaded.
- Search by ID for MusicBrainz tag source.
- Removed invalid files from puddletag.pro for translations.
- Checked Actions being overwritten by check Quick Actions selections.

## [1.0.1] - 2012-08-31

This release fixes some bugs spotted with the last release.

Have fun!

### Changed

- AcoustID tag source is not loaded if `fpcalc` binary not found.

### Fixed

- Issue 189.
- puddletag.desktop file installation error with deb package.
- Python2.6 incompatibility.

## [1.0.0] - 2012-08-21

v1 has finally arrived!

There's not much difference between this and RC1 though. Just a change
of icon and minor fixes. If you want to have a look at the changelog.

Right now puddletag is about as stable as it'll get without much more
work. As for the future, I have a some things that I've been putting
off until v1. A command line version being top priority.

Anyway, that's it for now. Enjoy!

### Added

- Russian translation by Viktor Yu. Kovalskiy
- German translation by Ralf Sarholz
- To .desktop file, options that'll make it possible to right click in
  FM and open in puddletag.

### Changed

- Updated icon
- Updated .desktop file as per issue 186.

### Fixed

- Cutting tags wasn't working.
- If multiple files were selected in file-view and edited. When
  changing focus, the new cell would be opened and would remain with
  the value as before after the change.
- Encoding is added for genre field. Fixes
  <http://sourceforge.net/apps/phpbb/puddletag/viewtopic.php?f=4&p=699&sid=10751cabefe27ffcd74eea2dde7663f8#p699>
- Filter wasn't working with filename fields like `__filename`.

## [1.0.0RC1] - 2012-06-09

This release is the first RC with the final release planned for next
week depending on feedback. All that's still needed is to update the
docs, fix some outstanding bugs and package the plugins.

As for the changes here, it's just some bug fixes. For a more
comprehensive list see the changelog.

### Added

- Copy/Paste now copies the data as JSON to clipboard.
- Status message for Mp3tag tag sources.
- Made it impossible to save Functions with invalid field names.
- AcoustID tag source also returns `acoustid_fingerprint` field.

### Changed

- Filesystem panel will not update if hidden. Works for loading large
  directories so puddletag won't freeze for an extended period.
- If directory was created when removing a file, that directory will be
  removed if change is undone.

### Fixed

- Loading a new directory would sometimes not unload previously loaded
  directory (issue 180).
- Mp3tag tag sources are more compatible than before.
- AcoustID doesn't have as many dependencies. Only
  [chromaprint](http://acoustid.org/chromaprint) as included sampsyo's
  pyacoustid source and wrote supporting libs to contain only needed
  code.
- Issue 183 where the Tag Sources dialog wouldn't unfreeze for invalid
  results.
- Masstagging was discarding albums with same name.
- Issue 181. `regex` function wasn't working on Python 2.6.
- Undoing filename related changes weren't being effected.
- Creating new actions duplicated old ones.

## [1.0.0beta6] - 2012-04-18

Updated to 1.0.0beta6 to fix issues with deb. This is the second last
beta.

### Changed

- Added translations to source tarball.

### Fixed

- Fixed issues with deb not un/installing.
- Fixed issue with dropping album art on Artwork window. Invalid files
  would still affect the files that have been loaded.
- Fixed error in parser where it wouldn't detect syntax errors
  correctly.

## [1.0.0beta5] - 2012-04-11

This release contains a ton of fixes with regards to Tag Sources.

That's it basically. If you want more, see the changelog. Docs for the
latest version have been uploaded
[here](http://puddletag.sf.net/latest/docs.html). I still have quite a
bit of updating to do though.

[Please let me know if you experience any issues.](http://code.google.com/p/puddletag/issues)

### Added

- `__md5_sig` field that lists internal MD5 signature of FLAC files.
- `$regex` scripting function.
- Dutch Translation by Fabian Bakkum.
- Added AcoustID support, but not for general use yet due to the heavy
  dependency load. Do not try to make it work unless you're an
  'advanced' user.
- Rate limiting for FreeDB as too many requests at once causes errors.
- Added parameter to `$num` function to use track separators or not
  (default not)

### Changed

- Restart numbering checkbox in Autonumbering wizard now hides the
  Total spinbox so that track numbering is generated for each
  directory.
- `$num` function uses the length for the track number only and not the
  total.
- Massively updated parser.
- ID3v2.3 frames are written in same order as Mp3tag's.

### Fixed

- MusicBrainz works.
- Discogs works better with regards to VA albums.
- Fixed Amazon tag source as now requires AssociateTag to do lookups.
- Featuring artist in MusicBrainz tag source are parsed correctly.
- For functions like `$meta_sep` to not use parsed patterns as things
  like `\\\\` were being parsed as one separator instead of two.
- For Discogs, fixed albums where tracks don't have lengths weren't
  being loaded.
- Fixes issue 174, where if scrollbar shown in Functions dialog, it
  sometimes hides text.

## [1.0.0beta4] - 2012-02-12

### Added

- Helpful menu items added to about menu.

### Changed

- Updated documentation.

### Fixed

- Fixed centering of images in docs.
- When Discogs returned no results there'd be an error.

## [1.0.0beta3] - 2012-01-24

### Fixed

- Fixes for issue 171.

## [1.0.0beta2] - 2012-01-23

### Fixed

- Fixed MusicBrainz not working (issue 170).

## [1.0.0beta1] - 2012-01-22

It's been a while I know, but I figured if I don't get this out now I
might just leave it until next year.

This is a beta, reason being that it's not anywhere near thoroughly
tested.

Test it out and if you find any bugs feel free to
[let me know](http://code.google.com/p/puddletag/issues).

[Download](https://docs.puddletag.net/download.html#development-builds)

### Added

- `$ceiling`, `$eql` (renamed `$equals` in 1.0.2), `$floor`, `$round`
  scripting functions.
- Full support for Mp3tag tag sources.
- Support for MusicBrainz and Discogs new APIs.
- More than one file can be written to at a time in the file-view. Just
  select more than one file, edit a field as normal (like album) and
  Bob's your aunt.
- Confirmations when exiting/loading dirs if file's still contain
  previews.
- Update Discogs tag source to use new Discogs API as per
  <http://www.discogs.com/help/forums/topic/234138>.
- `--version` command line option.

### Changed

- Masstagging improvements with regards to both matching (courtesy of
  [beets](http://beets.radbox.org/)) and searching.
- Improved masstagging for albums with weird track numbers.
- Masstagging ignores stuff between brackets like "this name (disc 1)"
  and retries the search.
- Mastagging checks all files and rearranges for best matches instead
  finding the best match for one file and putting that match out of the
  running for checking with later files.
- Files containing APEv2 tags are loaded even if the file is not a
  valid audio file.
- If writing previews to files fails, then those files' previews are
  kept.
- Quickactions and actions' checked settings are now stored in
  different keys in config.
- Plugins are sorted in plugin chooser widget.
- Request to check log to for more info in error messages.

### Fixed

- Fixed a bug whereby if a file has an invalid picture type,
  puddletag would not start up.
  <https://sourceforge.net/apps/phpbb/puddletag/viewtopic.php?f=4&p=542#p542>
- An error would be raised when trying to save invalid picture data.
  Data is discarded now upon saving. Issue 167

## [0.10.6.3] - 2011-08-24

### Changed

- Did modifications for inclusion into Debian.

## [0.10.6.2] - 2011-08-21

### Changed

- No source changes. Added missing files required for Debian
  packaging.

## [0.10.6] - 2011-06-06

0.10.6 fixes another bug not found. Think this'll be the last for now.

### Fixed

- Fix for freezes if Update empty fields and 'Retrieve exact matches.'
  checked in Tag Sources dialog.

## [0.10.5] - 2011-06-04

Tag sources were broken due to a bug not found in testing. Therefore
0.10.5 has been released.

### Fixed

- Fixed broken tag sources in release.

## [0.10.4] - 2011-06-03

Unless there're some critical bugs discovered in this release, then the
next release will be puddletag v1. There won't be much changed except
for a couple of dollops of polish. I plan to release it around the end
of this month.

As for this release, there're a lot of changes, but nothing of note UI
wise (except for the website theme change copied from the
[Django docs](http://djangoproject.com)).

Quickly listed, I've added a Man page, created a slightly better
looking splash screen, converted the documentation to reStructuredText
and added it to the tarball. Also there's a changelog containing most
everything done and **Raphaël Rochet** became the first person to
translate puddletag by providing a
[French translation](https://docs.puddletag.net/about.html#translators).

### Added

- French translation contributed by Raphaël Rochet.
- Man page added.
- New logo created.
- Added data files to source tarball.
- Added documentation to source tarball.
- Added changelog.
- Much improved masstagging.
- The
  [Export artwork to file](https://docs.puddletag.net/source/function.html#export-artwork-to-file)
  Function.
- The filter behaves like Mp3tag's. Described in
  [source/filter](https://docs.puddletag.net/source/filter.html)
- For the Discogs tag source:
  - Added the ability to retrieve track artists for Various Artist
    albums.
  - This required that the `involvedpeople` field be renamed to
    `involvedpeople_album` as a list of involved people were returned
    for each track too.
  - These people are added to the `involvedpeople_track` field.
- URL links for albums in Tag Sources dialog are shown for all Tag
  Sources (except FreeDB).
- Tag to filename and Tag->Dir functions handle patterns like
  `'../%artist%'` and `'./%artist%/%album%'` correctly.
- Options for setting the pattern used in saving covers to file
  dialogs.
- Ability to drag and drop folders on file-view.

### Changed

- Unicode support for Replace with Regular Expression function.
- `peformersortorder` has been renamed to `performersortorder` in ID3
  tags.
- Renaming dirs hooks into
  [Tag->Dir](https://docs.puddletag.net/source/function.html#tag-to-dir)
  function now.
- Similarly the `lyrics_us` field is now `unsyncedlyrics`.
- Functions dialog restores last used function upon first load.
- In QuodLibet Library:
  - Changes the fields: `_rating` to `rating`, `_skipcount` to
    `__skipcount`, `_playcount` to `playcount`.
  - All fields are caseless.
  - Fixed the loading of fields with numbers for values.
  - Added the `__tag` and `__tag_read` fields.
- Proper error messages are now shown, differentiating whether the
  error occurred while writing to files or renaming dirs, files.
- The semi-colon character (';') has been removed from the list of
  invalid filename chars.
- The old Extended Tags plugin will no longer work. Use the
  [new one](https://docs.puddletag.net/source/plugins.html#bundled-plugins).
- Overhaul of Masstagging internals.
- Images can be removed when the Cover Varies in Extended Tags.
- If last loaded dir is not found on startup, then all parents of that
  dir (still existing) will be expanded.

### Fixed

- Multiple value handling for ID3v2.3.
- When editing actions, if a field not in the current list of fields
  was used, then the list of saved fields would contain only that
  field.
- Undoing renaming of dirs and adding images using the Extended Tags
  dialog.
- Patterns that use scripting functions in the form
  `$validate(arg1,,arg3)`. will work correctly in that the second
  argument will evaluate to an empty string instead of being discarded.
- Issue 132: Images weren't being added to list of fields to undo.
- For Discogs Tag Source: Images were being retrieved even if disabled
  when using textual searches.
- Changing files in Extended Tags changes the selection in File-View,
  thereby ensuring changes are written to the correct file.
- Lines that contain '/' being parsed incorrectly in Import Text File
  dialog.
- FreeDB tag source artist/album parsing.
- MusicBrainz Tag Source ratings error.
- Tag->Dir creating subfolders when it shouldn't.
- Numbering of COMM frames (and others like it) to have frames with the
  same description being number 0,1,2,3 instead of 0,01,002, etc.
- If a file contained an ID3v2.2 tag than that tag would be shown twice
  in the Stored Tags window.
- Editing colour in Extended Tags remaining green even if changed.
- Subfolder checkbox in the Filesystem window being enabled when it had
  no reason to be.

## [0.10.3] - 2011-03-23

A couple of critical bugs were found in the last release, they've all
been fixed.

Provided nothing critical arises, there won't be any releases until at
least late next month.

### Fixed

- Deleting tags when they contain mapped fields.
- Functions operating on multiple values like Merge Field were broken.
- `peformersortorder` is spelt correctly as `performersortorder` for
  ID3 tags.
- Renaming directories when intermediate directories are to be created.

## [0.10.2] - 2011-03-20

Another incremental-bugfix release. I might release another one before
month-end.

### Fixed

- Contains a fix for bug discovered in 0.10.1 where the default dir for
  saving artwork defaults to home directory.

## [0.10.1] - 2011-03-20

### Added

- A bunch of new fields related to Mp3tag compatibility, most notably
  `__tag` and `__tag_read`. All are listed on the
  [source/tags](https://docs.puddletag.net/source/tags.html).
- Loading subfolders can be turned on/off using the Filesystem Window.
- USLT Frame support for ID3 that uses the same format as ID3. See the
  [ID3 page](https://docs.puddletag.net/source/id3.html#uslt).
- The Stored Tags window shows the values of all tags found in file.
- Experimental ID3v2.3 support courtesy of
  [MusicBrainz Picard](http://musicbrainz.org/doc/PicardTagger).
  Multiple values are not supported. Don't use it for now unless you
  really need to. Then report back on how it went. Enable it in
  `Edit->Preferences->Tags`.
- Two new plugins. Details are on the
  [Downloads](https://docs.puddletag.net/source/plugins.html#bundled-plugins)
  page.

### Changed

- Values in the Stored Tags window aren't emboldened anymore due to
  performance reasons.

### Removed

- WMA support has been completely removed due to the high risk that
  you'd end up with damaged files.

### Fixed

- Major MP4 fixes.
- Retrieving PUIDS using the MusicBrainz tag source.
- Adding album art from Tag Source was defective.
- The Tag Panel not updating with 'previewed' values.
- Properties window not showing for certain file types.

## [0.10.0] - 2011-03-08

This is a kind-of bugfix release. I'm releasing it before I start with
some pretty major architecture-related changes.

Oh, and puddletag is now licensed under the
[GPLv3](http://www.gnu.org/licenses/gpl-3.0.html).

### Added

- Cover art support for all formats (except ASF)
- Loading master releases in the Discogs.com tag source.

### Changed

- For ID3 tags, UFID frames are now only loaded if the data can be
  decoded to UTF8.
- MusicBrainz artist search retrieves 100 albums by default.
- The initial reading of a directory can be canceled now.

### Fixed

- Uncaught errors for Tag Sources shouldn't leave the Tag Sources
  window disabled anymore.
- Discogs artist/albums are parsed correctly instead of looking weird.
- Amazon keyword search wasn't working at all.
- Having periods in the Tag->Dir function were causing problems.

## [0.9.12] - 2011-02-09

Almost all the work done, was modifying the code base so that
puddletag could be translated properly. I've put up a
[translation guide](https://docs.puddletag.net/source/translate.html)
for interested parties. Since this is a bug-fix release, there are no
new features, just some changes and fixes.

### Added

- puddletag is now fully translatable.

### Changed

- Users stuck using python-musicbrainz2 < 0.7.0 shouldn't have
  problems with puddletag crashing on startup.
- Nor is python-musicbrainz2 a hard dependency any more.
- The default user agent now set to puddletag/0.9.12. New users will be
  able to use the Discogs Tag Source 'out of the box'.
- I might've used some things available only in newer Qt versions. If
  you're using Qt/PyQt >= 4.5 and puddletag crashes,
  [let me know](http://code.google.com/p/puddletag/issues).

### Fixed

- Editing `__dirname` and `__dirpath` while using QuodLibet library is
  now possible + tons of Music Library related bugs.
- Editing Actions sometimes didn't work.
- The `Load Artwork` function didn't work as advertised.
- `%__total_files%` and `%__counter%` not working when used within
  scripting functions.
- The Artwork Window is floating by default. Fixes an issue whereby the
  puddletag window would be larger than the screen.

## [0.9.11] - 2010-12-19

Another bug related to Tag Sources freezing often is fixed in this
release. Promise this is the last for a while. ;)

### Fixed

- Another bug where the Tag Sources dialog would freeze when
  retrieving albums is fixed.

## [0.9.10] - 2010-12-18

A bug was discovered in Discogs that'd make it fail on the vast
majority of albums (just not the ones I tested with). This release is
to fix that.

### Added

- Discogs uses the Discogs ID field (which you can define) if it's
  found in your files.
- You can use your own Amazon and Discogs API keys.
- `__counter` and `__total_files` fields which you can use in
  Functions and Actions. Info
  [here](https://docs.puddletag.net/source/tags.html).

### Fixed

- Case Sensitivity for field names is handled better.

## [0.9.8] - 2010-12-16

This'll be the last release for a while as I'm taking a break from
puddletag development. I'll still be lurking in the forums and issue
tracker, so don't hesitate to ask for help or report bugs.

All in all this has been a good year for puddletag. It went from
kinda-working to better than anything else on Linux. Besides myself you
gotta thank Evan for that. Without his constant feedback, testing and
feature requests puddletag would be way less than it is.

So yeah, some goals (like better WMA support) haven't been met, but on
the whole I'm satisfied with the way things turned out. The next
planned release will be around mid to late March 2011, although I might
do one in late January to update translations and plugins. Any other
releases before March 2011 will be bugfix releases.

Website changes:

- I've added another tutorial called
  [Things you should know](https://docs.puddletag.net/source/tut3.html).
  You probably know some of it already.
- Documentation for Preferences has been added
  [here](https://docs.puddletag.net/source/preferences.html).

### Added

- puddletag now supports translations. If you want to create one for
  your language create an on the
  [issue tracker](https://github.com/puddletag/puddletag/issues).
- A [new Function](https://docs.puddletag.net/source/function.html#convert-from-non-standard-encoding)
  to correct incorrectly encoded files contributed by Stjujsckij
  Nickolaj.
- MoveUp and MoveDown shortcuts that move the selected files Up/Down in
  file-view.
- The MusicBrainz tag source now retrieves even more fields. See
  [here](https://docs.puddletag.net/source/tagsources.html#musicbrainz)
  for a complete listing. The following fields were added to the
  MusicBrainz tag source: `mbrainz_rating`, `label`, `country`,
  `isrcs`, `musicip_puid`, `asin`, `barcode`
- Support for GUI and music library plugins. There aren't any docs yet.
  I'll add them in mid January. If you want to do development in the
  mean time, make a post on the forum and I'll help you out.
- A tag source that uses Discogs.com's XML service. I'm not sure how
  complete this tag source is since Discogs.com's documentation is
  woefully inadequate.
  [Info](https://docs.puddletag.net/source/tagsources.html#discogs).
  **You must set the User-Agent to use this!**.
- [Tag->Dir](https://docs.puddletag.net/source/function.html#tag-to-dir),
  with which you can move directories has also been included.
- puddletag now uses your theme's icons. Thanks to
  [this](http://sourceforge.net/apps/phpbb/puddletag/viewtopic.php?f=1&t=16#p178)
  post.
- I've added (tentative) support for Mp3tag's tag sources. Info
  [here](https://docs.puddletag.net/source/tagsources.html#mp3tag-sources).
- The '~'-notation used in Tag Sources can now be used for Functions
  too. See the bottom of
  [this](https://docs.puddletag.net/source/tut3.html) page.
- Options to remove ID3v1 and ID3v2 tags separately to the Tag Tools
  menu.
- You can now automatically retrieve matches using Tag Sources. Kinda
  like mini-masstagging.

### Changed

- The Replace with Regular Expression function now starts from `$1`
  instead of `$0`. I had to do this in order for Mp3tag's Tag Sources
  to work. Please update your actions.
- Previews in the Functions dialog now show the fields too.
- Action Shortcuts settings have been moved from Preferences to the
  Actions dialog.
- Tools->Sort Selected is now Tools->Sort By. The last sort option is
  now saved between sessions/loads. Visit this
  [page](https://docs.puddletag.net/source/preferences.html#sort-option-prefs)
  for info.
- `performer` in ID3 has been changed to `albumartist`.

### Removed

- **Select all in Dir** has been removed. I've added two new menu
  items. Select Next in Dir and Select Previous Dir. Info can be found
  [menus](https://docs.puddletag.net/source/menus.html#select-next).

### Fixed

- MP4 mappings and handling of unicode fields in MP4 files.
- ID3's rating didn't handle missing parameters well.
- Not loading APEv2 tags with cover art.
- Crashes due to renaming many directories at once.
- Undo errors while in Preview Mode.
- Quick Actions weren't working at all.
- Bug in Amazon Tag Source while retrieving small images.
- Loading playlist's with any contained file's having commas.
- Tag Panel not saving if genre isn't present.
- and more...

## [0.9.7] - 2010-10-30

There's not much to this release, but I think the second 'New Feature'
is pretty fundamental to puddletag's usability. Enjoy.

### Added

- The Autonumbering wizard is now a Function.
- Fields are now case-insensitive. Which means that if a file contains
  a field named 'album', writing to 'ALBUM' will rename 'album' to
  'ALBUM'.
- You can add your actions as shortcuts to the Actions menu. See the
  tooltip for Create Shortcut in Actions dialog for details.

### Changed

- Filenames are now written using the filesystem's encoding instead of
  UTF-8 (though you should be using UTF-8 anyway ;)).
- A new logo cause the old one was getting a bit long in the tooth.
- Functions now save their state.
- PIL (the Python Imaging Library) is no longer a dependency.
- I've relaxed the dependencies for the deb so that it should work on a
  wider range of distributions.

### Fixed

- Just a couple bugs were fixed, but nothing noteworthy.

## [0.9.6] - 2010-10-13

There was a major bug discovered in 0.9.5 where fields weren't being
shown in the Function's dialog. This release fixes it.

### Fixed

- Major bug fixed where the fields weren't being shown in the
  Functions dialog.

## [0.9.5] - 2010-10-09

This release is a bit late, but packed with features.

### Added

- Actions and Functions now operate and write multiple-valued fields.
- A bunch of new Functions. All listed on the
  [functions](https://docs.puddletag.net/source/function.html).
- Two new scripting functions copied straight from Mp3tag, `$meta_sep`
  and `$meta`. See the
  [scripting functions](https://docs.puddletag.net/source/scripting.html)
  page for details.
- A new icon. This one designed by Yianni Pappas-Acreman.
- A new Tag Tools menu, with which you can remove ID3 and APEv2 tags
  from files where they don't belong.
- Configurable confirmations. Like when you want to Rename Directories,
  etc.
- A `__dirname` field. Modify this field to rename the directory.
- UFID frames for ID3v2 Tags.
- Monkey's Audio File's are now supported.
- The Actions and Functions dialogs can now be tool windows too (See
  Windows Menu).
- All [docs](https://docs.puddletag.net/docs.html) have been updated.

### Changed

- Files that have previews now have a green background while in Preview
  Mode (Configurable in Edit->Preferences).

### Removed

- The configuration for the MusicBrainz Tag Source has been removed.
  Instead I've opted to return MusicBrainz fields (Album ID, Artist ID,
  Track ID) by default in `mbrainz_track_id`, `mbrainz_album_id` and
  `mbrainz_artist_id`. I've also set up default mappings, so that these
  fields are written to the correct field for each format. Remove
  `~/.puddletag/mappings` to get these.

### Fixed

- If it was broken before, it probably works now.
- The one major fix is that you can load files with messed up
  encodings now, instead of having puddletag choke on them.

## [0.9.4] - 2010-08-25

As promised, this release is awesome. The next one will be in a couple
of weeks, it'll include some features I've been promising for a while.

### Added

- Profiles were added to MassTagging, which means now you can do a
  configuration once and use that forever.
- Renaming files is now possible within Preview Mode.
- A new Function called 'Remove Fields' that does exactly that.
- A new scripting function (contributed by Erik Reckase) that'll
  convert unicode strings to ASCII.
- The plugin interface for tag sources is now public. See the docs
  [here](https://docs.puddletag.net/source/function.html).
- Right click on any directory. Click the refresh button to refresh it.
- You can now change the shortcut for any menu item.
  Edit->Preferences->Shortcuts to configure.
- Also, you can now sort selected tracks using predefined fields. Some
  defaults are in Tools->Sort Selected. Configure it using the 'Edit
  sort options' button in Preferences.
- I've finally added a RSS Feed to the website.

### Changed

- I've changed the way Tag Sources store their settings, so you'll need
  to reconfigure them.

### Fixed

- Some bugs related to Preview Mode not working correctly.
- A bunch of others that aren't really worth mentioning.

## [0.9.3] - 2010-08-11

Because of time commitments and the complexity of the new features,
this release is a bit late...and a bit unfinished. I'm releasing it,
because it contains too many bugfixes to keep to myself (and those
using svn).

Trust me when I say 0.9.4, due the 25th, will be awesome.

### Added

- I've added WavPack, MusePack, and basic WMA support (only common
  fields, not including artwork are supported.)
- *Masstagging*. Also known as the time-sink, was added. What this
  allows you to do is retrieve tags from multiple tag sources at once,
  combine time and write them to the selected files. It sounds simple,
  but extremely useful. There's no tutorial for it as yet (soon), but I
  think the interface is pretty self-explanatory.
- Also, I've added what I call Preview Mode, wherein you can do all
  your editing and write to files only once. See the description for it
  on the [menus page](https://docs.puddletag.net/source/menus.html)
  (scroll to bottom).
- A new Function called 'Load Artwork' Function with which you can load
  artwork from the file's directory. Explanation can be found on the
  [functions page](https://docs.puddletag.net/source/function.html).
- The plugin interface is now public for Functions. Tag sources will be
  available in the next release. For those interested, there's a
  tutorial [here](https://docs.puddletag.net/source/plugins.html).
- Converting filenames to tags can now take the directory name into
  account. Description on
  [menus page](https://docs.puddletag.net/source/menus.html).

### Fixed

- Some Tag Panel Bugs, including entries being replaced if an
  autocompletion was found of differing case. Genres always being
  Acapella and when adding entries like `Blues\\Rock` not being
  separated properly. And puddletag crashing on loading non-ASCII
  genres.
- Copy/Paste not working correctly sometimes.
- Saving artwork using Extended tags would clear the artwork instead if
  the cover differed between files. Sorry 'bout that one.
- Duplicate entries in comboboxes for the Functions dialog are now
  removed.
- A whole bunch of small ones which may have caused problems for
  someone somewhere.

## [0.9.2] - 2010-07-04

Again just a couple of things, but they improve the puddletag
experience immensely.

### Added

- FreeDB and Amazon tag sources were added.
- And puddletag can now use the MusicBrainz ArtistID if it's in a
  file's tag instead of searching for one. Still need to enable it for
  releases.
- Tag mappings for tag sources, see the tooltip in Preferences/Mappings
  for more info.
- And the ability to load only files based on their extension
  (Preferences/Tags to configure.)
- A new application icon created by Evan himself.

### Fixed

- No new fixes were entered last week, but there's a bug that
  completely freezes puddletag that I haven't been able to track down.
  I'll fix this one as soon as I find out just WTH is causing it.

## [0.9.1] - 2010-06-25

Just a couple of things this time. I spent most of my time on backend
stuff. Next week will be dedicated to tag sources, so expect some major
additions/improvements on that side.

### Added

- Moving files using Tag->File is now supported. See the
  [functions page](https://docs.puddletag.net/source/function.html) for
  examples.
- And using it as an part of an action is possible too.
- The option to not write ID3v1 tags.
- Complete rewrite of the tag sources backend. Now you can sort the tag
  sources window using any field you want.

### Changed

- The Replace with regular expression function now works like Mp3tag's.
  i.e only replacing matches instead of overwriting whatever field it
  was writing to.
- Extended tags now shows changes properly.

### Fixed

- A bug where the same value is shown for user-defined fields in ID3
  tags.
- The artwork windows resizing by itself (when not docked).

## [0.9.0] - 2010-06-11

Interesting Trivia. The World Cup starts in about an hour.

This release is pretty awesome. Evan found bugs, I fixed 'em. Then
added some polish. Then uploaded this release. Which is pretty awesome.

puddletag now has only two known bugs (and many unknown). That is all.
There's some UI changes some new features too for those interested.

## [0.8.8] - 2010-05-11

### Fixed

- Fixed some regressions with writing artwork and allowed saving of
  pictures in jpeg too.

## [0.8.7] - 2010-05-01

### Added

- Amazon tag sources plus a bunch of small stuff.

### Fixed

- Very many.

## [0.8.6] - 2010-04-14

It's five months later and from the outside it kinda looks like the
project has died when in fact I've spent more time working on
puddletag this year than I have the past two years. All thanks to Evan
Devetsis who've taken it upon himself to help me make puddletag
better. Mostly it was restructuring work in paving the way to add new
features.

Most everything has changed, so for those that've used it before,
explore and check it out. Cause I'm not listing all that here
(...because I forgot :)

### Added

- Multiple tag sources support. Musicbrainz only for now, will add more
  over the coming week.
- Tag mappings. Map a tag to whatever you want to.
- Some tags were changed. See the
  [Tag Reference](https://docs.puddletag.net/source/tags.html).
- More ID3 tags are supported.
- Unicode in MP4 tags is supported.
- Library code has been rewritten. Currently only QuodLibet is
  supported. Will add more week after next.
- Some of the scripting functions with odd names (`if_`, `not_`, etc.)
  have been renamed to what they're supposed to be.
- All icons not created by me are from the Oxygen icon set for KDE. As
  soon as I found out how to detect if GNOME is running, I'll add some
  Ubuntu icons.

### Fixed

- Far too many to list.

## [0.8.1] - 2009-11-05

There won't be any releases until at least February next year as I'm
gonna take some time of from puddletag (and python) to learn new stuff
and hopefully with enough new knowledge to implement the advanced
features that I've been thinking of. If I do discover some critical
bugs during this time though, I'll update the site.

### Added

- The only new feature for this release is that the MusicBrainz dialog
  now allows you to select individual tracks. I like it better now.

### Fixed

- Some (actually many) bugs with loading directories were fixed.

## [0.8.0] - 2009-10-10

For the next release I'm gonna give Musicbrainz lots of attention. It
really needs it.

### Added

- A Stored Tags dialog that shows the current tags of the selected file
  as stored on disk. Useful for when editing libraries and the tag
  differs from the tag on disk.
- I added an option to allow retrieval of duplicates via a specific
  tag. This can speed things up for some searches.
- A properties dialog as in Mp3tag (but slightly different) in addition
  to a delete tags button.
- And finally, a setup script.

### Changed

- Instead of changing the background colour of a row, the Musicbrainz
  dialog now just emboldens the text that's to be written. It's better
  this way.

### Fixed

- Duplicates can retrieve more than 300 at a time. (My fault for not
  checking.)
- Musicbrainz now works for all cases (it gave an error when retrieving
  via 'album').
- There ain't no more barfing of errors while editing text in the
  pattern combo.
- Reloading works again (didn't even know it was broken).

## [0.7.8] - 2009-09-09

Website changes:

- It looks tons better.
- A [screenshots](https://docs.puddletag.net/screenshots.html) section
  was added. I'll up some videos during the month if I get time.

### Added

- A super useful duplicates finder. It's not as well tested as I'd like
  so I'll make that a priority for the next release. Currently it only
  works on the supported music libraries. I'll add support for
  arbitrary folders during the month.
- Rudimentary file-management support had been added to the filesystem
  view.
- Note that I haven't added any progress bars for these features (due
  in a week) so just have patience when using them (and keep an eye on
  the command line for errors).

### Changed

- I've changed the config system to use ConfigObj as PyQt4's too buggy
  and Python's built in library too much of a pain. Because of this, I
  recommend you remove `~/.puddletag/puddletag.conf` just to avoid any
  adverse effects from using the new config style.

### Removed

- Amarok library support has been removed due to the fact that it'll
  probably not work on any machine but mine (and that's not even
  guaranteed).

### Fixed

- Bugs were fixed where needed (I seriously need to remember to log
  this stuff)

## [0.7.0] - 2009-06-04

Besides not having much time, I have been very lazy this month when it
came to puddletag. If all goes well then the next release will be more
bountiful.

### Added

- Loading times are improved by a couple of milliseconds.
- I've implemented a bit of fuzzy string matching via the Show Dupes
  button. Enter a tag prepended by a colon (like `:title` and values
  will be fuzzily matched. It uses the
  [python-Levenshtein](http://code.michael-noll.com/?p=third-party;a=tree;f=python-Levenshtein-0.10.1)
  for matching. If you don't have it installed, difflib (part of the
  standard library) is used. There isn't much difference except that
  Levenshtein is supposed to be faster since it's compiled (I haven't
  tested it though). Furthermore, entering `:artist` in the library
  search box will show you all the fuzzily matched duplicate artists.

### Changed

- I just changed the UI a bit to make it more coherent. It's still ugly
  as hell, but that's way outta my area of expertise.

### Fixed

- Sorting or doing anything else while some rows are highlighted is
  fixed.
- Other little stuff that I can't remember.
- There are many. I spent some time writing unit tests and testing the
  critical parts of puddletag. Many bugs were found. Many of these bugs
  weren't logged. This being said, there may still be some bugs as I've
  once again made some internal changes that could mess up things.
  Expect one or two updates during the month.

## [0.6.5] - 2009-05-01

I like so this release so much that I almost changed it to puddletag
version 1, but it still has some shortcomings compared to Mp3tag and
some things that I want to implement before then.

### Added

- Saving and loading is now loads faster. On par with Mp3tag (sometimes
  puddletag is faster, sometimes Mp3tag).
- Like Mp3tag, puddletag stores a history of all the values you've used
  for the Format Value function, and every other one. Unlike Mp3tag,
  puddletag allows you delete any entries you don't want on-the-fly, by
  clicking the red button next to it!
- Cut, Copy and Paste of tags is supported. Available via the Edit
  menu.
- The current selection is now preserved when sorting.

### Changed

- All window related actions were move to a new Windows menu to reduce
  clutter on the edit menu.
- A progress indicator is now shown when loading a music library.
- An error message is shown (on the console) if a file failed to load.
- Settings are stored in `~/.puddletag` instead of the `~/.config...`

### Fixed

- Saving or changing the image type now works in both the tag editor
  and Extended tags dialog.
- Also, the image controls being enabled or disabled depending on the
  file now works properly.
- Clicking Cancel while loading or saving now actually works as
  expected and instantly.
- The progress window doesn't stay persistent anymore when puddletag
  loads or saves files too quickly.

## [0.6.0] - 2009-04-11

### Fixed

- Saving pictures on an mp3 file with the same description.
- No more 'copy method' doesn't exist errors.
- Flickering of the >> and << buttons below images were removed.
- Buttons on the image editor are enabled or disabled depending on
  file.

## [0.5.9] - 2009-04-10

### Added

- Mp4 support was added (Mutagen `> 1.9` is needed and Mutagen `<= 1.9`
  isn't supported anymore.)
- And a console version was added. At the moment it's pretty basic, but
  as time goes on, it'll become better.

### Fixed

- Bugs wrt FLAC are sorted.

## [0.5.8] - 2009-04-08

P.S. This version is 0.5.8, because it's not tested as much as I'd
like, so expect many bugfixes over the coming month.

### Added

- M4A support (You need mutagen 1.9 or greater in order not to get any
  error messages)
- A console version (in the main directory as `console.py`). I've been
  pressed for time, so expect documentation to be added over the coming
  week.

### Fixed

- Bugfixes galore

## [0.5.4] - 2009-03-23

### Changed

- The In Library and Show Dupes action now change the colors of the
  rows that match instead of hiding those that don't.
- The Rename Dir action now works with library files. Keep in mind
  though that it only works for files loaded in the file-view and any
  other files that happen to reside in the same directory will not be
  updated.

### Fixed

- More bugfixes, especially related with the library treeview.

## [0.5.3] - 2009-03-10

### Added

- A search was added button to the library window, so that slow
  searches(like prokyon) don't suck as much.

### Fixed

- Actions sometimes behaved unexpectedly in that they didn't take the
  currently edited values into account.
- The show dupes button now works.
- A bug where strings such as `'%artist% - %title%.lower(%__ext%)`
  didn't work as expected, because the last part wasn't matched
  properly.

## [0.5.2] - 2009-03-09

Nope, still don't got no console version (been busy with other stuff,
definitely next month).

For the next release I'll concentrate on supporting the rest of
Mutagen's supported formats, fixing bugs and smoothing the user
interface (progress when loading a library, faster search, etc.).

Expect some interim updates over the next couple of days and a complete
release in about a month (1 April 2009).

### Added

- The ability to search the music libraries (albeit slowly).
- Two extra toolbar buttons, "In library" and 'Show Dupes".
- If a library is loaded then "In library?" hides all the files that
  are not in the library.
- "Show Dupes" hides all the files in the file-view that doesn't have a
  duplicate (in the file-view).

### Changed

- A totally revamped parsing system (though it'll look the same from
  the users point of view).
- Like Mp3tag, Actions are now stored separately instead of in one big
  file.

### Fixed

- ...and a ton of bugfixes, most of which I can't remember (but which
  are in the svn logs...well, not really)

## [0.5.0] - 2009-02-05

This is basically a bugfix release. There are far too many fixes to
list here, but some of the major ones were unicode related.

Hmmm, most of the other changes have to do with code quality (improved,
but not much) and refactoring, which I doubt you'll wanna hear about.

Anyway, the only thing I have for the next release is more powerful
scripting and (maybe not, but probably) a console version.

### Added

- If you wanna, you can use the `__image` tag to show the currently
  selected file's cover in the Tag Editor (Go to Preferences -> Tag
  Editor to add it)

### Changed

- UTF-8 is used for everything.
- The user interface has changed. This includes the look of the icons
  have improved (they're remain horrible, but still)

### Fixed

- Unicode support in prokyon, amarok and rhythmbox libraries was fixed.
- puddletag's unicode issues were sorted (e.g. If the last folder you
  visited contained non-ascii characters, puddletag would give you a
  big F-U.)
- Changing a picture using the extended tags dialog now works.

## [0.4.5] - 2009-01-20

Got a bunch of updates for ya.

First as promised, the feature is called **Import Your Music Library
(Tools -> Import Music Library)**. Like I said, I haven't seen it
before anywhere else. The reason (I think) it because it's extremely
difficult to do well. Right now, only three types of music libraries
are supported: Prokyon3 (which is what I use), Rhythmbox (which is what
a lot of other people use, why?) and Amarok (before version 2). I have
to mention a couple of caveats though. If your music library is spread
out across many devices (on another server especially), don't use
puddletag to edit the library, because I haven't taken those
conditions into account. Concerning Rhythmbox, you'll notice that it
has a save button above the Library tree. Use this to save files to the
database, because it takes a while to do for large libraries. Expect
these irritants to be gone two weeks from now.

I'm sure there's a bunch of other stuff, but I can't remember and I'm
to lazy to look at previous versions, so you'll just have to see for
yourself. Oh, there's a
[puddletag subreddit](http://www.reddit.com/r/puddletag) now too.

...Can't remember what else I did, cause I forgot to update the log.

### Added

- Music library support for Amarok, Prokyon and Rhythmbox. Currently,
  it's kinda sucky, but I'll spend some time on it and fix it as best I
  can.
- The user interface is a bit more customizable then before. The Tag
  editor and Filesystem windows are now tool windows. So you can drag
  them around and do whatever you want. Use the items on the Edit menu
  to show and hide these windows.
- Saving and writing images to id3 tags is now supported. You can do
  this via the extended tags dialog. Besides that, user defined tags
  are now supported (as long as the don't conflict with any of internal
  puddletag tags).
- The extended tags dialog now support editing and saving images. It
  also acts a bit more like Mp3tag's with options to move to the next
  and previous file in the file-view.
- Multiple tags are now available. I've followed Mp3tag's style of
  allowing the user to create multiple tags by using `\\` in the tag
  editor and removing multiple tags if the tag was edited in the file
  view.
- Like Mp3tag, the Preferences dialog now contains an extra option to
  edit all the patterns you've created using the patterncombo. Use it
  when you need to.

### Changed

- I modified much of the loading and saving code to be independent of
  PyQt so that users using PyQt 4.4.3 don't get those save and loading
  errors anymore.

### Fixed

- My Kubuntu cd arrived a couple of days ago and puddletag (besides
  having some bugs) looked atrocious. All these are fixed now, and all
  ya'll Kubuntu users who haven't been able to use puddletag can now
  share in the joy.
- There was a pretty nasty bug where puddletag would remove any
  unsupported tags. Sorry about that, hopefully you haven't lost any
  priceless info because of it.
- Any bugs to do with the extended tags dialog has been fixed (I hope)

## [0.3.1] - 2008-12-16

It's December and the sun is out. As such, all I have to show is just a
couple of bugfixes (in particular, the import from file window not
saving tags) and a message that appears in the statusbar when an error
occurs while editing a file.

Don't expect any updates until the 20th of January. If everything works
out I'll have at least one feature that sets puddletag apart from any
tag-editor I've ever seen and propel puddletag into greatness.

## [0.3.0] - 2008-12-03

### Added

- A splash screen for the long loads at the beginning to keep you
  company.
- Genres! Now you don't have to remember all of them.
- Press Ctrl+W to switch between the file-view, pattern combo and the
  tag panel.
- FLAC and APEv2 tags are now supported (only text tags, not images).
  Feedback on these would be appreciated as I have a serious lack of
  FLAC on my PC.

### Fixed

- The musicbrainz dialog doesn't freeze up puddletag anymore. Note that
  the threading is implemented in a very roughshod way though, so don't
  hesitate to contact me if behaves in unexpected ways.
- The main window's layout in addition to its size is now saved.
- Fixed niggling things like some controls not having accelerators.

## [0.2.5] - 2008-11-25

### Added

- A filter like in Mp3tag. F3 shows/hides it.
- Musicbrainz support (Available on the toolbar and Tools ->
  Musicbrainz). Not sure how good it is. Send me a mail if you have any
  ideas on improving it.
- The extended tags dialog is now available via the Tools menu (and by
  right clicking on the file-view).

### Fixed

- Saving a file's album art to disk now works.
- The importing tags text files dialog now looks better, by bolding the
  tags instead of the ugly interface puddletag had before.
- Not everything moves around when resizing puddletag anymore and the
  layout is saved from the previous session.

[Unreleased]: https://github.com/puddletag/puddletag/compare/2.5.0...HEAD
[2.5.0]: https://github.com/puddletag/puddletag/compare/2.4.0...2.5.0
[2.4.0]: https://github.com/puddletag/puddletag/compare/2.3.0...2.4.0
[2.3.0]: https://github.com/puddletag/puddletag/compare/2.2.0...2.3.0
[2.2.0]: https://github.com/puddletag/puddletag/compare/2.1.1...2.2.0
[2.1.1]: https://github.com/puddletag/puddletag/compare/2.1.0...2.1.1
[2.1.0]: https://github.com/puddletag/puddletag/compare/2.0.1...2.1.0
[2.0.1]: https://github.com/puddletag/puddletag/compare/v2.0.0...2.0.1
[2.0.0]: https://github.com/puddletag/puddletag/compare/v1.2.0...v2.0.0
[1.2.0]: https://github.com/puddletag/puddletag/compare/1.1.1...v1.2.0
[1.1.1]: https://github.com/puddletag/puddletag/compare/1.1.0...1.1.1
[1.1.0]: https://github.com/puddletag/puddletag/compare/v1.0.5...1.1.0
[1.0.5]: https://github.com/puddletag/puddletag/compare/1.0.4...v1.0.5
[1.0.4]: https://github.com/puddletag/puddletag/compare/1.0.2...1.0.4
[1.0.2]: https://github.com/puddletag/puddletag/compare/1.0.1...1.0.2
[1.0.1]: https://github.com/puddletag/puddletag/compare/1.0.0...1.0.1
[1.0.0]: https://github.com/puddletag/puddletag/compare/RC1...1.0.0
[1.0.0RC1]: https://github.com/puddletag/puddletag/compare/1.0.0beta6...RC1
[1.0.0beta6]: https://github.com/puddletag/puddletag/compare/1.0.0beta4...1.0.0beta6
[1.0.0beta4]: https://github.com/puddletag/puddletag/compare/1.0.0beta3...1.0.0beta4
[1.0.0beta3]: https://github.com/puddletag/puddletag/compare/1.0.0beta2...1.0.0beta3
[1.0.0beta2]: https://github.com/puddletag/puddletag/compare/1.0.0beta1...1.0.0beta2
[1.0.0beta1]: https://github.com/puddletag/puddletag/tree/1.0.0beta1
