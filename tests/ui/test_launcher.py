"""The puddletag launcher run as a user runs it: the puddletag script with
command-line options, in a process of its own on the test profile (conftest
points HOME and the XDG folders at the test sandbox, and Qt draws
offscreen). The man page (puddletag.1) documents the options. A start that
opens the window goes through a wrapper that ends the event loop once the
window is up and prints what it shows. Synthetic files and settings.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from puddlestuff import loadshortcuts, version_string
from puddlestuff.puddleobjects import PuddleConfig

pytestmark = pytest.mark.ui

ROOT = Path(__file__).parents[2]
LAUNCHER = str(ROOT / 'puddletag')

# Runs the launcher as __main__ with QApplication.exec replaced: once the
# window is up and holds ROWS rows, it prints what the window shows as one
# JSON line and returns 0 instead of waiting for the user.
WRAPPER = '''import json, os, runpy, sys, time
sys.path.insert(0, {root!r})
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication


def shown(self=None):
    from puddlestuff.puddletag import status
    model = status['model']
    end = time.monotonic() + 20
    while model.rowCount() < int(os.environ['ROWS']) and time.monotonic() < end:
        QApplication.processEvents()
    font = model.data(model.index(0, 0), Qt.ItemDataRole.FontRole) if model.rowCount() else None
    print('SHOWN ' + json.dumps({{
        'app_font': QApplication.font().pointSize(),
        'direction': QApplication.layoutDirection().name,
        'file_menu': QApplication.translate('Menus', '&File'),
        'files': [audio.filepath for audio in model.taginfo],
        'table_font': font.pointSize() if font else None,
        'title': status['mainwin'].windowTitle(),
        'translators': [os.path.basename(t.filePath()) for t in sys.modules['__main__'].translators],
    }}))
    status['mainwin'].close()
    return 0


if os.environ.get('SLOW_THREADS'):
    import puddlestuff.resource
    from puddlestuff.puddleobjects import PuddleThread
    run_thread = PuddleThread.run

    def slow_run(self):
        time.sleep(float(os.environ['SLOW_THREADS']))
        run_thread(self)

    PuddleThread.run = slow_run

QApplication.exec = shown
sys.argv = [{launcher!r}] + sys.argv[1:]
runpy.run_path({launcher!r}, run_name='__main__')
'''


@pytest.fixture(autouse=True)
def fresh_profile(clean_profile):
    """Each run starts on an empty profile."""


def run(*args, env=None):
    """The launcher with these arguments, run to its end."""
    return subprocess.run([sys.executable, LAUNCHER, *args], capture_output=True, text=True,
                          timeout=60, env=env)


def start(tmp_path, *args, rows=0, env=None):
    """Starts puddletag with these arguments and returns (what its window
    shows once it holds rows rows, the launcher's stdout): see WRAPPER."""
    wrapper = tmp_path / 'wrapper.py'
    wrapper.write_text(WRAPPER.format(root=str(ROOT), launcher=LAUNCHER))
    env = dict(os.environ if env is None else env, ROWS=str(rows))
    result = subprocess.run([sys.executable, str(wrapper), *args], capture_output=True, text=True,
                            timeout=60, env=env)
    assert result.returncode == 0, result.stderr
    [line] = [line for line in result.stdout.splitlines() if line.startswith('SHOWN ')]
    return json.loads(line[len('SHOWN '):]), result.stdout


def locale_env(**variables):
    """The environment with its locale variables replaced by these.
    Synthetic locales."""
    env = {key: value for key, value in os.environ.items() if not key.startswith(('LANG', 'LC_'))}
    return dict(env, **variables)


def window_built():
    """Building the main window writes the shortcuts file into the config
    folder, which fresh_profile emptied."""
    return os.path.exists(loadshortcuts.shortcut_path)


@pytest.mark.parametrize('option', ['--version', '-v'])
def test_version_is_printed_without_a_window(option):
    # The man page doesn't list it; this is what puddletag does.
    result = run(option)
    assert result.returncode == 0
    assert result.stdout.startswith(f'puddletag Version: {version_string}')
    assert not window_built()


def test_help_lists_the_options():
    # puddletag.1: "-h, --help  Show help message and exit." and the options
    # --langfile=LANGFILE, --fontsize=FONTSIZE and -d, --debug.
    result = run('--help')
    assert result.returncode == 0
    for option in ('-d, --debug', '--fontsize=FONTSIZE', '-h, --help', '--langfile=LANGFILE'):
        assert option in result.stdout
    assert not window_built()


def test_paths_given_are_loaded(make_audio, tmp_path):
    # puddletag.1: "file/directory paths... Paths to any files or directories
    # which'll be loaded on startup."
    music = tmp_path / 'music'
    other = tmp_path / 'other'
    paths = [make_audio('01.mp3', music, title='One'), make_audio('02.mp3', music, title='Two'),
             make_audio('03.mp3', other, title='Three')]
    shown, _ = start(tmp_path, str(music), str(other / '03.mp3'), rows=3)
    assert sorted(shown['files']) == sorted(str(path) for path in paths)


@pytest.mark.xfail(strict=True, reason='quitting while the Filesystem dock is still selecting the '
                                       'folder aborts the process')
def test_quitting_while_the_filesystem_dock_selects_the_folder_exits_cleanly(make_audio, tmp_path):
    # The docs are silent: a user who quits while the Filesystem dock is
    # still selecting the folder just loaded should get a clean exit. The
    # slow threads are synthetic (SLOW_THREADS), standing in for a big
    # folder or a slow network mount.
    music = tmp_path / 'music'
    make_audio('01.mp3', music, title='One')
    env = dict(os.environ, SLOW_THREADS='1')
    shown, _ = start(tmp_path, str(music), rows=1, env=env)
    assert shown['files'] == [str(music / '01.mp3')]


def test_missing_path_stops_before_the_window(tmp_path):
    # The docs are silent on a missing path; this is what puddletag does,
    # as the maintainer decided: the message and exit code 1, without
    # building the window first.
    missing = tmp_path / 'missing'
    result = run(str(missing))
    assert result.returncode == 1
    assert result.stdout.endswith(f'Directory or file {missing} does not exist.\n')
    assert not window_built()


def test_fontsize_that_isnt_a_number_is_refused():
    # The docs are silent; this is what puddletag does.
    result = run('--fontsize', 'abc')
    assert result.returncode == 2
    assert '--fontsize' in result.stderr
    assert not window_built()


def test_fontsize_leaves_the_file_view_its_own_size(make_audio, tmp_path):
    # puddletag.1: "--fontsize=FONTSIZE Default font size to use (in points).
    # All UI elements except the file-view will use this font size, once
    # puddletag has saved the file-view's size (after its first start)."
    # Synthetic: 12 is the size an earlier session saved.
    make_audio('01.mp3', tmp_path / 'music', title='One')
    PuddleConfig().set('table', 'fontsize', 12)
    shown, _ = start(tmp_path, '--fontsize', '15', str(tmp_path / 'music'), rows=1)
    assert shown['app_font'] == 15
    assert shown['table_font'] == 12


def test_fontsize_on_a_first_start(make_audio, tmp_path):
    # puddletag.1: "All UI elements except the file-view will use this font
    # size, once puddletag has saved the file-view's size (after its first
    # start)." Before that the file-view takes the size too.
    make_audio('01.mp3', tmp_path / 'music', title='One')
    shown, _ = start(tmp_path, '--fontsize', '15', str(tmp_path / 'music'), rows=1)
    assert shown['app_font'] == 15
    assert shown['table_font'] == 15


@pytest.mark.parametrize('size', ['-inf', 'inf'])
def test_fontsize_that_is_not_a_size_keeps_the_font(make_audio, tmp_path, size):
    # puddletag.1: "--fontsize=FONTSIZE Default font size to use (in
    # points)." The docs are silent on a value that isn't a size: it is
    # handled as any invalid size is, and puddletag starts with its normal
    # font. Synthetic input.
    make_audio('01.mp3', tmp_path / 'music', title='One')
    normal, _ = start(tmp_path, str(tmp_path / 'music'), rows=1)
    shown, _ = start(tmp_path, '--fontsize', size, str(tmp_path / 'music'), rows=1)
    assert shown['app_font'] == normal['app_font']


def test_region_only_hebrew_keeps_left_to_right(tmp_path):
    # preferences.txt, Language: "<Autodetect> uses your system's language".
    # A language of English with the region set to he_IL laid the window out
    # right to left (#199). Synthetic locale variables, as a desktop's
    # region setting sets them.
    env = locale_env(LANG='en_US.UTF-8', LC_MEASUREMENT='he_IL.UTF-8',
                     LC_MONETARY='he_IL.UTF-8', LC_NUMERIC='he_IL.UTF-8',
                     LC_PAPER='he_IL.UTF-8', LC_TIME='he_IL.UTF-8')
    shown, _ = start(tmp_path, env=env)
    assert shown['direction'] == 'LeftToRight'
    assert shown['file_menu'] == '&File'


def test_autodetect_follows_a_hebrew_system(tmp_path):
    # preferences.txt, Language: "<Autodetect> uses your system's language".
    shown, _ = start(tmp_path, env=locale_env(LC_ALL='he_IL.UTF-8'))
    assert shown['direction'] == 'RightToLeft'
    assert 'qt_he.qm' in shown['translators']


def test_default_language_is_english(tmp_path):
    # preferences.txt, Language: "Default is English".
    PuddleConfig().set('main', 'lang', 'default')
    shown, _ = start(tmp_path, env=locale_env(LC_ALL='he_IL.UTF-8'))
    assert shown['direction'] == 'LeftToRight'
    assert shown['translators'] == []


def test_langfile_translates_puddletag(tmp_path):
    # translate.txt: "Otherwise just run: puddletag --langfile
    # /path/to/your_locale.qm"; puddletag.1: "If valid, this file'll be used
    # to translate puddletag."
    qm = ROOT / 'puddlestuff' / 'translations' / 'puddletag_de.qm'
    shown, _ = start(tmp_path, '--langfile', str(qm))
    assert 'puddletag_de.qm' in shown['translators']
    assert shown['file_menu'] != '&File'


def test_langfile_that_isnt_qm_keeps_the_chosen_language(tmp_path):
    # puddletag.1: "Path to a translation (.qm) file. If valid, this
    # file'll be used to translate puddletag. Otherwise the last translation
    # chosen will be used." Synthetic: French chosen in Preferences.
    PuddleConfig().set('main', 'lang', 'fr')
    bad = tmp_path / 'x.txt'
    bad.write_text('')
    shown, stdout = start(tmp_path, '--langfile', str(bad))
    assert 'Invalid translation file.' in stdout
    assert 'puddletag_fr.qm' in shown['translators']


def test_langfile_that_doesnt_load_keeps_the_chosen_language(tmp_path):
    # puddletag.1: "Path to a translation (.qm) file. If valid, this
    # file'll be used to translate puddletag. Otherwise the last translation
    # chosen will be used." Synthetic: French chosen in Preferences.
    PuddleConfig().set('main', 'lang', 'fr')
    shown, stdout = start(tmp_path, '--langfile', str(tmp_path / 'missing.qm'))
    assert 'Invalid translation file.' in stdout
    assert 'puddletag_fr.qm' in shown['translators']
