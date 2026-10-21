"""Saving the configuration file (puddlestuff/puddleobjects.py PuddleConfig)."""
import json

import pytest

from puddlestuff.puddleobjects import PuddleConfig


@pytest.mark.xfail(strict=True, raises=json.JSONDecodeError,
                   reason='save opens the file for writing, which empties it, '
                          'before json.dumps runs, so a failed save leaves an empty file')
def test_failed_save_keeps_the_file(tmp_path):
    # #987: puddletag.conf ends up empty. The value json can't encode is
    # synthetic; so is the key set before it.
    filename = tmp_path / 'puddletag.conf'
    config = PuddleConfig(str(filename))
    config.set('main', 'before', 'kept')

    with pytest.raises(TypeError):
        config.set('main', 'x', object())

    assert json.loads(filename.read_text(encoding='utf-8'))['main']['before'] == 'kept'
