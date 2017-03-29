# -*- coding: utf-8 -*-
from collections import defaultdict
from puddlestuff.constants import ALWAYS, FILESLOADED, VIEWFILLED, FILESSELECTED, ENABLESIGNALS
from PyQt4.QtCore import SIGNAL
from puddlestuff.puddlesettings import add_config_widget, SettingsError
import logging

status = {}
def connect_shortcut(action, enabled, disabled=None, togglecheck=None):
    controls = status['dialogs']
    emits = defaultdict(lambda: [])

    for c in controls.values():
        [emits[sig].append(c) for sig in c.emits]

    connect = action.connect
    if enabled in emits:
        [connect(c, ENABLESIGNALS.get(enabled, SIGNAL(enabled)),
            action.setEnabled) for c in emits[enabled]]
    else:
        logging.error(u'No enable signal found for ' + action.text())
        action.setEnabled(False)

    if togglecheck and togglecheck in emits:
        [connect(c, ENABLESIGNALS.get(togglecheck, SIGNAL(togglecheck)),
            action.setEnabled) for c in emits[togglecheck]]

def connect_control(control):
    controls = status['dialogs']
    emits = defaultdict(lambda: [])
        
    for c in controls.values():
        [emits[sig].append(c) for sig in c.emits]

    connect = control.connect

    for signal, slot in control.receives:
        if signal in emits:
            [connect(c, SIGNAL(signal), slot) for c in emits[signal]]

    for c in controls.values():
        for signal, slot in c.receives:
            if signal in control.emits:
                connect(control, SIGNAL(signal), slot)
