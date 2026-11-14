"""The translation files puddletag ships, checked as translate.txt has
translators make them: update_translation.py collects puddletag's texts
into puddlestuff/translations/*.ts, Qt Linguist fills in the
translations, and each .ts is released to the .qm file puddletag loads.
"""
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PyQt6.QtCore import QTranslator
from PyQt6.QtWidgets import QApplication

from puddlestuff import translations

TRANSLATIONS = Path(translations.__file__).parent / 'translations'
TS_FILES = sorted(TRANSLATIONS.glob('*.ts'))


def language(ts):
    return ts.stem.removeprefix('puddletag_')


def messages(ts):
    """(context, source, translation) for each message of the .ts file.
    The translation is '' when there is none. lrelease puts every
    translation with text in the .qm, those marked unfinished too."""
    for context in ET.parse(ts).getroot().iter('context'):
        name = context.find('name').text
        for message in context.iter('message'):
            yield name, message.find('source').text, message.find('translation').text or ''


def edges(text):
    """The whitespace text starts and ends with."""
    return text[:len(text) - len(text.lstrip())], text[len(text.rstrip()):]


def every_file(failing=(), reason=''):
    """Every .ts file, those of the languages in failing marked as
    failing for this reason."""
    return [pytest.param(ts, id=language(ts),
                         marks=pytest.mark.xfail(strict=True, reason=reason) if language(ts) in failing else ())
            for ts in TS_FILES]


ALL = ('afr', 'cs', 'de', 'es_ES', 'fr', 'it', 'nl-nl', 'pl_PL', 'pt_BR', 'ru_RU', 'sv')
TEN = ALL[1:]  # all but afr
TWO = ('it', 'pl_PL')
OCCURRED = 'puddletag spells "occurred" as "occured"'

# The languages that translated each message before it was corrected.
CORRECTED = [
    pytest.param('Defaults', '<p>An error occurred while renaming the directory <b>{}</b> to <i>{}</i>.</p>'
                             '<p>Reason: <b>{}</b><br />File used: {}</p>', TEN, id='rename-directory'),
    pytest.param('Defaults', '<p>An error occurred while renaming the file <b>{}</b> to <i>{}</i>.</p>'
                             '<p>Reason: <b>{}</b></p>', TEN, id='rename-file'),
    pytest.param('Defaults', '<p>An error occurred while writing to <b>{}</b>.</p>'
                             '<p>Reason: <b>{}</b> (<i>See {} for debug info.</i>)</p>', TEN,
                 id='write-with-debug-info'),
    pytest.param('Defaults', '<p>An error occurred while writing to <b>{}</b>.</p>'
                             '<p>Reason: <b>{}</b>.</p><p>(<i>See {} for debug info.</i>)</p>', TWO,
                 id='write-with-debug-info-paragraphs'),
    pytest.param('Defaults', 'An error occurred while converting <b>{}</b>. ({})', TWO, id='convert'),
    pytest.param('Defaults', 'An error occurred while setting the modification time of <b>{}</b>. ({})', TWO,
                 id='modification-time'),
    pytest.param('Defaults', 'An error occurred while updating <b>{}</b>. ({})', TWO, id='update'),
    pytest.param('Defaults', 'An error occurred while writing to <b>{}</b>. ({})', ALL, id='write'),
    pytest.param('MusicLib', 'An error occurred while loading the {} library: <b>{}</b>', ALL,
                 id='load-library'),
    pytest.param('Playlist', 'An error occurred while reading <b>{}</b> ({})', ALL, id='read-playlist'),
]


@pytest.mark.parametrize('ts', every_file())
def test_every_text_listed_for_translators_is_in_every_ts_file(ts, monkeypatch):
    # translate.txt: "Then run update_translation.py with your desired
    # locale ... A translation file will be created in
    # puddlestuff/translations/puddletag_your_locale.ts".
    listed = []
    monkeypatch.setattr(translations, 'translate', lambda context, text: listed.append((context, text)))
    translations.dont_execute()
    assert len(listed) > 200
    sources = {(context, source) for context, source, _ in messages(ts)}
    # pylupdate6 leaves out empty texts
    assert {pair for pair in listed if pair[1]} - sources == set()


@pytest.mark.parametrize('ts', every_file())
def test_translations_keep_their_sources_leading_and_trailing_space(ts):
    # #588 "There must be a space after translated word" (Russian
    # 'Loading ' -> 'Загрузка'); the docs are silent on the other texts.
    assert [(context, source, text) for context, source, text in messages(ts)
            if text and edges(text) != edges(source)] == []


@pytest.mark.parametrize('ts', every_file())
def test_qm_shows_the_translations_of_its_ts(qapp, ts):
    # translate.txt: "To test your translation, generate a .qm file using
    # File->Release in Qt Linguist." QApplication.translate gives the source
    # back when the .qm has no translation; QTranslator.translate takes
    # ASCII only.
    translator = QTranslator()
    assert translator.load(str(ts.with_suffix('.qm')))
    QApplication.installTranslator(translator)
    try:
        shown = {(c, s): QApplication.translate(c, s) for c, s, _ in messages(ts)}
    finally:
        QApplication.removeTranslator(translator)
    assert shown == {(c, s): text or s for c, s, text in messages(ts)}


@pytest.mark.parametrize('ts', every_file(failing=ALL, reason=OCCURRED))
def test_no_text_misspells_occurred(ts):
    assert [source for _, source, _ in messages(ts) if 'occured' in source] == []


@pytest.mark.xfail(strict=True, reason=OCCURRED)
@pytest.mark.parametrize('context, source, languages', CORRECTED)
def test_corrected_messages_keep_their_translations(context, source, languages):
    # The languages that translate a message today keep their translation
    # when its spelling is corrected (synthetic: the list is read from the
    # .ts files).
    translated = {language(ts) for ts in TS_FILES
                  if any(c == context and s == source and t for c, s, t in messages(ts))}
    assert set(languages) <= translated


def test_russian_rename_errors():
    # The translator's own text, typo fixed (the docs are silent).
    ru = TRANSLATIONS / 'puddletag_ru_RU.ts'
    renames = {source.split(' while renaming the ')[1].split(' ')[0]: text
               for _, source, text in messages(ru) if ' while renaming the ' in source}
    assert renames == {
        'directory': '<p>Произошла ошибка во время переименования директории <b>{}</b> в <i>{}</i>.</p>'
                     '<p>Причина: <b>{}</b><br />Используемый файл: {}</p>',
        'file': '<p>Произошла ошибка во время переименования файла <b>{}</b> в <i>{}</i>.</p>'
                '<p>Причина: <b>{}</b></p>',
    }
