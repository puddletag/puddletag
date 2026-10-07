"""Actions: the functions of the Functions dialog, run through findfunc.Function,
and the .action files that save chains of them.

Expected results come from docsrc/source/function.txt unless noted.
"""
import json
import os

import pytest

from puddlestuff.constants import ACTIONDIR, DATADIR
from puddlestuff.findfunc import Function, load_macro_info, save_macro
from puddlestuff.puddleobjects import load_actions


def make_action(name, fields, *args):
    action = Function(name)
    action.setTag(list(fields))
    action.setArgs(list(args))
    return action


def test_convert_to_ascii():
    # The docs' example. The action runs on each value of the field.
    action = make_action('to_ascii', ['title'])
    assert action.funcname == 'Convert to ASCII'
    assert action.runFunction(text=['abc äéç цы'], m_tags={'title': ['abc äéç цы']}) == ['abc aec tsy']


# The default actions shipped in puddlestuff/data, by name.
SHIPPED = {'Case Conversion': 'caseconversion.action', 'Standard': 'standard.action'}


def describe(func):
    """A loaded function as its .action file section writes it."""
    return {'func_name': func.function.__name__, 'module': func.function.__module__,
            'fields': func.tag, 'arguments': [str(arg) for arg in func.args]}


@pytest.mark.parametrize('name', sorted(SHIPPED))
def test_default_action_loads_as_written(name):
    # Expected: the shipped file's own content.
    path = os.path.join(DATADIR, SHIPPED[name])
    with open(path) as f:
        saved = json.load(f)
    funcs, loaded_name = load_macro_info(path)
    assert loaded_name == name
    assert [describe(func) for func in funcs] == [saved[f'Func{i}'] for i in range(len(saved) - 1)]


def test_default_case_conversion_action():
    # docsrc/source/tut2.txt: the Case Conversion action's function changes
    # the album, title and artist fields to "Mixed Case", which capitalises
    # each word and lowers the rest (function.txt). Synthetic title.
    funcs, name = load_macro_info(os.path.join(DATADIR, SHIPPED['Case Conversion']))
    assert set(funcs[0].tag) == {'album', 'title', 'artist'}
    assert funcs[0].runFunction(text=['the BEST of'], m_tags={'title': ['the BEST of']}) == ['The Best Of']


def test_saved_action_loads_back(tmp_path):
    # Synthetic action. Replace's last two arguments are checkboxes.
    funcs = [make_action('titleCase', ['artist', 'title'], 'UPPER CASE', '., !'),
             make_action('replace', ['__all'], '_', ' ', True, False)]
    path = str(tmp_path / 'tidy.action')
    save_macro(path, 'Tidy', funcs)
    loaded, name = load_macro_info(path)
    assert name == 'Tidy'
    assert [(f.function, f.tag, f.args) for f in loaded] == [(f.function, f.tag, f.args) for f in funcs]


def test_clean_profile_gets_the_default_actions(clean_profile):
    # The action shortcuts call load_actions() at startup, before the
    # Actions window has copied the defaults into a new profile.
    for _ in range(2):  # the copies stay: the second call finds them
        actions = load_actions()
        assert sorted(name for funcs, name, path in actions) == sorted(SHIPPED)
        for funcs, name, path in actions:
            assert os.path.dirname(path) == ACTIONDIR
            shipped = load_macro_info(os.path.join(DATADIR, SHIPPED[name]))[0]
            assert [describe(f) for f in funcs] == [describe(f) for f in shipped]
