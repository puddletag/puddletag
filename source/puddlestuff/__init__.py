# -*- coding: utf-8 -*-
import subprocess, re
from os.path import dirname
version_string = '1.0.0'
version = (1, 0, 0)

try:
    filedir = dirname(dirname(dirname(__file__)))
    info = subprocess.Popen(['hg', 'id', '-i', filedir],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    changeset = unicode(info.stdout.read().strip())
except (EnvironmentError, AttributeError):
    changeset = None