"""Builds source/tagsource.tar.gz, the docs' example tag source plugin,
from the source/tagsource_plugin folder. Run it after changing the
folder. The same files give the same archive: every entry has a fixed
date and owner.

    venv/bin/python docsrc/make_tagsource_example.py
"""
import gzip
import io
import tarfile
from pathlib import Path

SOURCE = Path(__file__).parent / 'source'
FOLDER = 'tagsource_plugin'
FILES = ['__init__.py', 'info']  # the folder's files, in the archive's order
MTIME = 1794027600  # 2026-11-07 00:00 America/New_York


def entry(name, mode, kind=tarfile.REGTYPE):
    info = tarfile.TarInfo(name)
    info.mtime = MTIME
    info.uid = info.gid = 0
    info.uname = info.gname = ''
    info.mode = mode
    info.type = kind
    return info


def tar_bytes():
    """The uncompressed archive: the folder, then FILES."""
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        archive.addfile(entry(FOLDER, 0o755, tarfile.DIRTYPE))
        for name in FILES:
            data = (SOURCE / FOLDER / name).read_bytes()
            info = entry(f'{FOLDER}/{name}', 0o644)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return out.getvalue()


def main():
    with open(SOURCE / 'tagsource.tar.gz', 'wb') as out:
        with gzip.GzipFile(filename='', mode='wb', fileobj=out, mtime=0) as packed:
            packed.write(tar_bytes())


if __name__ == '__main__':
    main()
