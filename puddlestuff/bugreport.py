"""The problem report: what puddletag fills in, shown for review before it
goes to the issue form on GitHub (.github/ISSUE_TEMPLATE/bug_report.yaml)."""
import getpass
import os
import platform
import re
import socket
import urllib.parse

from PyQt6.QtCore import QT_TRANSLATE_NOOP, Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                             QPushButton, QVBoxLayout)

from . import changeset, steps, version_string
from .about import versions
from .puddleobjects import PuddleConfig
from .translations import translate

FORM = 'https://github.com/puddletag/puddletag/issues/new'

# GitHub documents no limit; VS Code's issue reporter uses this one.
MAX_URL_LENGTH = 7500

TITLE_LENGTH = 100

# The form's field ids, in the order the window shows them, with the labels
# the form gives them.
FIELDS = (('title', QT_TRANSLATE_NOOP('Bug Report', 'Title')),
          ('current', QT_TRANSLATE_NOOP('Bug Report', 'Current Behavior')),
          ('reproduce', QT_TRANSLATE_NOOP('Bug Report', 'Steps To Reproduce')),
          ('system', QT_TRANSLATE_NOOP('Bug Report', 'Information about your system')))

STEPS_HEADER = 'puddletag recorded these steps, oldest first:'

FRAMES_LEFT_OUT = '  [... {} frames left out ...]'


def get_os():
    """Returns a string describing the underlying operating system."""

    def osrelease_dict_to_str(osrel):
        """Returns a pretty string from the given os-release dict."""
        # First try: The PRETTY_NAME usually already includes a version
        if 'PRETTY_NAME' in osrel:
            return osrel['PRETTY_NAME']

        # Second try: Combine name and version
        name = next((osrel[k] for k in ['NAME', 'ID'] if k in osrel), 'Linux')
        version = next((osrel[k] for k in ['VERSION', 'VERSION_ID', 'VERSION_CODENAME'] if k in osrel), '')
        return '%s %s' % (name, version)

    def get_linux_name():
        """Returns the name of the linux distribution. Hopefully."""
        # First try: The optional distro package (should always work if available)
        try:
            import distro
        except ImportError:
            pass
        else:
            return distro.name(True)

        # Second try: the function in platform
        try:
            return osrelease_dict_to_str(platform.freedesktop_os_release())
        except OSError:
            pass

        # We tried hard, but it wasn't enough.
        return None

    if 'Linux' == platform.system():
        result = get_linux_name()
        if result:
            return result
        # else fall through to the fallback
    if 'Windows' == platform.system():
        win_info = platform.win32_ver()
        return 'Windows %s' % (win_info[0])
    if 'Darwin' == platform.system():
        return 'macOS %s' % (platform.mac_ver()[0])

    # In case of emergency, hope for the best
    return '%s %s %s' % (platform.system(), platform.release(), platform.version())


def get_display_server():
    """Returns a string describing the display server."""
    display_server = QApplication.instance().platformName()
    if display_server == 'xcb':
        # only a heuristic, but still better than nothing
        if os.environ.get('XDG_SESSION_TYPE') == 'wayland' or os.environ.get('WAYLAND_DISPLAY'):
            return 'xwayland'
        else:
            return 'x11'
    if display_server:
        return display_server
    return 'unknown'


def get_desktop_environment():
    """Returns a string describing the desktop environment."""
    for env_var in ('XDG_CURRENT_DESKTOP', 'XDG_SESSION_DESKTOP'):
        if os.environ.get(env_var):
            return os.environ[env_var]
    return 'unknown'


def system_info():
    """The lines of the form's system field."""
    puddletag_version = version_string
    if changeset:
        puddletag_version = f'{puddletag_version} ({changeset})'
    system_list = [
        ('Puddletag', puddletag_version),
        ('OS', get_os().strip()),
        ('Display Server', get_display_server().strip()),
        ('Desktop Environment', get_desktop_environment().strip()),
        *versions().items(),
    ]
    return '\n'.join(f'{name}: {value}' for name, value in system_list)


QUERY_SECRETS = ('access_token', 'api_key', 'apikey', 'client', 'client_id', 'key', 'password', 'secret', 'sig',
                 'signature', 'token', 'user', 'username')


def tagsource_keys():
    """The tag sources' settings that look like keys: strings of 8 or more
    characters without whitespace, in any section and language."""
    from .mainwin.tagsources import TAGSOURCE_CONFIG
    keys = set()
    for section in PuddleConfig(TAGSOURCE_CONFIG).data.values():
        if isinstance(section, dict):
            keys.update(value for value in section.values()
                        if isinstance(value, str) and len(value) >= 8 and not re.search(r'\s', value))
    return sorted(keys, key=len, reverse=True)


def sanitize(text):
    """The text without what identifies the user or opens their accounts:
    tag source keys, home folder, user and host names, e-mail addresses and
    key-like address parameters. Music file paths stay (after the home
    folder is cut): a name that breaks puddletag is often the bug."""
    for key in tagsource_keys():
        text = text.replace(key, '<key>')

    home = os.path.expanduser('~')
    for folder in dict.fromkeys((home, os.path.realpath(home))):
        if folder not in ('', '/'):
            text = text.replace(folder, '~')

    names = [(getpass.getuser(), '<user>')]
    host = socket.gethostname()
    names += [(host, '<host>'), (host.split('.')[0], '<host>')]
    for name, placeholder in names:
        if len(name) >= 3:
            text = re.sub(rf'\b{re.escape(name)}\b', placeholder, text)

    text = re.sub(r'[\w.+-]+@[\w-]+(\.[\w-]+)+', '<email>', text)

    text = re.sub(rf'([?&](?:{"|".join(QUERY_SECRETS)})=)[^&\s#]*', r'\1<removed>', text, flags=re.IGNORECASE)
    text = re.sub(r'(?im)^(\s*Authorization:).*$', r'\1 <removed>', text)
    text = re.sub(r'(Discogs token=)\S+', r'\1<removed>', text)
    return text


def address(fields):
    """The issue form's address with these fields (by id), leaving out the
    empty ones."""
    params = {'labels': 'bug', 'template': 'bug_report.yaml',
              **{name: text for name, text in fields.items() if text.strip()}}
    return f'{FORM}?{urllib.parse.urlencode(params)}'


def full_text(fields):
    """The report as one text, for the clipboard."""
    parts = [f'# {fields["title"]}'] if fields.get('title', '').strip() else []
    parts += [f'### {label}\n\n{fields[name]}' for name, label in FIELDS
              if name != 'title' and fields.get(name, '').strip()]
    return '\n\n'.join(parts)


def drop_oldest_step(steps):
    """The steps text without its oldest step, renumbered; empty once no step
    is left."""
    lines = steps.splitlines()
    kept = [re.sub(r'^\d+\. ', '', line) for line in lines[2:]]
    if not kept:
        return ''
    return '\n'.join([lines[0]] + [f'{n}. {line}' for n, line in enumerate(kept, 1)])


def trim_traceback(details, left_out):
    """The traceback without `left_out` frames from its middle (the first
    frame and the last three stay), with a marker where they were."""
    lines = details.splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith('  File ')]
    header = max((i for i, line in enumerate(lines) if line == 'Traceback (most recent call last):'), default=None)
    if header is None:
        return details
    starts = [i for i in starts if i > header]
    end = starts[-1] + 1 if starts else len(lines)
    while end < len(lines) and lines[end].startswith('    '):
        end += 1
    frames = [lines[a:b] for a, b in zip(starts, starts[1:] + [end])]
    if left_out < 1 or len(frames) - left_out < 4:
        return details
    first = 1 + (len(frames) - 4 - left_out) // 2
    kept = (frames[:first] + [[FRAMES_LEFT_OUT.format(left_out)]]
            + frames[first + left_out:])
    out = lines[:header + 1] + [line for frame in kept for line in frame] + lines[end:]
    return '\n'.join(out) + ('\n' if details.endswith('\n') else '')


def error_current(details):
    return f'puddletag showed this error:\n\n```\n{details}\n```'


def fit(fields, details=None):
    """The fields trimmed until the address fits: the oldest steps go
    first, then the middle of the error's traceback."""
    fields = dict(fields)
    while len(address(fields)) > MAX_URL_LENGTH and fields['reproduce']:
        fields['reproduce'] = drop_oldest_step(fields['reproduce'])
    if details is not None:
        left_out = 0
        while len(address(fields)) > MAX_URL_LENGTH:
            left_out += 1
            trimmed = trim_traceback(details, left_out)
            if trimmed == details:
                break
            fields['current'] = error_current(sanitize(trimmed.rstrip('\n')))
    return fields


class ReviewWindow(QDialog):
    """The report in editable boxes, shown before anything goes to GitHub."""

    def __init__(self, parent, fields):
        super().__init__(parent)
        self.setWindowTitle(translate('Bug Report', 'Report a problem'))
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(640, 640)

        self._boxes = {}
        layout = QVBoxLayout(self)
        for name, label in FIELDS:
            layout.addWidget(QLabel(translate('Bug Report', label)))
            if name == 'title':
                box = QLineEdit(fields[name])
            else:
                box = QPlainTextEdit(fields[name])
            self._boxes[label] = box
            layout.addWidget(box, 0 if name == 'title' else 1)

        self._open = QPushButton(translate('Bug Report', 'Open on GitHub'))
        self._open.setDefault(True)
        self._open.clicked.connect(self._open_on_github)
        copy = QPushButton(translate('Bug Report', '&Copy'))
        copy.setAutoDefault(False)
        copy.clicked.connect(self._copy)
        cancel = QPushButton(translate('Bug Report', 'Cancel'))
        cancel.setAutoDefault(False)
        cancel.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        for button in (self._open, copy, cancel):
            buttons.addWidget(button)
        layout.addLayout(buttons)

    def field(self, label):
        """The box under this label (the form's labels)."""
        return self._boxes[label]

    def _fields(self):
        return {name: self._boxes[label].text() if name == 'title' else self._boxes[label].toPlainText()
                for name, label in FIELDS}

    def _copy(self):
        QApplication.clipboard().setText(full_text(self._fields()))

    def _open_on_github(self):
        fields = self._fields()
        url = address(fields)
        if len(url) > MAX_URL_LENGTH:
            QApplication.clipboard().setText(full_text(fields))
            note = translate('Bug Report', 'The report was too long for the address, so puddletag put it on '
                                           'the clipboard: paste it here.')
            url = address({'title': fields['title'], 'current': note, 'system': fields['system']})
            QMessageBox.information(
                self.parent(), 'puddletag',
                translate('Bug Report', 'The report is too long to send in the address, so puddletag put it on '
                                        'the clipboard: paste it into the issue.'))
        QDesktopServices.openUrl(QUrl(url))
        self.close()


# Windows with no parent would be collected as soon as the function returns.
_windows = []


def _show(parent, fields):
    window = ReviewWindow(parent, fields)
    _windows.append(window)
    window.finished.connect(lambda: _windows.remove(window))
    window.show()


def steps_text():
    """The recorded steps as the Steps field's text; empty when there are none."""
    recent = steps.recent()
    if not recent:
        return ''
    return '\n'.join([STEPS_HEADER] + [f'{n}. {step}' for n, step in enumerate(recent, 1)])


def report_problem(parent=None):
    """Help > Report a problem: the review window with the system filled in."""
    fields = {'title': '', 'current': '', 'reproduce': sanitize(steps_text()), 'system': sanitize(system_info())}
    _show(parent, fit(fields))


def report_error(parent, summary, details):
    """The error report: the review window with the error and the system
    filled in."""
    fields = {'title': sanitize(summary)[:TITLE_LENGTH],
              'current': error_current(sanitize(details.rstrip('\n'))),
              'reproduce': sanitize(steps_text()),
              'system': sanitize(system_info())}
    _show(parent, fit(fields, details))
