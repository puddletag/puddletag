"""The docs list exactly the functions puddletag registers.

scripting.txt documents the $functions. function.txt has a section for each
entry of the Functions dialog, which lists every registered function that has
a docstring (actiondlg.FunctionDialog), under the name its docstring gives.
"""
import re
from pathlib import Path

from puddlestuff.findfunc import Function
from puddlestuff.functions import functions

DOCS = Path(__file__).resolve().parents[2] / 'docsrc' / 'source'
SCRIPTING = re.findall(r'^\.\. describe:: \$(\w+)\(',
                       (DOCS / 'scripting.txt').read_text(encoding='utf-8'), re.M)
SECTIONS = [title.strip() for title in re.findall(
    r'^(.+)\n-{3,}$', (DOCS / 'function.txt').read_text(encoding='utf-8'), re.M)]
DIALOG = {name: Function(name).funcname for name, func in functions.items()
          if func.__doc__ is not None and not func.__name__.startswith('__')}


def test_every_scripting_function_is_documented():
    scripting_only = set(functions) - set(DIALOG)
    assert sorted(scripting_only - set(SCRIPTING)) == []


def test_every_documented_scripting_function_exists():
    assert sorted(set(SCRIPTING) - set(functions)) == []


def test_no_scripting_function_is_documented_twice():
    assert sorted({name for name in SCRIPTING if SCRIPTING.count(name) > 1}) == []


def test_every_dialog_entry_has_a_section_of_the_same_name():
    sections = {title.lower() for title in SECTIONS}
    assert sorted(title for title in DIALOG.values() if title.lower() not in sections) == []


def test_every_section_is_a_dialog_entry():
    entries = {title.lower() for title in DIALOG.values()}
    assert sorted(title for title in SECTIONS if title.lower() not in entries) == []
