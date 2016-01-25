# -*- coding: utf-8 -*-
import subprocess
import os
from os.path import dirname

version_string = '1.1.0'
version = (1, 1, 0)

try:
    filedir = dirname(dirname(dirname(__file__)))
    hash_file = os.path.join(filedir, '.git/refs/heads/master')
    if os.path.exists(hash_file):
        with open(hash_file) as fo:
            changeset = fo.read().strip()
except (EnvironmentError, AttributeError):
    changeset = None
