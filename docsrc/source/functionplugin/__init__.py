# -*- coding: utf-8 -*-

#Function plugin tutorial
#Last updated 11 August 2010
#copyright concentricpuddle, GPLv2

#There are three types of controls that are allowed in creating a dialog
#for an Function. TEXT, COMBO and CHECKBOX correspond to a lineedit, combobox
#and a checkbox respectively.
from puddlestuff.constants import TEXT, COMBO, CHECKBOX
from puddlestuff.functions import FuncError, format_value

#Your function can be any normal python function. If you want it to accept
#the tags of a file, just name the first or last argument 'tags'.
#Fields can be read like a normal dictionary e.g tags.get('artist', u''). 
#Never, ever assume that a specific field is present.
def append_text(tags, text, combo, checkbox):
    try:
        return tags['artist'] + text
    except KeyError:
        raise FuncError('No artist field found')

#If you're not creating an Function, nothing else is needed, but to let
#puddletag know of the existence of this function. Do it 
#by definining a functions property as dictionary with 
# (function_name, function) pairs...
functions = {'append': append_text}

#append_text will now be available as the scripting function '$append'

#Things you need to know.
#1. Only alphanumeric characters are allowed. No spaces and no punctuation.
#2. To make things easier I've included some static typing functionality. Three
#   types are supported. text, number and pattern.
#   Arguments starting with 't_' will be passed as text, a unicode string.
#   Any pattern the user provides (eg. '%artist% - %title%') be parsed and
#   replaced with the associated values.
#   Start an argument with 'n_' to denote a number. It's floating point, unless
#   it can be converted non-destructively to an int.
#   Starting an argument with 'p_' means you want a pattern. Do with it what
#   you wish. Use the puddlestuff.functions.format_value(tags, pattern) 
#   to replace the values in the pattern with what's appropriate.
#3. Only unicode strings will be passed and you should return unicode 
#   strings only.
#4. Return floating point values with 2 decimal places max unless
#   more precision is needed.
#5. If the function wasn't sucessful for any reason, return None 
#   (not something equivalent, None).
#6. Errors aren't handled, so catch any you can.
#9. If an error occured that the user should be notified of raise 
#   FuncError(message).

#Use the PluginFunction class to register your function as a Function.

from puddlestuff.util import PluginFunction

func = PluginFunction('Append text to artist', append_text, 
    u'Action Test: $0 -> Text: $1, Combo: $2, Checkbox: $3', 
    [('Textbox: ', TEXT, 'Default text.'),
        ('ComboBox', COMBO, 'One', 'Two', 'Three'),
        ('Checkbox', CHECKBOX, False)])

#Four arguments are required:
#1. The human-readable name of your Function.
#2. A python function, with same restrictions/rules as normal functions.
#3. A print_string (I need a better name for this) to preview what the
#   action does (like in 'Replace: Match Case: True').
#   It can be formatted as follows.
#   $# shows the value of argument number #. $0 will always be the fields 
#   that'll get written to. $1 corresponds to the first argument, 
#   $2 the second, etc.
#
#   For example, consider an Activities Function where the user has supplied
#   'underwater' and selects 'swimming' as the first and second arguments 
#   respectively. The result of which will be written to the artist field.
#   The print_string u'Activities: $0 -> Where: $1, What: $2' would become
#   'Activities: artist -> Where: underwater, What: swimming'
#
#4. The controls (a list of lists) to create the dialog that to configure
#   your Function with.
#   Currently, there are three types of controls: TEXT, COMBO and CHECKBOX
#   which correspond to a QLineEdit, QComboBox and QCheckBox respectively.

#Each control requires three arguments in order to be created.
#1. Some descriptive text that's shown in a label.
#2. The control type, either TEXT, COMBO or CHECKBOX
#3. For TEXT this argument is the default text. It's not required.
#   For COMBO, the third and any following argument will be added as an item
#   to the combobox. Default arguments aren't allowed.(I'm willing to 
p#   (change this if shown an appropriate use-case.)
#   Checkboxes can either be checked or not so default arguments must either 
#   True or False.

#Functions are added like scripting functions (and they'll be 
# available in the same way).

functions.update({'append_function': func})

# If you would prefer that your function doesn't have a preview
# in the functions dialog add it to this list.

functions_no_preview = [append_text]
