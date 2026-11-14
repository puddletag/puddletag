"""Playlists read and written in UTF-8 whatever the system's locale: m3u
run in a fresh interpreter whose default encoding is ASCII, as open() is
on a system whose locale isn't UTF-8. Synthetic playlists.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# PYTHONUTF8=0 also turns off Python 3.15's UTF-8 mode; without
# PYTHONCOERCECLOCALE=0 the C locale would become C.UTF-8.
ASCII_LOCALE = {'LANG': 'C', 'LC_ALL': 'C', 'PYTHONCOERCECLOCALE': '0', 'PYTHONUTF8': '0'}


def run_m3u(code, *args):
    """Runs code, after importing m3u, in a fresh interpreter with an ASCII
    locale; returns what it prints, read as JSON. The code and the
    arguments must be ASCII (\\u escapes for the rest)."""
    prelude = 'import json, sys; import puddlestuff.resource; from puddlestuff import m3u; '
    done = subprocess.run([sys.executable, '-c', prelude + code, *map(str, args)],
                          env={**os.environ, **ASCII_LOCALE}, cwd=ROOT,
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_reads_a_utf8_playlist_whatever_the_locale(tmp_path):
    # Docs-silent: puddletag says "The playlist is not encoded in UTF-8", so
    # it reads UTF-8.
    path = tmp_path / 'list.m3u'
    path.write_bytes('#EXTM3U\nmúsica/01.mp3\n'.encode('utf-8'))
    assert run_m3u('print(json.dumps(m3u.readm3u(sys.argv[1])))', path) == [
        str(tmp_path / 'música' / '01.mp3')]


def test_writes_a_utf8_playlist_whatever_the_locale(tmp_path):
    # Docs-silent: the playlist is read as UTF-8, so it is written as UTF-8.
    # A SimpleNamespace stands in for a tag: without a pattern exportm3u reads
    # only its filepath.
    out = tmp_path / 'out.m3u'
    run_m3u("from types import SimpleNamespace; "
            "m3u.exportm3u([SimpleNamespace(filepath='/m\\u00fasica/01.mp3')], sys.argv[1]); "
            "print('null')", out)
    assert out.read_bytes() == '#EXTM3U\n/música/01.mp3'.encode('utf-8')
