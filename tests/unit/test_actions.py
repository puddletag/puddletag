"""Actions: the functions of the Functions dialog, run through findfunc.Function.

Expected results come from docsrc/source/function.txt unless noted.
"""
from puddlestuff.findfunc import Function


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
