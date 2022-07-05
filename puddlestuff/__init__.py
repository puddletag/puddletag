# -*- coding: utf-8 -*-

from os import path

version_string = '2.2.0'

# This is only used by the github workflow
_buildid = None
if _buildid:
    version_string += f".post{_buildid}"

changeset = None
if '__file__' in globals():
    filedir = path.dirname(__file__)
    git_root = path.join(filedir, '..')
    hash_file = path.join(git_root, '.git', 'HEAD')
    if path.exists(hash_file):
        try:
            with open(hash_file) as fo:
                changeset = fo.read().strip()
            if changeset.startswith("ref: "):
                hash_file = path.join(git_root, '.git', *(changeset[5:].split('/')))
                with open(hash_file) as fo:
                    changeset = fo.read().strip()
        except (EnvironmentError, AttributeError):
            pass

# for PEP-396 compatibility
__version__ = version_string
