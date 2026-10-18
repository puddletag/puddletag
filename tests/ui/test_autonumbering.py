"""The Autonumbering Wizard (the Tools menu, menus.txt:217-237; tut2.txt:77),
run from the main window as a user runs it: Ctrl+K, the Tools menu and the
toolbar, with clicks and typing in the wizard. Each result is checked in
the files and in the table. Synthetic files and tags.
"""
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialogButtonBox, QMessageBox, QStyle, QStyleOptionButton

from puddlestuff import audioinfo
from puddlestuff.helperwin import AutonumberDialog

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier

COMMAND = 'Autonumbering &Wizard...'


def load(mainwin, qtbot, user, folder, paths):
    """Opens the folder, its subfolders too, and gives the table the focus."""
    mainwin.openDir(str(folder), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == len(paths))
    user.activate()
    table.setFocus()
    return table


@pytest.fixture
def four(mainwin, make_audio, tmp_path, qtbot, user):
    """Four files in one folder, track 9 in each, in this order in the table."""
    music = tmp_path / 'music'
    paths = [make_audio(f'0{i}.mp3', music, title=f'title {i}', tracknumber='9') for i in range(1, 5)]
    table = load(mainwin, qtbot, user, music, paths)
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]
    return table, paths


@pytest.fixture
def discs(mainwin, make_audio, tmp_path, qtbot, user):
    """Five files in one folder, track 9 in each: three on disc 1, then two
    on disc 2."""
    music = tmp_path / 'music'
    paths = [make_audio(f'0{i}.mp3', music, title=f'title {i}', tracknumber='9', discnumber=disc)
             for i, disc in enumerate(['1', '1', '1', '2', '2'], 1)]
    table = load(mainwin, qtbot, user, music, paths)
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]
    return table, paths


@pytest.fixture
def folders(mainwin, make_audio, tmp_path, qtbot, user):
    """Three files in folder cd1 and two in cd2, track 9 in each. The table
    sorts them by file name, so its rows alternate between the folders."""
    music = tmp_path / 'music'
    paths = [make_audio(name, music / folder, title=f'{folder} {name}', tracknumber='9')
             for folder, name in [('cd1', '01.mp3'), ('cd1', '02.mp3'), ('cd1', '03.mp3'),
                                  ('cd2', '01.mp3'), ('cd2', '02.mp3')]]
    table = load(mainwin, qtbot, user, music, paths)
    assert [audio.filepath for audio in table.model().taginfo] == [str(paths[i]) for i in (0, 3, 1, 4, 2)]
    return table, paths


def select_all(user):
    user.click_cell(user.cell(0, 'title'))
    user.press(Key.Key_A, Ctrl)


def opened(qtbot, user):
    """The wizard once it's open, made the active window: it opens inactive
    on the offscreen platform, and keys go to the active window."""
    qtbot.waitUntil(lambda: isinstance(QApplication.activeModalWidget(), AutonumberDialog))
    dialog = QApplication.activeModalWidget()
    user.activate(dialog)
    return dialog


def wizard(user, qtbot):
    """Opens the wizard with Ctrl+K."""
    user.press(Key.Key_K, Ctrl)
    return opened(qtbot, user)


def run(user, dialog):
    """Clicks OK. Writing several files shows a progress window, which closes
    after the last one is written; activate waits for that."""
    user.click(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok))
    user.activate()


def cancel(user, dialog):
    user.click(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Cancel))
    user.activate()


def tick(user, box):
    """Clicks the check box's indicator, which flips it."""
    option = QStyleOptionButton()
    box.initStyleOption(option)
    indicator = box.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, box)
    checked = box.isChecked()
    user.click(box, indicator.center())
    assert box.isChecked() != checked


def retype(user, widget, text):
    """Clicks into the field, selects its text and types over it, or with no
    text deletes it."""
    user.click(widget)
    user.press(Key.Key_A, Ctrl)
    if text:
        user.type(text)
    else:
        user.press(Key.Key_Delete)


def in_files(paths, field):
    return [audioinfo.Tag(str(p)).get(field) for p in paths]


def in_table(table, paths, field):
    """The table's values, in the order of paths rather than of its rows."""
    values = {audio.filepath: audio.get(field) for audio in table.model().taginfo}
    return [values[str(p)] for p in paths]


AUTONUMBER = {
    'Ctrl+K': lambda user: user.press(Key.Key_K, Ctrl),
    'Tools menu': lambda user: user.click_menu(COMMAND),
    'toolbar': lambda user: user.click_toolbar(COMMAND),
}


@pytest.mark.parametrize('autonumber', AUTONUMBER.values(), ids=AUTONUMBER.keys())
def test_numbers_the_selected_files(user, four, qtbot, autonumber):
    # The wizard "lets you number selected tracks sequentially" (tut2.txt:77),
    # from Start 1 as its screenshot shows (tut2.txt:83). The unselected
    # fourth file keeps its track.
    table, paths = four
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(2, 'title'), Shift)
    autonumber(user)
    dialog = opened(qtbot, user)
    run(user, dialog)
    expected = [['1'], ['2'], ['3'], ['9']]
    assert in_files(paths, 'track') == expected
    assert in_table(table, paths, 'track') == expected


def test_needs_a_selection(user, four, mainwin):
    # It numbers "selected tracks" (tut2.txt:77): with none selected the
    # command is disabled and Ctrl+K opens nothing.
    user.click_cell(user.cell(0, 'title'))
    assert user.action(COMMAND).isEnabled()
    user.click_cell(user.cell(0, 'title'), Ctrl)
    assert user.table.selectedRows == []
    assert not user.action(COMMAND).isEnabled()
    user.press(Key.Key_K, Ctrl)
    assert mainwin.findChildren(AutonumberDialog) == []


def test_grouped_by_discnumber(user, discs, qtbot):
    # "Group tracks using pattern: Enter a pattern to group the tracks by.
    # Eg. if you would like to number tracks by discnumber enter
    # %discnumber%." (menus.txt:227-229) The pattern shows once "Restart
    # numbering at each directory group" is ticked (menus.txt:223); each disc
    # counts from 1.
    table, paths = discs
    select_all(user)
    dialog = wizard(user, qtbot)
    tick(user, dialog._restart_numbering)
    retype(user, dialog.grouping, '%discnumber%')
    run(user, dialog)
    expected = [['1'], ['2'], ['3'], ['1'], ['2']]
    assert in_files(paths, 'track') == expected
    assert in_table(table, paths, 'track') == expected
    assert in_files(paths, 'discnumber') == [['1'], ['1'], ['1'], ['2'], ['2']]


def test_discnumber_per_folder(user, folders, qtbot):
    # "Eg if you split the tracks by %__dirpath% and output field
    # %discnumber%. ... All tracks in the first folder will have
    # discnumber=1. All tracks in folder 2 will have discnumber=2 and so on."
    # (menus.txt:235-237, under "Increase counter only on group change",
    # menus.txt:233). Written "Instead of writing to the track field"
    # (menus.txt:225): track is kept.
    table, paths = folders
    select_all(user)
    dialog = wizard(user, qtbot)
    tick(user, dialog._restart_numbering)
    retype(user, dialog.grouping, '%__dirpath%')
    retype(user, dialog.output_field.lineEdit(), 'discnumber')
    tick(user, dialog.count_by_group)
    run(user, dialog)
    expected = [['1'], ['1'], ['1'], ['2'], ['2']]
    assert in_files(paths, 'discnumber') == expected
    assert in_table(table, paths, 'discnumber') == expected
    assert in_files(paths, 'track') == [['9']] * 5
    assert in_table(table, paths, 'track') == [['9']] * 5


def test_split_by_directory(user, folders, qtbot):
    # "If you'd like to split by directory, *%__dirpath%*" (menus.txt:230):
    # each folder counts from 1.
    table, paths = folders
    select_all(user)
    dialog = wizard(user, qtbot)
    tick(user, dialog._restart_numbering)
    retype(user, dialog.grouping, '%__dirpath%')
    run(user, dialog)
    expected = [['1'], ['2'], ['3'], ['1'], ['2']]
    assert in_files(paths, 'track') == expected
    assert in_table(table, paths, 'track') == expected


def test_discs_in_any_order(user, mainwin, make_audio, tmp_path, qtbot):
    # The docs don't say; this is what puddletag does: files of disc 1 and
    # disc 2 alternating in the table still count from 1 within each disc.
    music = tmp_path / 'music'
    paths = [make_audio(f'0{i}.mp3', music, title=f'title {i}', tracknumber='9', discnumber=disc)
             for i, disc in enumerate(['1', '2', '1', '2'], 1)]
    table = load(mainwin, qtbot, user, music, paths)
    select_all(user)
    dialog = wizard(user, qtbot)
    tick(user, dialog._restart_numbering)
    retype(user, dialog.grouping, '%discnumber%')
    run(user, dialog)
    expected = [['1'], ['1'], ['2'], ['2']]
    assert in_files(paths, 'track') == expected
    assert in_table(table, paths, 'track') == expected


def test_file_field_refused(user, four, qtbot, dialogs):
    # "...any field except the file fields (such as __filename and __path),
    # which are refused." (menus.txt:225) The message "Invalid field..."
    # shows, the wizard stays open and the files keep their names.
    table, paths = four
    dialogs.answer('QMessageBox.critical', QMessageBox.StandardButton.Ok)
    select_all(user)
    dialog = wizard(user, qtbot)
    tick(user, dialog._restart_numbering)
    retype(user, dialog.output_field.lineEdit(), '__filename')
    user.click(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok))
    user.activate(dialog)
    assert [(name, args[1:]) for name, args, kwargs in dialogs.calls] == [
        ('QMessageBox.critical', ('Invalid field...', 'The output field specified was invalid. Please check '
                                                      'your values.'))]
    assert dialog.isVisible()
    assert sorted(p.name for p in paths[0].parent.iterdir()) == ['01.mp3', '02.mp3', '03.mp3', '04.mp3']
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]
    cancel(user, dialog)


def test_original_filename_field(user, four, qtbot):
    # The docs don't say; this is what puddletag does: `filename` is ID3's
    # original-filename tag, a tag field and not a file field, so it's
    # written and the files keep their names.
    table, paths = four
    select_all(user)
    dialog = wizard(user, qtbot)
    tick(user, dialog._restart_numbering)
    retype(user, dialog.output_field.lineEdit(), 'filename')
    run(user, dialog)
    expected = [['1'], ['2'], ['3'], ['4']]
    assert in_files(paths, 'filename') == expected
    assert in_table(table, paths, 'filename') == expected
    assert sorted(p.name for p in paths[0].parent.iterdir()) == ['01.mp3', '02.mp3', '03.mp3', '04.mp3']
    assert in_files(paths, 'track') == [['9']] * 4


def test_defaults(user, four, qtbot):
    # Start 1, padding 1 and both boxes unticked are in the screenshot
    # (tut2.txt:83); "Restart numbering at each directory group" is "Off by
    # default" (menus.txt:223). The docs don't say the rest; this is what
    # puddletag does: Number of tracks shows the 4 selected files, and the
    # restart options start as %__dirpath%, track and unticked.
    select_all(user)
    dialog = wizard(user, qtbot)
    assert dialog._start.value() == 1
    assert dialog._padlength.value() == 1
    assert not dialog._separator.isChecked()
    assert dialog._numtracks.value() == 4
    assert not dialog._restart_numbering.isChecked()
    assert not dialog.grouping.isVisible()
    assert not dialog.output_field.isVisible()
    assert not dialog.count_by_group.isVisible()
    tick(user, dialog._restart_numbering)
    assert dialog.grouping.text() == '%__dirpath%'
    assert dialog.output_field.currentText() == 'track'
    assert not dialog.count_by_group.isChecked()
    cancel(user, dialog)


def test_start_and_padding(user, four, qtbot):
    # The docs don't say; this is what puddletag does: Start 5 and padding 2
    # number the files 05, 06, 07 and 08.
    table, paths = four
    select_all(user)
    dialog = wizard(user, qtbot)
    retype(user, dialog._start, '5')
    retype(user, dialog._padlength, '2')
    run(user, dialog)
    expected = [['05'], ['06'], ['07'], ['08']]
    assert in_files(paths, 'track') == expected
    assert in_table(table, paths, 'track') == expected


def test_separator(user, four, qtbot):
    # The docs don't say; this is what puddletag does: the separator box adds
    # the number of files after a slash, 1/4 to 4/4.
    table, paths = four
    select_all(user)
    dialog = wizard(user, qtbot)
    tick(user, dialog._separator)
    run(user, dialog)
    expected = [['1/4'], ['2/4'], ['3/4'], ['4/4']]
    assert in_files(paths, 'track') == expected
    assert in_table(table, paths, 'track') == expected


def test_separator_padded(user, four, qtbot):
    # The docs don't say; this is what puddletag does: the padding applies to
    # the total too, 01/04 to 04/04.
    table, paths = four
    select_all(user)
    dialog = wizard(user, qtbot)
    retype(user, dialog._padlength, '2')
    tick(user, dialog._separator)
    run(user, dialog)
    expected = [['01/04'], ['02/04'], ['03/04'], ['04/04']]
    assert in_files(paths, 'track') == expected
    assert in_table(table, paths, 'track') == expected


def test_separator_per_folder(user, folders, qtbot):
    # The docs don't say; this is what puddletag does: with the numbering
    # restarted per folder, the total is the files in that folder, 3 for cd1
    # and 2 for cd2.
    table, paths = folders
    select_all(user)
    dialog = wizard(user, qtbot)
    tick(user, dialog._restart_numbering)
    tick(user, dialog._separator)
    run(user, dialog)
    expected = [['1/3'], ['2/3'], ['3/3'], ['1/2'], ['2/2']]
    assert in_files(paths, 'track') == expected
    assert in_table(table, paths, 'track') == expected


def test_number_of_tracks(user, four, qtbot):
    # The docs don't say; this should happen: with the separator ticked the
    # Number of tracks box is usable, and what is typed in it is the total,
    # 1/12 to 4/12.
    table, paths = four
    select_all(user)
    dialog = wizard(user, qtbot)
    tick(user, dialog._separator)
    assert dialog._numtracks.isEnabled()
    retype(user, dialog._numtracks, '12')
    run(user, dialog)
    expected = [['1/12'], ['2/12'], ['3/12'], ['4/12']]
    assert in_files(paths, 'track') == expected
    assert in_table(table, paths, 'track') == expected


@pytest.mark.xfail(strict=True, reason='the total of a count by group is its group\'s files, not the groups')
def test_disc_total(user, folders, qtbot):
    # The docs don't say; this should happen: counting by group into
    # discnumber with the separator ticked, the total is the number of
    # groups (2 folders), so 1/2 in cd1 and 2/2 in cd2.
    table, paths = folders
    select_all(user)
    dialog = wizard(user, qtbot)
    tick(user, dialog._restart_numbering)
    tick(user, dialog._separator)
    retype(user, dialog.grouping, '%__dirpath%')
    retype(user, dialog.output_field.lineEdit(), 'discnumber')
    tick(user, dialog.count_by_group)
    run(user, dialog)
    expected = [['1/2'], ['1/2'], ['1/2'], ['2/2'], ['2/2']]
    assert in_files(paths, 'discnumber') == expected
    assert in_table(table, paths, 'discnumber') == expected


def test_remembers_its_settings(user, folders, qtbot):
    # The docs don't say; this is what puddletag does: the next time the
    # wizard opens it has the values of the last run.
    table, paths = folders
    select_all(user)
    dialog = wizard(user, qtbot)
    retype(user, dialog._start, '3')
    retype(user, dialog._padlength, '2')
    tick(user, dialog._separator)
    tick(user, dialog._restart_numbering)
    retype(user, dialog.grouping, '%__dirpath%')
    retype(user, dialog.output_field.lineEdit(), 'discnumber')
    tick(user, dialog.count_by_group)
    run(user, dialog)
    dialog = wizard(user, qtbot)
    assert dialog._start.value() == 3
    assert dialog._padlength.value() == 2
    assert dialog._separator.isChecked()
    assert dialog._restart_numbering.isChecked()
    assert dialog.grouping.text() == '%__dirpath%'
    assert dialog.output_field.currentText() == 'discnumber'
    assert dialog.count_by_group.isChecked()
    cancel(user, dialog)


def test_cancel(user, four, qtbot):
    # The docs don't say; this is what puddletag does: Cancel writes nothing
    # and doesn't remember what was typed.
    table, paths = four
    select_all(user)
    dialog = wizard(user, qtbot)
    retype(user, dialog._start, '5')
    cancel(user, dialog)
    assert not dialog.isVisible()
    assert in_files(paths, 'track') == [['9']] * 4
    assert in_table(table, paths, 'track') == [['9']] * 4
    dialog = wizard(user, qtbot)
    assert dialog._start.value() == 1
    cancel(user, dialog)


def test_hidden_output_field(user, four, qtbot):
    # "The pattern, **Output field** and **Increase counter only on group
    # change** options are shown only once it is checked." (menus.txt:223)
    # Unticking "Restart numbering" hides the Output field again, and a
    # hidden option doesn't apply, so track is numbered and discnumber is
    # not written.
    table, paths = four
    select_all(user)
    dialog = wizard(user, qtbot)
    tick(user, dialog._restart_numbering)
    retype(user, dialog.output_field.lineEdit(), 'discnumber')
    tick(user, dialog._restart_numbering)
    run(user, dialog)
    expected = [['1'], ['2'], ['3'], ['4']]
    assert in_files(paths, 'track') == expected
    assert in_table(table, paths, 'track') == expected
    assert in_files(paths, 'discnumber') == [None] * 4


def test_hidden_count_by_group(user, four, qtbot):
    # "The pattern, **Output field** and **Increase counter only on group
    # change** options are shown only once it is checked." (menus.txt:223)
    # Unticking "Restart numbering" hides "Increase counter only on group
    # change", which then doesn't apply, so every file gets its own number.
    table, paths = four
    select_all(user)
    dialog = wizard(user, qtbot)
    tick(user, dialog._restart_numbering)
    tick(user, dialog.count_by_group)
    tick(user, dialog._restart_numbering)
    run(user, dialog)
    expected = [['1'], ['2'], ['3'], ['4']]
    assert in_files(paths, 'track') == expected
    assert in_table(table, paths, 'track') == expected


def test_empty_pattern(user, four, qtbot, dialogs):
    # The docs don't say; this is what puddletag does: an empty pattern shows
    # the message "Field empty..." and writes nothing.
    table, paths = four
    dialogs.answer('QMessageBox.critical', QMessageBox.StandardButton.Ok)
    select_all(user)
    dialog = wizard(user, qtbot)
    tick(user, dialog._restart_numbering)
    retype(user, dialog.grouping, '')
    run(user, dialog)
    assert [(name, args[1:]) for name, args, kwargs in dialogs.calls] == [
        ('QMessageBox.critical', ('Field empty...', 'The field specified to use as a directory splitter was '
                                                    'invalid. Please check your values.'))]
    assert in_files(paths, 'track') == [['9']] * 4
    assert in_table(table, paths, 'track') == [['9']] * 4


def test_empty_output_field(user, four, qtbot, dialogs):
    # The docs don't say; this is what puddletag does: an empty Output field
    # shows the message "Field empty..." and writes nothing.
    table, paths = four
    dialogs.answer('QMessageBox.critical', QMessageBox.StandardButton.Ok)
    select_all(user)
    dialog = wizard(user, qtbot)
    tick(user, dialog._restart_numbering)
    retype(user, dialog.output_field.lineEdit(), '')
    run(user, dialog)
    assert [(name, args[1:]) for name, args, kwargs in dialogs.calls] == [
        ('QMessageBox.critical', ('Field empty...', 'The output field specified was invalid. Please check your '
                                                    'values.'))]
    assert in_files(paths, 'track') == [['9']] * 4
    assert in_table(table, paths, 'track') == [['9']] * 4


def test_empty_pattern_without_restart(user, four, qtbot, dialogs):
    # The docs don't say; this is what puddletag does: the pattern only
    # applies when "Restart numbering" is ticked (menus.txt:223), so an
    # empty one isn't refused while it's unticked.
    table, paths = four
    select_all(user)
    dialog = wizard(user, qtbot)
    tick(user, dialog._restart_numbering)
    retype(user, dialog.grouping, '')
    tick(user, dialog._restart_numbering)
    run(user, dialog)
    assert dialogs.calls == []
    expected = [['1'], ['2'], ['3'], ['4']]
    assert in_files(paths, 'track') == expected
    assert in_table(table, paths, 'track') == expected


def test_empty_pattern_keeps_the_wizard_open(user, four, qtbot, dialogs):
    # The docs don't say; this should happen: after the message about the
    # empty pattern the wizard stays open, so the user can fix it.
    dialogs.answer('QMessageBox.critical', QMessageBox.StandardButton.Ok)
    select_all(user)
    dialog = wizard(user, qtbot)
    tick(user, dialog._restart_numbering)
    retype(user, dialog.grouping, '')
    run(user, dialog)
    assert dialog.isVisible()
