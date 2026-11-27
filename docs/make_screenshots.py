#!/usr/bin/env python3
"""Makes the pictures the docs show, by driving puddletag offscreen.

    python docs/make_screenshots.py [--out DIR] [--list] [PICTURE ...]

A PICTURE is a path as the pages name it, relative to docs/
(``screenshots/5.png``, ``source/tut1/reload.png``); with none, every
picture is made. ``--out`` is where they go (default: next to this script,
so a bare run replaces the committed pictures); ``--list`` prints the names.

Everything shown is synthetic, made up for these pictures: the four albums
(The Silent Frames, Ada Rest, Mona Lisp and Тихие Соседи are not real
artists), their silent MP3 files (hand-written frames, so nothing here
needs ffmpeg), the covers (drawn by Qt), the text file, the actions and the
answers of the tag source. The
run happens in a throwaway profile under the temp folder: it never reads or
writes the user's own settings.

The pictures committed in the repo are made in the CI image (Ubuntu with
fonts-dejavu-core), where two runs give the same bytes. Elsewhere the fonts
and the "/" folder's content may differ.

A scene is a function ``def name(studio)`` registered with
``@scene('screenshots/1.png', ...)``, the names of the pictures it saves.
It starts with ``studio.reset()``, drives the program through ``studio``
(see ``Studio``) and saves each picture with ``studio.save(name, image)``.
"""
import argparse
import json
import math
import os
import random
import shutil
import socket
import sys
import tempfile
import traceback
import zlib
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import (QBuffer, QEvent, QIODevice, QItemSelection, QItemSelectionModel, QLocale,
                          QModelIndex, QPoint, QPointF, QRect, Qt)
from PyQt6.QtGui import (QBrush, QColor, QFont, QFontInfo, QIcon, QImage, QLinearGradient, QPainter,
                         QPainterPath, QPen, QPolygonF, QRadialGradient)
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QDialog, QDockWidget, QFileDialog,
                             QInputDialog, QMessageBox)

DOCS = Path(__file__).resolve().parent
WORK_NAME = 'puddletag-screenshots'

# What the pictures look like. A different answer to a design question is
# an edit here.
FONT_FAMILY = 'DejaVu Sans'
FONT_SIZE = 9
LAYOUT_SIZE = (1440, 900)
MAIN_SIZE = (1100, 700)
TUTORIAL_SIZE = (1100, 620)
DOCK_WIDTH = 360


@dataclass
class Album:
    artist: str
    title: str
    tracks: list  # (title, seconds)
    color: str = '#000000'
    year: str = ''
    genre: str = ''
    tagged: bool = True
    # Filename of track n; the tutorial album carries the artist.
    pattern: str = '{n:02d} - {title}.mp3'

    @property
    def folder(self):
        return f'{self.artist} - {self.title}'


NOTHING_TO_HEAR = Album(
    'The Silent Frames', 'Nothing to Hear', list(zip(
        ['Opening Hush', 'Zero Crossing', 'Room Tone', 'Noise Floor', 'Between the Notes',
         'Empty Studio', 'Mute Button', 'Low Battery', 'Rests and Pauses', 'Fade to Nothing',
         'Headroom', 'Dither', 'Last Sample'],
        [214, 187, 243, 199, 261, 176, 228, 205, 252, 191, 236, 183, 270])),
    tagged=False, pattern='The Silent Frames - {n:02d} - {title}.mp3')
LOW_LIGHT = Album(
    'Ada Rest', 'Low Light', list(zip(
        ['Small Hours', 'Night Bus', 'Porch Light', 'Kettle Song', 'Long Way Round',
         'Window Seat', 'Slow Thaw', 'Blue Hour', 'Paper Lanterns', 'Goodnight Street'],
        [201, 233, 187, 245, 212, 196, 260, 224, 189, 241])),
    color='#24476b', year='2025', genre='Folk')
WHISPER_SONGS = Album(
    'Mona Lisp', 'Whisper Songs', list(zip(
        ['Hush Now', 'Soft Spoken', 'Indoor Voice', 'Library Card', 'Tiptoe', 'Murmur',
         'Under My Breath', 'Quiet Car'],
        [182, 207, 229, 194, 216, 175, 238, 203])),
    color='#8e3b5f', year='2024', genre='Pop')
# Synthetic too: Cyrillic names, to show non-ASCII text.
NIGHT_AIR = Album(
    'Тихие Соседи', 'Ночной Эфир', tracks=[
        ('Тишина', 205), ('Шёпот', 188), ('Полночь', 231), ('Пустой Зал', 197), ('Эхо', 244),
        ('Снегопад', 176), ('Колыбельная', 219), ('Рассвет', 263)],
    color='#3d5a3d', year='2023', genre='Ambient')
ALBUMS = [LOW_LIGHT, NOTHING_TO_HEAR, WHISPER_SONGS]

# The synthetic actions of the layout picture: (name, [(function, fields, arguments)]).
LAYOUT_ACTIONS = [
    ('Album Artist from Artist', [('formatValue', ['albumartist'], ['%artist%'])]),
    ('Clean Up Spaces', [('strip', ['__all'], [])]),
    ('Lowercase Genre', [('titleCase', ['genre'], ['lower case', '., !'])]),
    ('Number Tracks Two Digits', [('formatValue', ['track'], ['$num(%track%,2)'])]),
    ('Remove Comments', [('remove_fields', ['comment'], [])]),
    ('Title Case Titles', [('titleCase', ['title'], ['Mixed Case', '., !'])])]

TEXT_FILE_LINES = [
    'Ada Rest - Small Hours', 'Mona Lisp - Hush Now', 'The Silent Frames - Room Tone',
    'DJ Placeholder - Loop One', 'Quiet Neighbours - Thin Walls', 'Ada Rest - Night Bus',
    'Low Fidelity Choir - Hum Along', 'Mona Lisp - Soft Spoken',
    'The Understudies - Second Act', 'Kite Committee - Glide']

# Every picture, as the pages name it. A picture whose scene isn't defined
# here (yet) maps to None.
PICTURES = dict.fromkeys([
    'screenshots/1.png', 'screenshots/2.png', 'screenshots/3.png', 'screenshots/4.png',
    'screenshots/5.png',
    'source/images/eg_tagsource.png', 'source/images/tagsource_dialog_tut4.png',
    'source/images/tut3_window.png',
    'source/masstag_images/choose_profile.png', 'source/masstag_images/configure_profile.png',
    'source/masstag_images/configure_tagsource.png',
    'source/tut1/1full.png', 'source/tut1/2full.png', 'source/tut1/3full.png',
    'source/tut1/4full.png', 'source/tut1/5full.png', 'source/tut1/6full.png',
    'source/tut1/actions.png', 'source/tut1/actionsbutton.png', 'source/tut1/addfolder.png',
    'source/tut1/caseaction.png', 'source/tut1/caseactionedit.png',
    'source/tut1/filetotag.png', 'source/tut1/formataction.png', 'source/tut1/functions.png',
    'source/tut1/importfile.png', 'source/tut1/importfilewindow.png',
    'source/tut1/numbering.png', 'source/tut1/parentfolder.png', 'source/tut1/quickactions.png',
    'source/tut1/reload.png', 'source/tut1/renamedir.png', 'source/tut1/tagtofile.png',
    'source/tut1/textedit.png', 'source/tut1/toolbarbuttonscomplete.png',
    'source/tut1/track.png'])
SCENES = []


def scene(*pictures):
    """Registers the decorated function as the scene making these pictures."""
    def register(func):
        unknown = [name for name in pictures if name not in PICTURES]
        assert not unknown, f'not in PICTURES: {unknown}'
        func.pictures = pictures
        SCENES.append(func)
        for name in pictures:
            PICTURES[name] = func
        return func
    return register


# Annotations -----------------------------------------------------------------

RED = QColor('#c62828')


def number(text, point, anchor='center'):
    return ('text', str(text), point, QFont(FONT_FAMILY, 14, QFont.Weight.Bold), anchor)


def label(text, point, size=12, anchor='center'):
    return ('text', text, point, QFont(FONT_FAMILY, size, QFont.Weight.Bold), anchor)


def arrow(start, end):
    return ('arrow', start, end)


def _draw_text(painter, text, point, font, anchor):
    path = QPainterPath()
    path.addText(0, 0, font, text)
    box = path.boundingRect()
    x = {'center': point.x() - box.center().x(), 'top': point.x() - box.center().x(),
         'left': point.x() - box.left(), 'right': point.x() - box.right()}[anchor]
    y = point.y() - box.top() if anchor == 'top' else point.y() - box.center().y()
    path.translate(x, y)
    pen = QPen(QColor('white'), 4)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(RED))
    painter.drawPath(path)


def _draw_arrow(painter, start, end):
    start, end = QPointF(start), QPointF(end)
    length = ((end.x() - start.x()) ** 2 + (end.y() - start.y()) ** 2) ** 0.5
    ux, uy = (end.x() - start.x()) / length, (end.y() - start.y()) / length
    base = QPointF(end.x() - 9 * ux, end.y() - 9 * uy)
    painter.setPen(QPen(RED, 2))
    painter.drawLine(start, base)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(RED))
    painter.drawPolygon(QPolygonF([end, QPointF(base.x() - 4.5 * uy, base.y() + 4.5 * ux),
                                   QPointF(base.x() + 4.5 * uy, base.y() - 4.5 * ux)]))


# Guards ----------------------------------------------------------------------

_MODAL_FUNCTIONS = {
    QDialog: ('exec',),
    QFileDialog: ('getExistingDirectory', 'getOpenFileName', 'getOpenFileNames',
                  'getSaveFileName'),
    QInputDialog: ('getDouble', 'getInt', 'getItem', 'getMultiLineText', 'getText'),
    QMessageBox: ('about', 'critical', 'exec', 'information', 'question', 'warning'),
}
_LOCAL_HOSTS = {None, 'localhost', '127.0.0.1', '::1'}


class Guards:
    """Stand-ins for every modal dialog, the network and slot exceptions.

    puddletag swallows some exceptions in bare ``except:`` blocks, so what
    went wrong is also recorded in ``problems``, and fails the run.
    """

    def __init__(self):
        self.problems = []
        self._answers = defaultdict(deque)

    def answer(self, name, *values):
        self._answers[name].extend(values)

    def install(self):
        for cls, names in _MODAL_FUNCTIONS.items():
            for name in names:
                setattr(cls, name, self._stub(f'{cls.__name__}.{name}'))

        real_getaddrinfo = socket.getaddrinfo
        real_connect = socket.socket.connect

        def getaddrinfo(host, *args, **kwargs):
            if host not in _LOCAL_HOSTS:
                self.problems.append(f'network: getaddrinfo {host!r}')
                raise OSError(f'network blocked: {host!r}')
            return real_getaddrinfo(host, *args, **kwargs)

        def create_connection(address, *args, **kwargs):
            self.problems.append(f'network: connection to {address!r}')
            raise OSError(f'network blocked: {address!r}')

        def connect(sock, address):
            host = address[0] if isinstance(address, tuple) else None
            if sock.family != socket.AF_UNIX and host not in _LOCAL_HOSTS:
                self.problems.append(f'network: connect to {address!r}')
                raise OSError(f'network blocked: {address!r}')
            return real_connect(sock, address)

        socket.getaddrinfo = getaddrinfo
        socket.create_connection = create_connection
        socket.socket.connect = connect

        def excepthook(kind, value, tb):
            text = ''.join(traceback.format_exception(kind, value, tb))
            self.problems.append(f'exception in a slot:\n{text}')
            print(text, file=sys.stderr)

        sys.excepthook = excepthook

    def _stub(self, name):
        def stub(*args, **kwargs):
            if not self._answers[name]:
                self.problems.append(f'unexpected modal dialog {name}{args[1:]!r}')
                raise AssertionError(f'unexpected modal dialog {name}')
            return self._answers[name].popleft()
        return stub

    def finish(self):
        for name, values in self._answers.items():
            if values:
                self.problems.append(f'queued answers never used: {name} {list(values)!r}')
        return self.problems


# Synthetic data --------------------------------------------------------------

# MPEG-1 Layer III, 128 kb/s, 44.1 kHz, mono, no side info: silence.
_FRAME = b'\xff\xfb\x90\xc4' + bytes(413)


def _mix(color, other, amount):
    """`color` moved `amount` (0 to 1) of the way to `other`, both QColors."""
    return QColor(*(round(a + (b - a) * amount) for a, b in
                    zip(color.getRgb()[:3], other.getRgb()[:3])))


def _draw_tree(painter, rng, color, leaf, base, levels=9):
    """A branching silhouette from `base`, then translucent leaves at its tips."""
    tips = []

    def branch(x, y, angle, length, width, level):
        end = QPointF(x + length * math.sin(angle), y - length * math.cos(angle))
        pen = QPen(color, width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(x, y), end)
        if level == levels:
            tips.append(end)
            return
        for side in (-1, 1):
            turn = math.radians(20 + 10 * rng.random())
            shrink = 0.72 + 0.08 * rng.random()
            branch(end.x(), end.y(), angle + side * turn + math.radians(6 * rng.random() - 3),
                   length * shrink, width * 0.72, level + 1)

    # Leaning slightly so the crown isn't symmetrical.
    branch(base.x(), base.y(), math.radians(-4 + 6 * rng.random()), 44, 7, 1)
    painter.setPen(Qt.PenStyle.NoPen)
    for tip in tips:
        for _ in range(3):
            radius = 2.5 + 2.5 * rng.random()
            leaf.setAlpha(70 + round(60 * rng.random()))
            painter.setBrush(leaf)
            painter.drawEllipse(QPointF(tip.x() + 12 * rng.random() - 6,
                                        tip.y() + 12 * rng.random() - 6), radius, radius)


def draw_cover(album):
    """A night landscape with the album's colour. Only rng.random() is used:
    Python keeps its sequence for a seed the same across versions, not the
    other methods', so a cover is the same bytes on every run."""
    rng = random.Random(zlib.crc32(album.title.encode()))
    color = QColor(album.color)
    size = 300
    image = QImage(size, size, QImage.Format.Format_RGB32)
    painter = QPainter(image)
    for hint in (QPainter.RenderHint.Antialiasing, QPainter.RenderHint.TextAntialiasing):
        painter.setRenderHint(hint)

    sky = QLinearGradient(0, 0, 0, size)
    sky.setColorAt(0, _mix(color, QColor('black'), 0.55))
    sky.setColorAt(0.8, _mix(color, QColor('white'), 0.28))
    painter.fillRect(0, 0, size, size, QBrush(sky))

    painter.setPen(Qt.PenStyle.NoPen)
    for _ in range(40):
        x, y = size * rng.random(), 140 * rng.random()
        radius = 0.6 + 0.9 * rng.random()
        star = QColor('white')
        star.setAlpha(round(230 * (1 - y / 170) * (0.5 + 0.5 * rng.random())))
        painter.setBrush(star)
        painter.drawEllipse(QPointF(x, y), radius, radius)

    moon = QPointF(232, 62)
    glow = QRadialGradient(moon, 70)
    for stop, alpha in ((0, 120), (0.35, 50), (1, 0)):
        pale = QColor('#f3e9c6')
        pale.setAlpha(alpha)
        glow.setColorAt(stop, pale)
    painter.setBrush(QBrush(glow))
    painter.drawEllipse(moon, 70, 70)
    painter.setBrush(QColor('#f3e9c6'))
    painter.drawEllipse(moon, 24, 24)

    dark = _mix(color, QColor('black'), 0.88)
    hill = QPainterPath()
    hill.moveTo(0, 252)
    hill.cubicTo(70, 226, 140, 262, 210, 240)
    hill.cubicTo(250, 228, 280, 236, size, 244)
    hill.lineTo(size, size)
    hill.lineTo(0, size)
    hill.closeSubpath()
    # The tree goes behind the hill, so its foot is hidden by the ground.
    _draw_tree(painter, rng, dark, _mix(color, QColor('white'), 0.55), QPointF(96, 246))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(dark)
    painter.drawPath(hill)

    painter.setPen(QColor('white'))
    painter.setFont(QFont(FONT_FAMILY, 17, QFont.Weight.Bold))
    painter.drawText(QRect(10, 252, 280, 26), Qt.AlignmentFlag.AlignCenter, album.title)
    painter.setFont(QFont(FONT_FAMILY, 11))
    painter.drawText(QRect(10, 276, 280, 20), Qt.AlignmentFlag.AlignCenter, album.artist)
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, 'PNG')
    return bytes(buffer.data())


def write_album(music, album):
    from mutagen.id3 import APIC, ID3, TALB, TCON, TDRC, TIT2, TPE1, TRCK
    folder = music / album.folder
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    cover = draw_cover(album) if album.tagged else None
    for n, (title, seconds) in enumerate(album.tracks, 1):
        path = folder / album.pattern.format(n=n, title=title)
        path.write_bytes(_FRAME * round(seconds * 44100 / 1152))
        if not album.tagged:
            continue
        tags = ID3()
        for frame in (TPE1(encoding=3, text=[album.artist]), TALB(encoding=3, text=[album.title]),
                      TIT2(encoding=3, text=[title]), TRCK(encoding=3, text=[str(n)]),
                      TDRC(encoding=3, text=[album.year]), TCON(encoding=3, text=[album.genre]),
                      APIC(encoding=3, mime='image/png', type=3, desc='', data=cover)):
            tags.add(frame)
        tags.save(path)


# The scene helper ------------------------------------------------------------

class Studio:
    """What a scene drives: the main window, its docks and dialogs, and the
    way pictures are taken and saved."""

    def __init__(self, win, app, music, work, out, wanted, guards, default_state):
        from puddlestuff.puddleobjects import PuddleDock
        from puddlestuff.puddletag import status
        self.win, self.app, self.music, self.work = win, app, music, work
        self.tags_txt = work / 'tags.txt'
        self.status = status
        self.out = out
        self.wanted = wanted
        self.saved = set()
        self.active = win
        self._guards = guards
        self._default_state = default_state
        self._controls = PuddleDock._controls

    # Waiting

    def wait(self, ms=200):
        QTest.qWait(ms)

    def wait_until(self, condition, what, timeout=10):
        waited = 0
        while not condition():
            if waited >= timeout * 1000:
                raise TimeoutError(what)
            QTest.qWait(10)
            waited += 10

    def activate(self, window):
        """Makes this window the one that has the activation, as a desktop's
        window manager does; the offscreen platform doesn't."""
        self.active = window
        window.activateWindow()
        self.wait_until(window.isActiveWindow, f'{window!r} active')

    def settle(self):
        """Waits for the progress window of a write to go, gives the
        activation back to the window that should have it, and lets the
        events run."""
        from puddlestuff.puddleobjects import ProgressWin
        self.wait_until(lambda: not any(w.isVisible() for w in self.win.findChildren(ProgressWin)),
                        'progress window gone')
        self.activate(self.active)
        self.wait(200)
        # The Filesystem dock keeps its old scroll position when it is
        # resized: show its selected folder.
        view = self._controls['Filesystem'].dirview
        selected = self._selected_folders()
        if view.isVisible() and selected:
            view.scrollTo(selected[0], QAbstractItemView.ScrollHint.PositionAtCenter)
            view.horizontalScrollBar().setValue(0)
            self.wait(50)

    def _selected_folders(self):
        # The Filesystem tree hides all columns but the first: its rows are
        # never fully selected.
        view = self._controls['Filesystem'].dirview
        return [i for i in view.selectionModel().selectedIndexes() if i.column() == 0]

    # Looking things up

    @property
    def table(self):
        return self.win._table

    def control(self, name):
        """The widget of a dock or the toolbar, by name ('Tag Panel',
        'patterncombo', ...)."""
        return self._controls[name]

    def dock(self, name):
        [dock] = [d for d in self.win.findChildren(QDockWidget) if d.objectName() == name]
        return dock

    def action(self, name):
        """The command with this name in data/shortcuts, not a menu of the
        same name ('&Actions' is both)."""
        from PyQt6.QtGui import QAction
        [action] = [a for a in self.win.findChildren(QAction) if a.text() == name and not a.menu()]
        return action

    def trigger(self, name):
        action = self.action(name)
        assert action.isEnabled(), f'{name} is disabled'
        action.trigger()

    def button(self, name):
        """The toolbar's button of a command."""
        button = self.win.toolbar.widgetForAction(self.action(name))
        assert button is not None, f'{name} is not in the toolbar'
        return button

    def shown(self, cls):
        """The one visible top-level window of this class; it gets the
        activation."""
        def found():
            return [w for w in QApplication.topLevelWidgets()
                    if isinstance(w, cls) and w.isVisible()]
        self.wait_until(lambda: len(found()) == 1, f'one visible {cls.__name__}')
        [window] = found()
        self.activate(window)
        return window

    def close(self, window):
        """Closes a window the scene opened; the main window or the window
        under it gets the activation."""
        window.close()
        self.wait_until(lambda: not window.isVisible(), f'{window!r} closed')
        self.activate(self.win)

    def pick(self, combo, text):
        """Picks an item as a user does; a combo that listens to `activated`
        ignores setCurrentIndex alone."""
        index = combo.findText(text, Qt.MatchFlag.MatchFixedString)
        assert index != -1, f'{text!r} not in the combo'
        combo.setCurrentIndex(index)
        combo.activated.emit(index)

    def answer(self, name, value):
        self._guards.answer(name, value)

    # Table helpers

    def column(self, field):
        return [f for title, f in self.table.model().headerdata].index(field)

    def cell(self, row, field):
        return self.table.model().index(row, self.column(field)).data()

    def set_widths(self, **widths):
        """Column widths by field name: ``set_widths(__filename=330, artist=120)``."""
        for field, width in widths.items():
            self.table.setColumnWidth(self.column(field), width)

    def select_rows(self, rows):
        """Selects exactly these rows."""
        model = self.table.model()
        selection = QItemSelection()
        for row in rows:
            selection.select(model.index(row, 0), model.index(row, model.columnCount() - 1))
        self.table.selectionModel().select(selection,
                                           QItemSelectionModel.SelectionFlag.ClearAndSelect)
        self._set_current(model.index(min(rows), 0))
        self.table.setFocus()

    def _set_current(self, index):
        """Sets the current cell (the one with the focus frame) without
        touching the selection; it is otherwise a matter of timing."""
        self.table.selectionModel().setCurrentIndex(
            index, QItemSelectionModel.SelectionFlag.NoUpdate)

    # Setting the stage

    def reset(self, width=MAIN_SIZE[0], height=MAIN_SIZE[1]):
        """The state every scene starts from: no other window, no files, the
        first start's layout, pattern and columns, at this size."""
        for window in QApplication.topLevelWidgets():
            if window is not self.win and window.isVisible():
                window.close()
        unload = self.action('&Unload Everything')
        if unload.isEnabled():
            unload.trigger()
            self.wait_until(lambda: self.table.model().rowCount() == 0, 'files unloaded')
        self.win.restoreState(self._default_state[0])
        self.table.horizontalHeader().restoreState(self._default_state[1])
        combo = self.control('patterncombo')
        combo.setCurrentIndex(0)
        combo.setEditText(combo.itemText(0))
        self.win.showNormal()
        self.win.resize(width, height)
        self.activate(self.win)
        self.wait(200)

    def load(self, *folders, select='all', one_by_one=False):
        """Opens the folders (the first replaces what is loaded, the rest
        are added) and selects 'all' rows, one row, or None. With
        `one_by_one` each folder is loaded before the next is added."""
        view = self.control('Filesystem').dirview
        expected = sum(len(list(Path(f).glob('*.mp3'))) for f in folders)
        self.win.openDir(str(folders[0]), False)
        loaded = len(list(Path(folders[0]).glob('*.mp3')))
        for folder in folders[1:]:
            if one_by_one:
                # A folder added while the last one still loads is dropped.
                self.wait_until(lambda: self.table.model().rowCount() == loaded,
                                f'{loaded} rows')
                loaded += len(list(Path(folder).glob('*.mp3')))
            self.win.openDir(str(folder), True)
        self.wait_until(lambda: self.table.model().rowCount() == expected, f'{expected} rows')
        names = {os.path.realpath(f) for f in folders}

        def folders_selected():
            return not view._threadRunning and names == {
                os.path.realpath(view.model().filePath(i)) for i in self._selected_folders()}
        self.wait_until(folders_selected, 'Filesystem selects the folders')
        model = self.table.model()
        if select == 'all':
            self.table.selectAll()
        elif select is not None:
            self.table.selectRow(select)
        self._set_current(model.index(select if isinstance(select, int) else 0, 0)
                          if select is not None else QModelIndex())
        self.table.setFocus()
        self.wait(100)

    # Pictures

    def grab(self, widget, rect=None):
        self.settle()
        pixmap = widget.grab() if rect is None else widget.grab(rect)
        return pixmap.toImage().convertToFormat(QImage.Format.Format_RGB32)

    def composite(self, window, popups):
        """The window's picture with popups (menus, a combo's list) drawn
        where they are on the screen; popups are top-level widgets."""
        image = self.grab(window)
        painter = QPainter(image)
        origin = window.mapToGlobal(QPoint(0, 0))
        for popup in popups:
            painter.drawPixmap(popup.mapToGlobal(QPoint(0, 0)) - origin, popup.grab())
        painter.end()
        return image

    def annotate(self, image, marks):
        """Draws number(), label() and arrow() marks on the image; points are
        in the image's pixels (``studio.rect(widget, grabbed)`` maps a
        widget into the grabbed widget)."""
        image = image.copy()
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        for mark in marks:
            if mark[0] == 'text':
                _draw_text(painter, *mark[1:])
            else:
                _draw_arrow(painter, *mark[1:])
        painter.end()
        return image

    def rect(self, widget, grabbed):
        """The widget's rectangle in the pixels of the grabbed widget."""
        return QRect(widget.mapTo(grabbed, QPoint(0, 0)), widget.size())

    def save(self, picture, image):
        assert picture in PICTURES, f'unknown picture {picture}'
        if picture not in self.wanted:
            return
        path = self.out / picture
        path.parent.mkdir(parents=True, exist_ok=True)
        assert image.save(str(path), 'PNG', 0), f'could not save {path}'
        self.saved.add(picture)
        print(f'made {picture}')


# Scenes: startup, tutorial 1, toolbar, two folders, artwork, layout ----------

@scene('screenshots/1.png', 'source/tut1/1full.png')
def startup(studio):
    studio.reset()
    studio.table.setFocus()
    image = studio.grab(studio.win)
    studio.save('screenshots/1.png', image)
    studio.save('source/tut1/1full.png', image)


@scene('source/tut1/2full.png', 'source/tut1/3full.png', 'source/tut1/4full.png',
       'source/tut1/5full.png', 'source/tut1/6full.png')
def tutorial_1(studio):
    studio.reset(*TUTORIAL_SIZE)
    write_album(studio.music, NOTHING_TO_HEAR)
    studio.load(studio.music / NOTHING_TO_HEAR.folder, select=0)
    win, table = studio.win, studio.table
    studio.win.resizeDocks([studio.dock('Tag Panel'), studio.dock('Filesystem')], [290, 160],
                           Qt.Orientation.Vertical)
    studio.set_widths(__filename=330, artist=120, title=130, album=110, track=50)
    combo = studio.control('patterncombo')

    def write_with(action, pattern, wait_for):
        combo.setEditText(pattern)
        studio.trigger(action)
        studio.wait_until(wait_for, f'{action} with {pattern}')
        studio.settle()
        table.setFocus()

    image = studio.grab(win)
    marks = []
    for text, widget in (('1', combo), ('2', studio.button('&File->Tag')),
                         ('3', studio.button('&Tag->File'))):
        box = studio.rect(widget, win)
        marks.append(number(text, QPoint(box.center().x(), box.bottom() + 3), 'top'))
    studio.save('source/tut1/2full.png', studio.annotate(image, marks))

    write_with('&File->Tag', '%artist% - %track% - %title%',
               lambda: studio.cell(0, 'title') == 'Opening Hush')
    studio.save('source/tut1/3full.png', studio.grab(win))

    table.selectAll()
    count = len(NOTHING_TO_HEAR.tracks)
    write_with('&File->Tag', '%artist% - %track% - %title%',
               lambda: all(studio.cell(row, 'title') for row in range(count)))
    studio.save('source/tut1/4full.png', studio.grab(win))

    panel = studio.control('Tag Panel')
    for name, text in (('album', NOTHING_TO_HEAR.title), ('year', '2026'), ('genre', 'Ambient')):
        panel.combos[name].setEditText(text)
    studio.trigger('&Save')
    studio.wait_until(lambda: all(studio.cell(row, 'album') == NOTHING_TO_HEAR.title
                                  for row in range(count)), 'files saved')
    studio.settle()

    write_with('&Tag->File', '%track% - %title%',
               lambda: studio.cell(0, '__filename') == '01 - Opening Hush.mp3')
    studio.save('source/tut1/5full.png', studio.grab(win))

    write_with('&Tag->File', '$num(%track%, 1) - %title%',
               lambda: studio.cell(0, '__filename') == '1 - Opening Hush.mp3')
    studio.save('source/tut1/6full.png', studio.grab(win))


@scene('source/tut1/actionsbutton.png', 'source/tut1/addfolder.png',
       'source/tut1/filetotag.png', 'source/tut1/functions.png', 'source/tut1/importfile.png',
       'source/tut1/parentfolder.png', 'source/tut1/quickactions.png', 'source/tut1/reload.png',
       'source/tut1/renamedir.png', 'source/tut1/tagtofile.png',
       'source/tut1/toolbarbuttonscomplete.png', 'source/tut1/track.png')
def toolbar(studio):
    studio.reset()
    studio.load(studio.music / LOW_LIGHT.folder, select=0)
    buttons = {
        'source/tut1/actionsbutton.png': '&Actions',
        'source/tut1/addfolder.png': '&Add Folder',
        'source/tut1/filetotag.png': '&File->Tag',
        'source/tut1/functions.png': '&Functions',
        'source/tut1/importfile.png': '&Text File->Tag',
        'source/tut1/parentfolder.png': '&Go to parent folder',
        'source/tut1/quickactions.png': '&QuickActions',
        'source/tut1/reload.png': '&Refresh',
        'source/tut1/renamedir.png': '&Rename Directories',
        'source/tut1/tagtofile.png': '&Tag->File',
        'source/tut1/track.png': 'Autonumbering &Wizard...'}
    for picture, name in buttons.items():
        studio.save(picture, studio.grab(studio.button(name)))
    bar = studio.win.toolbar
    # The toolbar is as wide as the window: clip the empty space after the
    # last button.
    right = max(w.geometry().right() for w in (bar.widgetForAction(a) for a in bar.actions())
                if w is not None and w.isVisible())
    studio.save('source/tut1/toolbarbuttonscomplete.png',
                studio.grab(bar, QRect(0, 0, right + 4, bar.height())))


@scene('screenshots/2.png')
def two_folders(studio):
    studio.reset()
    studio.load(studio.music / LOW_LIGHT.folder, studio.music / WHISPER_SONGS.folder, select=None)
    studio.win.resizeDocks([studio.dock('Tag Panel'), studio.dock('Filesystem')], [290, 250],
                           Qt.Orientation.Vertical)
    studio.set_widths(__filename=200)
    # Both albums have files named "01 - ...": the table sorts them together.
    studio.select_rows([row for row in range(studio.table.model().rowCount())
                        if studio.cell(row, 'album') == WHISPER_SONGS.title])
    studio.wait_until(lambda: studio.control('Tag Panel').combos['album'].currentText()
                      == WHISPER_SONGS.title, 'Tag Panel shows Whisper Songs')
    studio.save('screenshots/2.png', studio.grab(studio.win))


@scene('source/images/tut3_window.png')
def artwork(studio):
    studio.reset()
    studio.load(studio.music / LOW_LIGHT.folder, select=0)
    win = studio.win
    dock = studio.dock('Artwork')
    dock.toggleViewAction().trigger()
    studio.wait_until(dock.isVisible, 'Artwork shown')
    win.resizeDocks([dock], [260], Qt.Orientation.Horizontal)
    win.resizeDocks([studio.dock('Tag Panel'), studio.dock('Filesystem')], [290, 200],
                    Qt.Orientation.Vertical)
    studio.set_widths(__filename=200)
    image = studio.grab(win)
    marks = []
    for name, widget in (('Tag Panel', studio.dock('Tag Panel')),
                         ('Filesystem', studio.dock('Filesystem')), ('Artwork', dock)):
        marks.append(label(name, studio.rect(widget, win).center(), 20))
    viewport = studio.rect(studio.table.viewport(), win)
    marks.append(label('File View', QPoint(viewport.center().x(),
                                           viewport.top() + viewport.height() * 3 // 4), 20))
    combo = studio.rect(studio.control('patterncombo'), win)
    below = QPoint(combo.center().x(), combo.bottom() + 140)
    marks.append(label('Pattern Combo', below, 20))
    marks.append(arrow(QPoint(below.x(), below.y() - 18), QPoint(combo.center().x(), combo.bottom() + 4)))
    studio.save('source/images/tut3_window.png', studio.annotate(image, marks))


@scene('screenshots/5.png')
def layout(studio):
    from puddlestuff import constants
    studio.reset(*LAYOUT_SIZE)
    # Only this picture has the Cyrillic album: the others show the Music
    # folder in the Filesystem dock.
    write_album(studio.music, NIGHT_AIR)
    studio.load(*(studio.music / album.folder for album in (LOW_LIGHT, NIGHT_AIR, WHISPER_SONGS)),
                select=None, one_by_one=True)
    win, table = studio.win, studio.table
    model = table.model()
    bottom = Qt.DockWidgetArea.BottomDockWidgetArea
    corners = (Qt.Corner.BottomLeftCorner, Qt.Corner.BottomRightCorner)
    old_corners = [win.corner(corner) for corner in corners]
    old_header = list(model.headerdata)
    old_sort = model.sortFields, model.reverseSort
    action_files = []
    actions = studio.dock('Actions')
    try:
        for name, funcs in LAYOUT_ACTIONS:
            path = Path(constants.ACTIONDIR) / f'{name}.action'
            path.write_text(json.dumps({'info': {'name': name}, **{
                f'Func{i}': {'func_name': func_name, 'module': 'puddlestuff.functions',
                             'fields': fields, 'arguments': arguments}
                for i, (func_name, fields, arguments) in enumerate(funcs)}}, indent=2))
            action_files.append(path)
        actions.widget().updateOrder()

        for corner in corners:
            win.setCorner(corner, bottom)
        studio.dock('Filter').hide()
        right = Qt.DockWidgetArea.RightDockWidgetArea
        win.addDockWidget(right, actions)
        for name in ('Tag Panel', 'Functions', 'Artwork', 'Filesystem'):
            dock = studio.dock(name)
            win.addDockWidget(bottom, dock)
            dock.show()
        actions.show()
        # The layout takes sizes in two passes: without the second, the
        # docks' sizes depend on what the scenes before did.
        for _ in range(2):
            win.resizeDocks([studio.dock(name) for name in ('Tag Panel', 'Functions', 'Artwork',
                                                            'Filesystem')],
                            [350, 340, 260, 490], Qt.Orientation.Horizontal)
            win.resizeDocks([studio.dock('Tag Panel')], [320], Qt.Orientation.Vertical)
            win.resizeDocks([actions], [300], Qt.Orientation.Horizontal)
            studio.wait()

        header = [(title, field) for title, field in old_header]
        header.insert([field for title, field in header].index('__filename') + 1,
                      ('Dirname', '__dirname'))
        table.setHeaderTags(header)
        table.sortByColumn(studio.column('artist'), Qt.SortOrder.AscendingOrder)
        studio.set_widths(__filename=185, __dirname=220, artist=105, title=130, album=100,
                          track=45, __length=60, year=45, __bitrate=65, genre=60)

        selection = QItemSelection()
        for row in range(len(LOW_LIGHT.tracks)):
            index = model.index(row, studio.column('title'))
            selection.select(index, index)
        table.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        studio._set_current(model.index(0, studio.column('title')))
        table.setFocus()
        studio.wait_until(lambda: len(studio.status['selectedtags']) == 10, 'ten cells selected')

        function_dock = studio.control('Functions')
        studio.pick(function_dock.functions, 'Case conversion')
        function_dock.stack.currentWidget().tagcombo.setEditText('artist, title')
        listbox = actions.widget().listbox
        listbox.item(_row_of(listbox, 'Number Tracks Two Digits')).setCheckState(
            Qt.CheckState.Checked)
        # The example label's height comes from its scroll bar's, which is
        # only known once the dock has been laid out.
        studio.grab(win)
        actions.widget().updateExample()
        function_dock._update()
        studio.save('screenshots/5.png', studio.grab(win))
    finally:
        for corner, area in zip(corners, old_corners):
            win.setCorner(corner, area)
        studio.dock('Filter').show()
        table.setHeaderTags(old_header)
        model.sortFields, model.reverseSort = old_sort
        for path in action_files:
            path.unlink()
        actions.widget().updateOrder()
        shutil.rmtree(studio.music / NIGHT_AIR.folder)


# Scenes: actions, functions, autonumbering, text file, tag sources, mass tagging

def _push_button(widget, text):
    from PyQt6.QtWidgets import QPushButton
    [button] = [b for b in widget.findChildren(QPushButton) if b.text() == text]
    return button


def _row_of(listbox, text):
    rows = [row for row in range(listbox.count()) if listbox.item(row).text() == text]
    assert len(rows) == 1, f'{text!r} is not once in the list'
    return rows[0]


def _edit_action(studio, window, name):
    """Selects an action in the Actions window and clicks Edit."""
    from puddlestuff.actiondlg import CreateAction
    window.listbox.setCurrentRow(_row_of(window.listbox, name))
    window.buttonlist.editButton.click()
    return studio.shown(CreateAction)


@scene('screenshots/3.png', 'screenshots/4.png', 'source/tut1/actions.png',
       'source/tut1/caseaction.png', 'source/tut1/caseactionedit.png')
def actions(studio):
    from puddlestuff.actiondlg import ActionWindow, CreateFunction
    studio.reset()
    studio.load(studio.music / LOW_LIGHT.folder, select=0)
    studio.trigger('&Actions')
    window = studio.shown(ActionWindow)
    studio.save('source/tut1/actions.png', studio.grab(window))

    edit = _edit_action(studio, window, 'Case Conversion')
    image = studio.grab(edit)
    studio.save('source/tut1/caseaction.png', image)
    studio.save('screenshots/3.png', image)

    edit.listbox.setCurrentRow(0)
    edit.buttonlist.editButton.click()
    function = studio.shown(CreateFunction)
    studio.save('source/tut1/caseactionedit.png', studio.grab(function))
    studio.close(function)
    studio.close(edit)

    studio.activate(window)
    edit = _edit_action(studio, window, 'Standard')
    studio.save('screenshots/4.png', studio.grab(edit))
    studio.close(edit)
    studio.close(window)


@scene('source/tut1/formataction.png')
def functions(studio):
    from puddlestuff.actiondlg import CreateFunction
    studio.reset()
    studio.load(studio.music / LOW_LIGHT.folder, select=None)
    studio.table.setCurrentIndex(studio.table.model().index(2, studio.column('title')))
    studio.wait_until(lambda: len(studio.status['selectedtags']) == 1, 'one cell selected')
    studio.trigger('&Functions')
    window = studio.shown(CreateFunction)
    studio.pick(window.functions, 'Case conversion')
    window.stack.currentWidget().tagcombo.setEditText('__selected')
    studio.save('source/tut1/formataction.png', studio.grab(window))
    studio.close(window)


@scene('source/tut1/numbering.png')
def autonumbering(studio):
    from puddlestuff.helperwin import AutonumberDialog
    studio.reset()
    studio.load(studio.music / LOW_LIGHT.folder, select='all')
    studio.trigger('Autonumbering &Wizard...')
    window = studio.shown(AutonumberDialog)
    studio.save('source/tut1/numbering.png', studio.grab(window))
    studio.close(window)


@scene('source/tut1/importfilewindow.png', 'source/tut1/textedit.png')
def text_file(studio):
    from puddlestuff.helperwin import ImportTextFile
    studio.reset()
    studio.load(studio.music / LOW_LIGHT.folder, select='all')
    studio.answer('QFileDialog.getOpenFileName', (str(studio.tags_txt), ''))
    studio.trigger('&Text File->Tag')
    window = studio.shown(ImportTextFile)
    window.resize(700, 370)
    studio.save('source/tut1/importfilewindow.png', studio.grab(window))
    window.patterncombo.setEditText('%artist% - %title%')
    studio.save('source/tut1/textedit.png', studio.grab(window))
    studio.close(window)


def _show_dock(studio, name, width):
    dock = studio.dock(name)
    dock.show()
    dock.raise_()
    studio.wait_until(dock.isVisible, f'{name} shown')
    studio.win.resizeDocks([dock], [width], Qt.Orientation.Horizontal)
    return dock


def _checkbox_text_end(box):
    """The x of the end of a check box's text, in the box's own pixels."""
    from PyQt6.QtGui import QFontMetrics
    from PyQt6.QtWidgets import QStyle
    style = box.style()
    text = box.text().replace('&', '')
    return (style.pixelMetric(QStyle.PixelMetric.PM_IndicatorWidth)
            + style.pixelMetric(QStyle.PixelMetric.PM_CheckBoxLabelSpacing)
            + QFontMetrics(box.font()).horizontalAdvance(text))


def _musicbrainz_answers(source):
    """Albums made up for these pictures, in place of what the web service
    answers."""
    albums = [
        ({'#id': 'low-light', 'album': LOW_LIGHT.title, 'artist': LOW_LIGHT.artist,
          'year': LOW_LIGHT.year}, []),
        ({'#id': 'low-light-deluxe', 'album': 'Low Light (Deluxe Edition)',
          'artist': LOW_LIGHT.artist}, []),
        ({'#id': 'live', 'album': 'Live at the Library', 'artist': LOW_LIGHT.artist}, [])]
    tracks = [{'title': title, 'track': str(n)}
              for n, (title, seconds) in enumerate(LOW_LIGHT.tracks, 1)]
    source.keyword_search = lambda text: albums
    source.retrieve = lambda info: (info, tracks)


@scene('source/images/eg_tagsource.png', 'source/images/tagsource_dialog_tut4.png')
def tag_sources(studio):
    from PyQt6.QtGui import QFontMetrics
    studio.reset()
    studio.load(studio.music / LOW_LIGHT.folder, select='all')
    dock = _show_dock(studio, 'Tag Sources', DOCK_WIDTH)
    panel = studio.control('Tag Sources')
    studio.pick(panel.sourcelist, 'MusicBrainz')
    [source] = [s for s in studio.status['initialized_tagsources'] if s.name == 'MusicBrainz']
    _musicbrainz_answers(source)
    write = _push_button(panel, '&Write')
    clear = _push_button(panel, 'Clea&r preview')
    configure = panel._MainWin__preferencesButton
    fields = panel._MainWin__fieldsEdit
    results = panel.listbox
    try:
        # Before a search: the three arrows' picture.
        image = studio.grab(dock)
        box = {name: studio.rect(widget, dock) for name, widget in (
            ('combo', panel.sourcelist), ('configure', configure), ('list', results),
            ('write', write))}
        font = QFontMetrics(QFont(FONT_FAMILY, 12, QFont.Weight.Bold))
        top, bottom = box['list'].top(), box['list'].bottom()
        select_at = QPoint(box['list'].center().x(), top + 40)
        configure_at = QPoint(box['list'].right() - 12 - font.horizontalAdvance(
            'Configure Tag Source') // 2, top + 110)
        write_at = QPoint(box['write'].center().x(), bottom - 40)
        marks = [
            label('Select Tag Source', select_at),
            arrow(QPoint(select_at.x(), select_at.y() - 12),
                  QPoint(select_at.x(), box['combo'].bottom() + 3)),
            label('Configure Tag Source', configure_at),
            arrow(QPoint(box['configure'].center().x(), configure_at.y() - 12),
                  QPoint(box['configure'].center().x(), box['configure'].bottom() + 3)),
            label('Write Preview', write_at),
            arrow(QPoint(write_at.x(), write_at.y() + 12),
                  QPoint(write_at.x(), box['write'].top() - 3))]
        studio.save('source/images/tagsource_dialog_tut4.png', studio.annotate(image, marks))

        panel.searchEdit.setText('ada rest;low light')
        panel.searchButton.click()
        model = results.model()
        parent = QModelIndex()
        studio.wait_until(lambda: model.rowCount(parent) == 3, 'three albums found')
        studio.wait_until(panel.searchButton.isEnabled, 'search finished')
        # The view's `clicked` is what starts the retrieval.
        # The list is sorted by album: pick Low Light, the one with its tracks.
        [first] = [model.index(row, 0, parent) for row in range(3)
                   if model.index(row, 0, parent).internalPointer().itemData['album']
                   == LOW_LIGHT.title]
        results.setCurrentIndex(first)
        results.clicked.emit(first)
        studio.wait_until(lambda: model.rowCount(first) == len(LOW_LIGHT.tracks),
                          'tracks retrieved')
        studio.wait_until(results.isEnabled, 'retrieval done')
        results.expand(first)
        image = studio.grab(dock)

        combo = studio.rect(panel.sourcelist, dock)
        search = studio.rect(panel.searchEdit, dock)
        listing = studio.rect(results, dock)
        button = studio.rect(write, dock)
        fields_box = studio.rect(fields, dock)
        marks = [number(1, QPoint(combo.right() - 40, combo.center().y())),
                 number(2, QPoint(search.right() - 20, search.center().y())),
                 number(3, QPoint(listing.center().x(), listing.top() + listing.height() * 3 // 4)),
                 number(4, QPoint(button.left() - 18, button.center().y())),
                 number(5, QPoint(fields_box.right() - 12, fields_box.center().y()))]
        for text, check in ((6, panel._MainWin__updateEmpty), (7, panel._MainWin__autoRetrieve)):
            rect = studio.rect(check, dock)
            marks.append(number(text, QPoint(rect.left() + _checkbox_text_end(check) + 12,
                                             rect.center().y())))
        studio.save('source/images/eg_tagsource.png', studio.annotate(image, marks))
    finally:
        del source.keyword_search, source.retrieve
    if any(audio.preview for audio in studio.table.model().taginfo):
        studio.answer('QMessageBox.question', QMessageBox.StandardButton.Yes)
        clear.click()
        studio.wait_until(lambda: not any(audio.preview
                                          for audio in studio.table.model().taginfo),
                          'previews cleared')
    studio.settle()


@scene('source/masstag_images/choose_profile.png', 'source/masstag_images/configure_profile.png',
       'source/masstag_images/configure_tagsource.png')
def mass_tagging(studio):
    from puddlestuff.masstag import MassTagProfile, TagSourceProfile
    from puddlestuff.masstag.dialogs import MassTagEdit, MTProfileEdit, TSProfileEdit
    studio.reset()
    studio.load(studio.music / LOW_LIGHT.folder, select='all')
    _show_dock(studio, 'Mass Tagging', DOCK_WIDTH)
    panel = studio.control('Mass Tagging')
    sources = {s.name: s for s in panel.tag_sources}

    def profile(name, *names):
        return MassTagProfile(name, profiles=[TagSourceProfile(tag_source=sources[n])
                                              for n in names])

    panel.setProfiles([profile('AcoustID, then MusicBrainz', 'AcoustID', 'MusicBrainz'),
                       profile('Discogs', 'Discogs.com'),
                       profile('MusicBrainz', 'MusicBrainz'),
                       profile('MusicBrainz and Discogs', 'MusicBrainz', 'Discogs.com')])
    _push_button(panel, '&Configure Profiles').click()
    profiles = studio.shown(MassTagEdit)
    studio.save('source/masstag_images/choose_profile.png', studio.grab(profiles))

    profiles.buttonlist.addButton.click()
    edit = studio.shown(MTProfileEdit)
    studio.save('source/masstag_images/configure_profile.png', studio.grab(edit))

    edit.buttonlist.addButton.click()
    source = studio.shown(TSProfileEdit)
    studio.save('source/masstag_images/configure_tagsource.png', studio.grab(source))
    studio.close(source)
    studio.activate(edit)
    studio.close(edit)
    studio.activate(profiles)
    studio.close(profiles)


# The run ---------------------------------------------------------------------

def parse(argv):
    parser = argparse.ArgumentParser(description='Makes the docs\' pictures.')
    parser.add_argument('pictures', nargs='*', metavar='PICTURE',
                        help='as the pages name it, relative to docs/ (default: all)')
    parser.add_argument('--out', type=Path, default=DOCS,
                        help='where the pictures go (default: docs/)')
    parser.add_argument('--list', action='store_true', help='print every PICTURE and exit')
    args = parser.parse_args(argv)
    unknown = [p for p in args.pictures if p not in PICTURES]
    if unknown:
        print('unknown picture:', *unknown, file=sys.stderr)
        print('known pictures:', *sorted(PICTURES), sep='\n  ', file=sys.stderr)
        sys.exit(2)
    return args


def main(argv=None):
    args = parse(argv)
    if args.list:
        print(*sorted(PICTURES), sep='\n')
        return 0
    asked = set(args.pictures) or set(PICTURES)
    out = args.out.resolve()

    work = Path(tempfile.gettempdir()) / WORK_NAME
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    try:
        return run(work, out, asked)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run(work, out, asked):
    home = work / 'home'
    os.environ.update({
        'HOME': str(home), 'XDG_CONFIG_HOME': str(home / '.config'),
        'XDG_DATA_HOME': str(home / '.local' / 'share'), 'XDG_CACHE_HOME': str(home / '.cache'),
        'QT_QPA_PLATFORM': 'offscreen'})
    for name in ('QT_SCALE_FACTOR', 'QT_SCREEN_SCALE_FACTORS', 'QT_FONT_DPI',
                 'QT_QPA_PLATFORMTHEME'):
        os.environ.pop(name, None)
    sys.path.insert(0, str(DOCS.parent))
    import puddlestuff.resource  # noqa: F401  registers the data:/icons: search paths
    from puddlestuff import constants
    for path in (constants.CONFIGDIR, constants.SAVEDIR):
        if not path.startswith(str(work) + os.sep):
            print(f'refusing to run: {path} is outside {work}', file=sys.stderr)
            return 1
        os.makedirs(path, exist_ok=True)

    app = QApplication(['puddletag'])
    app.setStyle('Fusion')
    app.setPalette(app.style().standardPalette())
    app.setFont(QFont(FONT_FAMILY, FONT_SIZE))
    if QFontInfo(app.font()).family() != FONT_FAMILY:
        print(f'warning: {FONT_FAMILY} not found: the pictures will differ from the committed ones',
              file=sys.stderr)
    QApplication.setCursorFlashTime(0)
    QIcon.setThemeSearchPaths([])
    QIcon.setThemeName('')
    QLocale.setDefault(QLocale('en_US'))

    from puddlestuff import puddleobjects
    constants.trans_strings()
    puddleobjects.trans_imagetypes()

    guards = Guards()
    guards.install()

    music = work / 'Music'
    for album in ALBUMS:
        write_album(music, album)
    (work / 'tags.txt').write_text('\n'.join(TEXT_FILE_LINES) + '\n')

    from puddlestuff.puddletag import MainWin
    win = MainWin()
    win.show()
    win.showNormal()
    default = (win.saveState(), win._table.horizontalHeader().saveState())
    studio = Studio(win, app, music, work, out, asked, guards, default)

    failed = []
    for func in SCENES:
        if not asked & set(func.pictures):
            continue
        try:
            func(studio)
        except Exception:
            print(f'scene {func.__name__} failed ({", ".join(func.pictures)}):', file=sys.stderr)
            traceback.print_exc()
            failed.extend(func.pictures)
    for name in sorted(asked):
        if PICTURES[name] is None:
            print(f'no scene makes {name}', file=sys.stderr)
            failed.append(name)

    if any(audio.preview for audio in win._table.model().taginfo):
        guards.problems.append('a scene left previews behind')
        studio.answer('QMessageBox.question', QMessageBox.StandardButton.Yes)
    for window in QApplication.topLevelWidgets():
        if window is not win and window.isVisible():
            guards.problems.append(f'a scene left {type(window).__name__} open')
            window.close()
    win.close()
    app.processEvents()
    win.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    missed = sorted(p for p in asked if PICTURES[p] is not None and p not in studio.saved)
    for problem in guards.finish():
        print('problem:', problem, file=sys.stderr)
    for name in missed:
        if name not in failed:
            print(f'not saved: {name}', file=sys.stderr)
    return 1 if (failed or missed or guards.problems) else 0


if __name__ == '__main__':
    sys.exit(main())
