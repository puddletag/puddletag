"""The main window driven as a user drives it: a click goes to the widget
under the mouse, a key to the widget with the keyboard focus, and a
command runs from its menu, its toolbar button or its shortcut.
"""
import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QMenu, QToolBar

LEFT = Qt.MouseButton.LeftButton
NO_MODIFIER = Qt.KeyboardModifier.NoModifier


class User:
    def __init__(self, qtbot, mainwin):
        self._qtbot = qtbot
        self._mainwin = mainwin
        self.table = mainwin._table

    def activate(self):
        """Activates the main window, as clicking on it does. Writing
        several files shows a progress window, which takes the activation
        with it when it closes; a desktop's window manager then activates
        the main window again, the offscreen test platform doesn't."""
        self._mainwin.activateWindow()
        self._qtbot.waitUntil(self._mainwin.isActiveWindow)

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
        self._qtbot.keyClick(QApplication.focusWidget(), key, modifier)

    def type(self, text):
        for char in text:
            self.press(char)

    def action(self, name):
        """The command with this name in data/shortcuts, e.g. '&Save'."""
        [action] = [a for a in self._mainwin.findChildren(QAction) if a.text() == name]
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


@pytest.fixture
def user(qtbot, mainwin):
    return User(qtbot, mainwin)
