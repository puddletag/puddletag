"""docs/make_screenshots.py, run as the docs say, makes every picture
the pages show."""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.ui

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'docs' / 'make_screenshots.py'


def made_pictures():
    spec = importlib.util.spec_from_file_location('make_screenshots', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return sorted(module.PICTURES)


@pytest.mark.timeout(300)
def test_script_makes_every_picture(tmp_path):
    # Synthetic: the docs are silent on how their pictures are made. The
    # script runs without coverage: it asserts nothing about the lines it
    # runs.
    env = {name: value for name, value in os.environ.items()
           if name not in ('COVERAGE_PROCESS_CONFIG',
                           'COVERAGE_PROCESS_START')}
    env['TMPDIR'] = str(tmp_path)
    out = tmp_path / 'out'
    done = subprocess.run([sys.executable, str(SCRIPT), '--out', str(out)],
                          env=env, capture_output=True, text=True,
                          timeout=240)
    assert done.returncode == 0, done.stdout + done.stderr
    made = sorted(path.relative_to(out).as_posix()
                  for path in out.rglob('*.png'))
    assert made == made_pictures()
    for name in made:
        data = (out / name).read_bytes()
        assert data.startswith(b'\x89PNG\r\n\x1a\n'), name
        width = int.from_bytes(data[16:20], 'big')
        height = int.from_bytes(data[20:24], 'big')
        assert width >= 16 and height >= 16, name
