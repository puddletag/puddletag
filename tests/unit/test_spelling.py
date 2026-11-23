"""The spelling of every file, checked by codespell with the settings in
pyproject.toml's [tool.codespell], as tests.yml's spelling job checks it."""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_codespell_finds_no_misspellings():
    # Run from the repo root with no file names, as the spelling job runs
    # it: codespell reads ./pyproject.toml, whose skip list's ./ paths
    # match only then. Synthetic: the docs are silent on spelling.
    if importlib.util.find_spec('codespell_lib') is None:
        if os.environ.get('CI'):  # set by GitHub Actions; CI must not skip this
            pytest.fail('codespell is missing')
        pytest.skip('codespell is missing')
    done = subprocess.run([sys.executable, '-m', 'codespell_lib'], cwd=ROOT,
                          capture_output=True, text=True)
    assert done.stdout.splitlines() == []
    assert done.returncode == 0, done.stderr
