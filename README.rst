What it is
=========
puddletag is an audio tag editor (primarily created) for GNU/Linux similar to the Windows program, Mp3tag. Unlike most taggers for GNU/Linux, it uses a spreadsheet-like layout so that all the tags you want to edit by hand are visible and easily editable.

The usual tag editor features are supported like extracting tag information from filenames, renaming files based on their tags by using patterns and basic tag editing.

Then there’re Functions, which can do things like replace text, trim it, do case conversions, etc. Actions can automate repetitive tasks. Doing web lookups using Amazon (including cover art), Discogs (does cover art too!), FreeDB and MusicBrainz is also supported. There’s quite a bit more, but I’ve reached my comma quota.

Supported formats: ID3v1, ID3v2 (mp3), MP4 (mp4, m4a, etc.), VorbisComments (ogg, flac), Musepack (mpc), Monkey’s Audio (.ape) and WavPack (wv).

Why it is
=========
Keeping an XP partition just for Mp3tag just wasn't feasible anymore.

How it's different
==================
To Mp3tag it’s not that different. Mp3tag has things puddletag doesn’t have, puddletag has things Mp3tag doesn’t. Skim the menus section to get an overview of the differences.

However, compared to other GNU/Linux taggers the differences are much too vast to list.

What you need
=============

- At least Python2.5 (not Python3) available from http://python.org.
- PyQt4 (4.5 or greater) (http://www.riverbankcomputing.co.uk/software/pyqt/intro) for the GUI.
- PyParsing (1.5.1 or greater) (http://pyparsing.wikispaces.com) takes care of the parsing...
- Mutagen (1.20 recommended, 1.14 required) (http://code.google.com/p/mutagen/) is used as the tagging lib and...

The following are recommended
-----------------------------

- Chromaprint (≥ 0.4) (http://acoustid.org/chromaprint) for AcoustID support.

Downloading/Installing
======================

From source:

- Install the dependencies listed above.
- For Debian-based distros, run the following as root to install them aptitude install python-qt4 python-pyparsing python-mutagen python-configobj python-musicbrainz2 python-imaging
- Download the source tarball from http://puddletag.sourceforge.net. (If this file came from that tarball, ignore everything on this line.)
- Unzip it.
- You can run puddletag from that directory by typing ./puddletag in your console.
- Alternatively, install it by running python setup.py install as root in the unzipped directory.
- puddletag should appear in your Multimedia (or Sounds etc.) menu. If not run 'desktop-file-install puddletag.desktop' as root in the unzipped directory.


Installing from the Debian package.
-----------------------------------

- This package has been created on and for Ubuntu 10.04, but has been reported to work on Ubuntu 10.10, Sabayon and Debian Squeeze.
- Download the package from http://puddletag.sourceforge.net.
- Install using your distros preferred method (usually double clicking should suffice). Or:
- Run as root dpkg -i /path/to/puddletag-deb.
- Install dependencies using your favourite tool.
- puddletag will appear under your Multimedia menu


Installing from Homebrew on Mac OS X.
-------------------------------------

- This package can be installed on MacOS X via the Homebrew package manager.
- Install the package manager from http://brew.sh
- Download and install puddletag by typing "brew install puddletag" in your console


License
=======
puddletag licensed under the GPLv3, which you can find in its entirety at http://www.gnu.org/licenses/gpl-3.0.html

Updates
=======
Releases are infrequent. Not more than a couple per year.

Support
=======

Github issues: https://github.com/keithgg/puddletag/issues
