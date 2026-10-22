"""The CDDB tag source's module (puddlestuff/tagsources/CDDB.py)."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_cddb_imports_as_root_without_user():
    # Synthetic: root in a container, where USER and EMAIL aren't set. A
    # subprocess, because reloading CDDB here would reset the protocol
    # freedb sets at import.
    env = {k: v for k, v in os.environ.items() if k not in ('EMAIL', 'USER')}
    code = ('import os; os.geteuid = lambda: 0; '
            'from puddlestuff.tagsources import CDDB; print(CDDB.default_user)')

    done = subprocess.run([sys.executable, '-c', code], env=env, cwd=ROOT,
                          capture_output=True, text=True)

    assert (done.returncode, done.stdout.strip()) == (0, 'user'), done.stderr
