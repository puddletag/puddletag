**WARNING**: this is a development branch to update puddletag to PyQt5 and Python3; expect bugs, if so report them in the issues session of github.

# puddletag

puddletag is an audio tag editor (primarily created) for GNU/Linux similar to the Windows program, Mp3tag. Unlike most taggers for GNU/Linux, it uses a spreadsheet-like layout so that all the tags you want to edit by hand are visible and easily editable.


## Contents
 1. [About](#1-about)
 2. [License](#2-license)
 3. [Prerequisites](#3-prerequisites)
 4. [Installation](#4-installation)
 5. [Support](#5-support)

***

## 1. About

puddletag is an audio tag editor (primarily created) for GNU/Linux similar to the Windows program, Mp3tag. Unlike most taggers for GNU/Linux, it uses a spreadsheet-like layout so that all the tags you want to edit by hand are visible and easily editable.  

The usual tag editor features are supported like extracting tag information from filenames, renaming files based on their tags by using patterns and basic tag editing.  

*Note*: Not all functions are implemented yet for this fork.  

There are also Functions, which can do things like replace text, trim it, do case conversions, etc. Actions can automate repetitive tasks. Doing web lookups using Amazon (including cover art), Discogs (does cover art too!), FreeDB and MusicBrainz is also supported. There’s quite a bit more, but I’ve reached my comma quota.  

Supported formats: ID3v1, ID3v2 (mp3), MP4 (mp4, m4a, etc.), VorbisComments (ogg, flac), Musepack (mpc), Monkey’s Audio (.ape) and WavPack (wv).  

This is a fork of the [original](https://github.com/keithgg/puddletag) which incorporates PyQt5 and Python 3 (Python 2 support has been dropped).

## 2. License

`puddletag` is licensed under the GPLv3, which you can find in its entirety at  [http://www.gnu.org/licenses/gpl-3.0.html](http://www.gnu.org/licenses/gpl-3.0.html)  

## 3. Prerequisites  

* [Python3](https://www.python.org/)  
* [configobj](https://pypi.org/project/configobj/)
* [pyparsing](https://pypi.org/project/pyparsing/)  
* [PyQt5](https://pypi.org/project/pyqt5/)  
* [Mutagen](https://pypi.org/project/mutagen/)  

On Debian, you can install all prerequisites with the command:  

`apt-get install python3 python3-mutagen python3-configobj python3-pyparsing python3-pyqt5 python3-pyqt5.qtsvg`

The package names may be different in different distributions.  

## 4. Installation

After installing the dependencies above:  


```
git clone https://github.com/sandrotosi/puddletag
cd puddletag
PYTHONPATH=source/ ./source/puddletag
```


## 5. Support

Please use [Github issues](https://github.com/sandrotosi/puddletag/issues).  
