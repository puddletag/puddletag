"""Shared test setup.

puddlestuff fixes its config locations at import time (constants.py,
tagsources/__init__.py, the default argument of puddleobjects.winsettings), so
HOME and the XDG dirs are redirected here, when pytest imports this conftest
and before any test module imports puddlestuff.
"""
import atexit
import os
import shutil
import socket
import subprocess
import tempfile
from collections import defaultdict, deque

import mutagen
import pytest

_SANDBOX = os.path.realpath(tempfile.mkdtemp(prefix='puddletag-tests-'))
# atexit rather than a pytest hook, so the dir also goes when this conftest
# fails to import.
atexit.register(shutil.rmtree, _SANDBOX, ignore_errors=True)
_HOME = os.path.join(_SANDBOX, 'home')
os.environ['HOME'] = _HOME
os.environ['XDG_CONFIG_HOME'] = os.path.join(_HOME, '.config')
os.environ['XDG_DATA_HOME'] = os.path.join(_HOME, '.local', 'share')
os.environ['XDG_CACHE_HOME'] = os.path.join(_HOME, '.cache')
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtCore import pyqtSignal  # noqa: E402
from PyQt6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox  # noqa: E402

import puddlestuff.resource  # noqa: E402,F401  registers the data:/icons: search paths
from puddlestuff import constants  # noqa: E402

for _path in (constants.CONFIGDIR, constants.SAVEDIR):
    if not _path.startswith(_SANDBOX + os.sep):
        raise RuntimeError(f'refusing to run: {_path} is outside the test sandbox')


@pytest.fixture(scope='session')
def sandbox_root():
    return _SANDBOX


# Modal dialogs ---------------------------------------------------------------

_MODAL_FUNCTIONS = {
    QMessageBox: ('question', 'warning', 'critical', 'information', 'about', 'exec'),
    QDialog: ('exec',),
    QFileDialog: ('getOpenFileName', 'getOpenFileNames', 'getSaveFileName',
                  'getExistingDirectory'),
    QInputDialog: ('getText', 'getMultiLineText', 'getItem', 'getInt', 'getDouble'),
}


class ModalDialogs:
    """Stands in for every modal Qt dialog during a test.

    A test queues the answer a dialog should return, e.g.
    ``dialogs.answer('QMessageBox.question', QMessageBox.StandardButton.Yes)``.
    A dialog with no queued answer raises, and is also recorded in
    ``unexpected`` so the test still fails if puddletag swallows the exception
    in one of its bare ``except:`` blocks.
    """

    def __init__(self):
        self.calls = []
        self.unexpected = []
        self._answers = defaultdict(deque)

    def answer(self, name, *values):
        self._answers[name].extend(values)

    def unused_answers(self):
        return {name: list(values) for name, values in self._answers.items() if values}

    def _stub(self, name):
        def stub(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            if not self._answers[name]:
                self.unexpected.append((name, args))
                raise AssertionError(f'unexpected modal dialog {name}{args!r}')
            return self._answers[name].popleft()
        return stub


@pytest.fixture(autouse=True)
def dialogs(monkeypatch):
    guard = ModalDialogs()
    for cls, names in _MODAL_FUNCTIONS.items():
        for name in names:
            monkeypatch.setattr(cls, name, guard._stub(f'{cls.__name__}.{name}'))
    yield guard
    if guard.unexpected:
        pytest.fail(f'unexpected modal dialogs: {guard.unexpected!r}')
    if guard.unused_answers():
        pytest.fail(f'queued dialog answers never used: {guard.unused_answers()!r}')


# Network ---------------------------------------------------------------------

class NetworkBlockedError(OSError):
    pass


_LOCAL_HOSTS = {None, 'localhost', '127.0.0.1', '::1'}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Blocks DNS lookups and connections to anything but local sockets.

    Attempts raise NetworkBlockedError, an OSError, so puddletag takes its
    usual network-failure path, and are recorded in the returned list so the
    test fails even when that path swallows the error.
    """
    attempts = []
    real_getaddrinfo = socket.getaddrinfo
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def getaddrinfo(host, *args, **kwargs):
        if host not in _LOCAL_HOSTS:
            attempts.append(('getaddrinfo', host))
            raise NetworkBlockedError(f'network access blocked in tests: {host!r}')
        return real_getaddrinfo(host, *args, **kwargs)

    def guard(real):
        def connect(sock, address):
            if sock.family == socket.AF_UNIX or address[0] in _LOCAL_HOSTS:
                return real(sock, address)
            attempts.append(('connect', address))
            raise NetworkBlockedError(f'network access blocked in tests: {address!r}')
        return connect

    monkeypatch.setattr(socket, 'getaddrinfo', getaddrinfo)
    monkeypatch.setattr(socket.socket, 'connect', guard(real_connect))
    monkeypatch.setattr(socket.socket, 'connect_ex', guard(real_connect_ex))
    yield attempts
    if attempts:
        pytest.fail(f'network access attempted: {attempts!r}')


# Synthetic audio -------------------------------------------------------------

_CODECS = {
    'mp3': 'libmp3lame',
    'm4a': 'aac',
    'ogg': 'libvorbis',
    'flac': 'flac',
    'wv': 'wavpack',
    'wma': 'wmav2',
}

# mutagen's "easy" interface takes the plain field names for MP3, MP4, FLAC
# and Ogg; ASF and APEv2 need their native keys.
_NATIVE_KEYS = {
    'wma': {'artist': 'Author', 'title': 'Title', 'album': 'WM/AlbumTitle',
            'tracknumber': 'WM/TrackNumber'},
    'wv': {'artist': 'Artist', 'title': 'Title', 'album': 'Album',
           'tracknumber': 'Track'},
}


def _missing(reason):
    if os.environ.get('CI'):  # set by GitHub Actions; CI must not skip these
        pytest.fail(reason)
    pytest.skip(reason)


def _ffmpeg_encoders():
    """Names of the encoders this ffmpeg was built with. Builds differ: some
    leave out libvorbis or libmp3lame."""
    listing = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'],
                             capture_output=True, text=True, check=True).stdout
    # A legend, a "------" line, then one encoder per line:
    # " A....D flac                 FLAC (Free Lossless Audio Codec)"
    encoders = listing.split('------', 1)[1]
    return {line.split()[1] for line in encoders.splitlines() if line.strip()}


@pytest.fixture
def make_audio(tmp_path):
    """Return a factory for synthetic audio files.

    Synthetic: one second of silence encoded by ffmpeg, carrying only the
    tags the test passes. The tags are written with mutagen rather than
    ffmpeg's -metadata, because ffmpeg's ASF muxer writes Author twice and
    adds a second, lowercase title. Musepack (.mpc) and Monkey's Audio (.ape)
    can't be made this way: ffmpeg has no encoder for them.
    """
    if shutil.which('ffmpeg') is None:
        _missing('ffmpeg is not installed')

    def make(name, directory=None, **tags):
        path = (directory or tmp_path) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        ext = path.suffix[1:]
        codec = _CODECS[ext]
        if codec not in _ffmpeg_encoders():
            _missing(f'ffmpeg has no {codec} encoder')
        subprocess.run(
            ['ffmpeg', '-nostdin', '-loglevel', 'error',
             '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', '1',
             '-map_metadata', '-1', '-fflags', '+bitexact', '-flags:a', '+bitexact',
             '-c:a', codec, str(path)],
            check=True)

        audio = mutagen.File(path, easy=True)
        if audio.tags is None:
            audio.add_tags()
        audio.tags.clear()  # libvorbis adds an encoder tag even with +bitexact
        keys = _NATIVE_KEYS.get(ext, {})
        for key, value in tags.items():
            audio[keys.get(key, key)] = value
        audio.save()
        return path

    return make


# Main window -----------------------------------------------------------------

@pytest.fixture(scope='session')
def _translated_strings():
    from puddlestuff import puddleobjects
    constants.trans_strings()
    puddleobjects.trans_imagetypes()


@pytest.fixture
def clean_profile():
    """Empty config and data dirs, as on a fresh install.

    In the app the launcher's migrate_settings() creates these dirs, and
    MainWin fails without them.
    """
    for path in (constants.CONFIGDIR, constants.SAVEDIR):
        shutil.rmtree(path, ignore_errors=True)
        os.makedirs(path)


def _module_emitters():
    """QObjects created at import time that MainWin wires to its own widgets.

    The app only ever builds one MainWin, so it never disconnects them. A
    second MainWin in the same test process would leave them calling into
    the first window's deleted QActions (mainwin/funcs.py connect_status).
    """
    from puddlestuff import tagsources
    from puddlestuff.mainwin import funcs, previews
    from puddlestuff.masstag import dialogs as masstag_dialogs
    return [funcs.obj, previews.obj, masstag_dialogs.status_obj, tagsources.status_obj]


def _disconnect_all(qobject):
    for name, attr in vars(type(qobject)).items():
        if isinstance(attr, pyqtSignal):
            try:
                getattr(qobject, name).disconnect()
            except TypeError:  # nothing connected
                pass


@pytest.fixture
def mainwin(qtbot, clean_profile, _translated_strings):
    from puddlestuff.puddletag import MainWin
    win = MainWin()
    qtbot.addWidget(win)
    win.show()
    yield win
    for emitter in _module_emitters():
        _disconnect_all(emitter)
