# -*- coding: utf-8 -*-
import os
from os.path import dirname


_buildid = None
version = [2, 1, 0]
if _buildid:
    version.append(f"post{_buildid}")
version_string = ".".join(map(str, version))

changeset = None

filedir = dirname(dirname(dirname(__file__)))
hash_file = os.path.join(filedir, ".git/refs/heads/master")
if os.path.exists(hash_file):
    try:
        with open(hash_file) as fo:
            changeset = fo.read().strip()
    except (EnvironmentError, AttributeError):
        pass
