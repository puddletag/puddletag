# An interface specification for Tag Sources
#
# A Tag Source should define a class that derives from TagSOurce, and sets
# a module attribue "info" to an instance of that class in order to interface
# with puddletag
from puddlestuff.util import translate
from puddlestuff.constants import TEXT, CHECKBOX, SPINBOX, TAGLIST, COMBO


class UnimplementedMethod(Exception):
    pass


class TagSource():
    # A name for the tag source. Keep it short.
    name = "Generic Tag Source"

    # A list of tags to group album releases by.
    group_by = ["album", "artist"]

    # A ToolTip that displays when hovering above the Search box
    # Set to None to disable ToolTip
    tooltip = translate("Group", "HTML Tooltip Content")

    # A Set of preferences to display on the preference dialog box
    # Set to None to disable Preferences for this Tag Source
    preferences = [
                    [translate("Discogs", 'A Text Option'), TEXT, "Default Value"],
                    [translate("Discogs", 'A Checkbox Option'), CHECKBOX, True],  # Default value, True or False
                    [translate("Discogs", 'A Spinbox Integer'), SPINBOX, [0, 100, 50]],  # Minimum, Maximum, Default values
                    [translate("Discogs", 'A Tag List'), TAGLIST, []],  # Undocumented, no exemplar and unimplemented
                    [translate("Discogs", 'A Combobox Option'), COMBO,
                        [[translate("Discogs", 'Option 1'), translate("Discogs", 'Option 2')], 1]]  # List of option texts and default selection
                ]

    # Note the TAGLIST preference type is currently not implemented.
    # See: puddlestuff.webdb.SimpleDialog

    def retrieve(self, release):
        '''
        Called to retrieve release information when expanding a release in the Tag Sources Tree view

        :param release: A dict containing information about an album release
        :return: a 2-tuple containing
                    a dict of album release tags/fields and their values, and
                    a list of dicts containing album track tags/fields and their values
        '''
        raise UnimplementedMethod("TagsSource.retrieve")

    def keyword_search(self, text):
        '''
        Called when Search button is clicked, if the Search box contains some text

        :param text: The text in the Search box
        :return: A list of 2-tuples as described in retrieve() above
        '''
        raise UnimplementedMethod("TagsSource.keyword_search")

    def search(self, files_or_group, files=None):
        '''
        Called when Search button is clicked, if the Search box is empty

        :param files_or_group: if self.group_by is Falsey, a list of selected audio files as ModelTag instances.
                                (see puddlestuff.tagmodel.model_tag.ModelTag)
                               if if self.group_by is a list of attributes then the value of the first group_by tag.
                               For example if the first group_by tag is "artist" then this will be name of an artist
                               to search for.

        :param files: Provided only if self.group_by is defined. In which case it is the contents of the named group.
                      This will be a dict level for each remaining group_by tag, with a list of files at the bottom
                      (a ModelTag instances - see puddlestuff.tagmodel.model_tag.ModelTag).
        :return: A list of 2-tuples as described in retrieve() above
        '''
        raise UnimplementedMethod("TagsSource.search")

    def submit(self, files):
        '''
        If defined the a Submit button is presented, and when clicked calls here
        for submitting data from the list of suplied files (to the remote web database)

        If not implementing this do so explicitly with:

            delattr(self, "submit")

        in the Tag Sources __init__() method.

        :param files: a list of selected audio files as ModelTag instances.
                        (see puddlestuff.tagmodel.model_tag.ModelTag)
        :return: Nothing. No result is checked.
        '''
        raise UnimplementedMethod("TagsSource.submit")
