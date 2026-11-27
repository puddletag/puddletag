"""Every picture the docs show is one docs/make_screenshots.py makes,
and the docs keep no other picture."""
import importlib.util
import posixpath
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / 'docs'

NOT_DOCS = {'_build', '_static', '_templates'}
PICTURE_SUFFIXES = {'.gif', '.jpeg', '.jpg', '.png', '.svg'}
README_PICTURE = re.compile(
    r'raw\.githubusercontent\.com/puddletag/puddletag/master/docs/(\S+?\.png)')


def docs_files(pattern):
    return [path for path in DOCS.rglob(pattern)
            if not NOT_DOCS & set(path.relative_to(DOCS).parts)]


def pictures():
    spec = importlib.util.spec_from_file_location(
        'make_screenshots', DOCS / 'make_screenshots.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return sorted(module.PICTURES)


def shown():
    found = []
    for page in docs_files('*.txt'):
        folder = page.parent.relative_to(DOCS).as_posix()
        for name in re.findall(r'image::\s+(\S+)', page.read_text('utf-8')):
            found.append(posixpath.normpath(posixpath.join(folder, name)))
    readme = (ROOT / 'README.md').read_text('utf-8')
    found.extend(README_PICTURE.findall(readme))
    return found


def on_disk():
    return [path.relative_to(DOCS).as_posix() for path in docs_files('*')
            if path.suffix in PICTURE_SUFFIXES]


def test_every_picture_a_page_shows_is_made():
    # Synthetic: the docs are silent on how their pictures are made.
    assert sorted(set(shown()) - set(pictures())) == []


def test_every_picture_made_is_shown():
    # Synthetic, as above.
    assert sorted(set(pictures()) - set(shown())) == []


def test_docs_keep_no_other_picture():
    # Synthetic, as above.
    assert sorted(set(on_disk()) - set(pictures())) == []
