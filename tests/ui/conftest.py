"""The main window driven as a user drives it: a click goes to the widget
under the mouse, a key to the widget with the keyboard focus, and a
command runs from its menu, its toolbar button, its shortcut or a
right-click menu.
"""
import pytest
from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QMenu, QToolBar, QWidget

LEFT = Qt.MouseButton.LeftButton
NO_MODIFIER = Qt.KeyboardModifier.NoModifier


class User:
    def __init__(self, qtbot, mainwin):
        self._qtbot = qtbot
        self._mainwin = mainwin
        self.table = mainwin._table

    def activate(self, window=None):
        """Activates the window (the main one by default), as a desktop's
        window manager does when a dialog opens or closes; the offscreen
        test platform doesn't. Writing several files shows a progress
        window, which takes the activation with it when it closes. The
        command ends, its undo step recorded, only when that window
        closes, after the last file is written: wait for that first."""
        from puddlestuff.puddleobjects import ProgressWin
        self._qtbot.waitUntil(lambda: not any(w.isVisible() for w in self._mainwin.findChildren(ProgressWin)))
        window = window or self._mainwin
        window.activateWindow()
        self._qtbot.waitUntil(window.isActiveWindow)

    def click(self, widget, pos=QPoint(), modifier=NO_MODIFIER):
        """Clicks at pos, or at the widget's center."""
        self._qtbot.mouseClick(widget, LEFT, modifier, pos)

    def double_click(self, widget, pos):
        """A real double-click arrives as press, release, double-click,
        release; QTest's mouseDClick sends only the double-click, which
        opens no editor."""
        self.click(widget, pos)
        self._qtbot.mouseDClick(widget, LEFT, pos=pos)
        self._qtbot.mouseRelease(widget, LEFT, pos=pos)

    def press(self, key, modifier=NO_MODIFIER):
        """A key goes where the keyboard sends it: to the focused widget."""
        widget = QApplication.focusWidget()
        # With no focused widget, QTest sends the key to the keyboard
        # grabber, an open popup or the active window, as the keyboard
        # does, and aborts the whole run when there's none of them.
        assert widget or QWidget.keyboardGrabber() or QApplication.activePopupWidget() \
            or QApplication.activeWindow(), 'no window is active: activate it first'
        self._qtbot.keyClick(widget, key, modifier)

    def type(self, text):
        for char in text:
            self.press(char)

    def action(self, name):
        """The command with this name in data/shortcuts, e.g. '&Save', not
        a menu of the same name (&Actions is both)."""
        [action] = [a for a in self._mainwin.findChildren(QAction)
                    if a.text() == name and not a.menu()]
        return action

    def click_menu(self, name):
        """Opens the menu bar's menu holding the command and clicks it."""
        action = self.action(name)
        bar = self._mainwin.menuBar()
        [menu] = [m for m in bar.findChildren(QMenu) if action in m.actions()]
        self.click(bar, bar.actionGeometry(menu.menuAction()).center())
        self._qtbot.waitUntil(menu.isVisible)
        self.click(menu, menu.actionGeometry(action).center())

    def click_toolbar(self, name):
        action = self.action(name)
        [button] = [bar.widgetForAction(action) for bar in self._mainwin.findChildren(QToolBar)
                    if bar.widgetForAction(action)]
        self.click(button)

    def right_click(self, widget, pos, name):
        """Right-clicks at pos and clicks the command in the menu that
        opens. The click goes to the window, as the desktop sends it: Qt
        makes a right-click a context menu only there, not in a click
        sent to the widget itself. The menu runs its own event loop until
        an item is picked, so the pick waits on a timer. The window gets
        the activation back afterwards, as on a desktop."""
        action = self.action(name)
        menus = []

        def pick(tries=100):
            menu = QApplication.activePopupWidget()
            if not (isinstance(menu, QMenu) and menu.isVisible()):
                if tries:
                    QTimer.singleShot(10, lambda: pick(tries - 1))
                return
            menus.append(menu.actions())
            if action in menu.actions():
                self.click(menu, menu.actionGeometry(action).center())
            else:
                menu.close()

        QTimer.singleShot(0, pick)
        window = widget.window()
        self._qtbot.mouseClick(window.windowHandle(), Qt.MouseButton.RightButton, NO_MODIFIER,
                               widget.mapTo(window, pos))
        assert menus, 'no right-click menu opened'
        assert action in menus[0], f'{name} is not in the right-click menu'
        self.activate(window)

    def cell(self, row, field):
        """The File-View's cell of this row and field."""
        model = self.table.model()
        return model.index(row, [f for title, f in model.headerdata].index(field))

    def click_cell(self, index, modifier=NO_MODIFIER):
        self.table.scrollTo(index)
        self.click(self.table.viewport(), self.table.visualRect(index).center(), modifier)

    def double_click_cell(self, index):
        self.table.scrollTo(index)
        self.double_click(self.table.viewport(), self.table.visualRect(index).center())

    def right_click_cell(self, index, name):
        """Picks the command from the File-View's right-click menu."""
        self.table.scrollTo(index)
        self.right_click(self.table.viewport(), self.table.visualRect(index).center(), name)


@pytest.fixture
def user(qtbot, mainwin):
    return User(qtbot, mainwin)
