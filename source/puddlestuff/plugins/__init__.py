# -*- coding: utf-8 -*-
from __future__ import absolute_import
from collections import defaultdict
from ..constants import ALWAYS, FILESLOADED, VIEWFILLED, FILESSELECTED, ENABLESIGNALS
from ..puddlesettings import add_config_widget, SettingsError
import logging

status = {}
def connect_shortcut(action, enabled, disabled=None, togglecheck=None):
    controls = status['dialogs']
    emits = defaultdict(lambda: [])

    for c in controls.values():
        [emits[sig].append(c) for sig in c.emits]

    if enabled in emits:
        [getattr(c, enabled).connect(
            action.setEnabled) for c in emits[enabled]]
    else:
        logging.error(u'No enable signal found for ' + action.text())
        action.setEnabled(False)

    if togglecheck and togglecheck in emits:
        [getattr(c, togglecheck).connect(
            action.setEnabled) for c in emits[togglecheck]]

def connect_control(control):
    controls = status['dialogs']
    emits = defaultdict(lambda: [])
        
    for c in controls.values():
        [emits[sig].append(c) for sig in c.emits]

    for signal, slot in control.receives:
        if signal in emits:
            [getattr(c, signal).connect(slot) for c in emits[signal]]

    for c in controls.values():
        for signal, slot in c.receives:
            if signal in control.emits:
                getattr(control, signal).connect(slot)
