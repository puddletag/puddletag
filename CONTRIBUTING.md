# Contributing to puddletag

Thanks for helping. This file is for anyone who wants to fix a bug, add
a feature, or improve the docs or a translation.

- Questions and ideas go to
  [Discussions](https://github.com/puddletag/puddletag/discussions), bugs
  to the [issue tracker](https://github.com/puddletag/puddletag/issues).
  In puddletag, Help > Report a problem fills a report in for you.
- Issues labelled
  [newcomers](https://github.com/puddletag/puddletag/labels/newcomers)
  are a good place to start.
- For a larger change, open an issue first, so we can agree on the
  approach before you spend time on it.
- Translating needs no code: the [translation
  guide](https://docs.puddletag.net/source/translate.html) says how.

## Setting up

You need git and Python 3.14 or later (releases are built and tested on
3.15).

    git clone https://github.com/puddletag/puddletag.git
    cd puddletag
    python3 -m venv venv
    venv/bin/pip install -r requirements.txt -r requirements-dev.txt
    venv/bin/python puddletag [folder or files]

`-d` turns on debug logging. A few tests also need ffmpeg, mpcenc and
fpcalc (on Debian and Ubuntu: `ffmpeg musepack-tools
libchromaprint-tools`); without them, those tests are skipped.

## Running the tests

    venv/bin/pytest                    # everything
    venv/bin/pytest -m "not ui"        # without the main window's tests
    venv/bin/pytest tests/ui/test_smoke.py::test_open_dir_loads_files_and_tags
    venv/bin/pytest --cov --cov-report=term-missing

The tests run headless, in a temporary home folder and without the
network, so they never touch your settings or your music. Most make
their own audio files. Expected values come from the docs or from real
reports, not from what the code happens to do; a known bug is a strict
`xfail` that says what differs.

The spelling is checked too: run `venv/bin/codespell` from the repo
root (its settings are `[tool.codespell]` in `pyproject.toml`). A word
that is right but flagged (a name, an ID3 frame) goes in
`ignore-words-list`. A misspelling quoted from a report gets `[sic]`
after it or, where that would change a text the code uses,
`# codespell:ignore <word>` at the end of the line.

## Sending a pull request

- Branch from `master`, one topic to a pull request.
- Add tests: a fix comes with a test that fails without it.
- Text users see goes through `translate()` (see Translations).
- A change users will notice adds its line to `CHANGELOG.md` (see
  below).
- Before it's merged, the branch must be up to date with `master` (the
  pull request's "Update branch" button).

### Changelog

`CHANGELOG.md` follows [Keep a Changelog
1.1.0](https://keepachangelog.com/en/1.1.0/). Add your line under
`## [Unreleased]`, in Added, Changed, Deprecated, Removed, Fixed or
Security, in the same commit as the change. Only what users notice or
have to act on gets a line: a new feature, a feature that didn't work at
all, lost data, a common crash, a saved pattern or action that now gives
a different result, settings reset, a new dependency. Not refactors,
tests, small fixes or dependency bumps. Write it for users (what they
see and do) and name the issues it fixes (`#1105`).

## What CI checks

Every pull request runs the tests on Python 3.14 and 3.15, builds the
docs and checks the spelling. The required check, "All tests passed",
passes only when all of them did. Coverage goes to
[Codecov](https://app.codecov.io/gh/puddletag/puddletag), whose checks
only inform. To reproduce a failure, run the same pytest command
locally; CI installs the system packages listed in
`.github/workflows/tests.yml`.

## Translations

When you add or change a text in `translate()`, run `venv/bin/python
update_translation.py de` (any existing language): it refreshes every
`.ts` file in `puddlestuff/translations/`, and
`tests/unit/test_translation_files.py` fails until you do. When you
correct a text that already has translations, correct its `<source>` in
every `.ts` file as well (a refresh would drop its translations), then
rebuild the `.qm` files with `lrelease puddlestuff/translations/*.ts`
(Debian's `qttools5-dev-tools`).

## Docs

The site, [docs.puddletag.net](https://docs.puddletag.net/), is built
from `docs/` with Sphinx and published on every push to `master`. To build it as CI does, in a venv
of its own with `requirements-docs.txt` installed: `sphinx-build -W
--keep-going -b html docs docs/_build/html` (git ignores `docs/_build/`).
The pages' pictures are made by `venv/bin/python
docs/make_screenshots.py`; rerun it when a window they show changes.

## Dependencies

`requirements.txt` pins every dependency exactly, the transitive ones
too, and the published package installs exactly those: that's on
purpose, so don't loosen it. To change one, edit `requirements.in`
(minimum versions only) and run `venv/bin/pip-compile`; the dev tools
and the docs have their own `requirements-dev.in` and
`requirements-docs.in`, compiled the same way. CI tests both Pythons
with these pins, so each pin needs wheels for both.

## Releases

The maintainer makes them: [RELEASING.md](RELEASING.md) says how.
