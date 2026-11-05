"""Record the AcoustID reply tests/unit/test_acoustid.py serves from a local
web server: the lookup puddletag sends for the Musopen Canon in F minor,
the recording of tests/data/musopen-canon.*, fingerprinted whole. README.md
gives the address and the license. Needs network access and fpcalc; the
tests never run it.

    venv/bin/python tests/data/record_acoustid.py
"""
import json
import tempfile
import urllib.request
from pathlib import Path

import acoustid

OUT = Path(__file__).parent / 'acoustid' / 'lookup-canon.json'
SOURCE = 'https://archive.org/download/musopen-chopin/Canon%20in%20F%20minor.mp3'
# puddletag's application key and what it asks for (tagsources/acoust_id.py).
API_KEY = 'gT8GJxhO'
META = 'releases recordings tracks'


def main():
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'canon.mp3'
        urllib.request.urlretrieve(SOURCE, path)
        duration, fingerprint = acoustid.fingerprint_file(str(path), force_fpcalc=True)
    lookup = acoustid.lookup(API_KEY, fingerprint, duration, META, timeout=60)
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open('w', encoding='utf-8') as out:
        json.dump(lookup, out, indent=1, sort_keys=True)


if __name__ == '__main__':
    main()
