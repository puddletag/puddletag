# AGENTS.md

puddletag is a PyQt6 audio tag editor with a spreadsheet layout (similar to
Mp3tag). The importable package is `puddlestuff/`; `puddletag` at the repo root
is the launcher script, not a module.

## Commands

- Run from source: `venv/bin/python puddletag [dir-or-files]` (`-d` for debug
  logging, `--langfile path.qm`, `--fontsize N`). The local `venv/` already has
  the dependencies.
- Dependencies and CI: read `CONTRIBUTING.md`; publishing and releases
  (`release.py`): read `RELEASING.md`. Read both before changing
  `requirements*`, `setup.py`, `release.py` or `.github/`. A push to
  `master` publishes a public pre-release to TestPyPI.
- Tests (pytest, run headless):
  - Spelling: codespell is the one linter. `venv/bin/codespell` from the
    repo root (no arguments) checks the tree with `[tool.codespell]` in
    `pyproject.toml`; `tests/unit/test_spelling.py` fails on what it
    finds. CONTRIBUTING.md says how to accept a word or quote a
    misspelling.
  - `venv/bin/pytest` runs everything. Add `-m "not ui"` to skip the tests that
    build the main window, or name one test:
    `venv/bin/pytest tests/ui/test_smoke.py::test_open_dir_loads_files_and_tags`.
  - Coverage: `venv/bin/pytest --cov --cov-report=term-missing`.
  - `tests/conftest.py` points HOME and the XDG dirs at a temp sandbox before
    puddlestuff is imported, because it fixes its config paths at import time.
    Never import puddlestuff in a test before that conftest has run.
  - Autouse guards fail a test on any modal dialog without a queued answer
    (`dialogs.answer('QMessageBox.question', ...)`) and on any network
    access. Both also record what happened, so a test still fails when
    puddletag swallows the error in a bare `except:`.
  - `make_audio` creates synthetic files: one second of silence (longer
    with `seconds=`) carrying only the tags the test passes (its docstring
    says how each format is made). Without a program or encoder a format
    needs, its tests skip
    locally but fail in CI (the `CI` env var is set).
  - Expected values come from the docs (`docs/`) or from real reports
    (linked issues, discussions, scripts users shared), never from reading
    the code. Where the code disagrees, flag it to the maintainer before
    writing the case either way: users are likely used to what the program
    does, so the docs may be what needs fixing. Once they decide the code
    is wrong, the case is a strict `xfail` that names what differs or
    links the open issue, so it fails once fixed. Invented inputs are
    labelled synthetic.
  - Every format puddletag registers is tested with every feature (file
    information, field names, multiple values and non-ASCII text, cover
    art, removing fields and tags), on files `make_audio` creates at
    test time. External files are only for what synthetic ones can't
    show: tags as other programs wrote them.
  - Real files come from public-domain sources with a reliable license
    (Musopen's CC0 and public-domain recordings, Wikimedia Commons), not
    from anyone's library. Each fixture keeps the file's tags byte for byte
    and only the first audio frames, and a README next to the fixtures
    records its source URL and license.
  - `mainwin` builds a fresh MainWin on an empty profile. Its teardown
    disconnects the module-level signal emitters that MainWin wires to its
    own widgets.
- Import `puddlestuff.resource` before other puddlestuff modules outside the
  app. It registers the `data:`/`icons:`/`translations:` Qt search paths that
  other modules use at import time.
- Docs: Sphinx sources are in `docs/`. CI builds them and publishes the site,
  docs.puddletag.net, on every push to master; CONTRIBUTING.md's Docs section
  has the build command. `make html` there builds a local copy into
  `docs/_build/`, which git ignores.
- Translations: `python update_translation.py <locale>` runs `pylupdate6` to
  refresh `puddlestuff/translations/puddletag_<locale>.ts`. User-visible
  strings go through `translate(context, text)` from `puddlestuff.translations`.

## Architecture

**Startup and config.** The `puddletag` script builds `MainWin` from
`puddlestuff/puddletag.py`. Config is JSON under `$XDG_CONFIG_HOME/puddletag/`,
read and written through `PuddleConfig` in `puddleobjects.py` (its docstring
still says INI). User plugins, actions and translations live under
`$XDG_DATA_HOME/puddletag/`. `constants.py` defines all paths.

**Components are wired by signal name.** Docks and the main window never
connect to each other directly. Each control declares `self.emits` (signal
names) and `self.receives` (`(name, slot)` pairs), and `connect_controls()` in
`puddletag.py` matches them by name at startup. `PuddleDock._controls` maps
control names to instances. A dock is a module in `puddlestuff/mainwin/` with a
`control = (title, WidgetClass, dock_area, visible)` tuple, listed in
`create_tool_windows()` and in `update_translation.parse_dialogs()`. Plugins
wire themselves with `puddlestuff.plugins.connect_control()`.

**Shared `status` object.** One `PuddleStatus`, injected as a module global
(`mainwin.funcs.status`, `tagmodel.status`, `plugins.status`, ...), exposes
state such as `selectedfiles`, `selectedrows`, `previewmode`, `table`, `model`
and `dialogs`. Read anything, but write only keys you created.

**Menus, toolbar and shortcuts are data.** `puddlestuff/data/shortcuts` defines
each action (`name`, `command`, `control`, the `enabled` signal, icon, tooltip)
and `puddlestuff/data/menus` places actions by name. `connect_actions()` in
`loadshortcuts.py` connects `command` to a function in `mainwin/funcs.py` when
`control` is `mainwin`, or else to a method on the named control. Both files
are copied into the user's config dir and only replaced when their `"version"`
is below `loadshortcuts.__version__` (currently 34 in all three places). Bump
all three together when changing them: existing users otherwise keep their
stale copy, and a bump overwrites their customizations.

**Tag I/O (`puddlestuff/audioinfo/`).** One module per format family (`id3`,
`vorbis`, `apev2`, `mp4`, `wma`) on top of mutagen, each registered through
`filetype`/`filetypes`. `audioinfo.Tag(filename)` picks the class by extension,
then by mutagen's score. A tag is dict-like: a field name maps to a list of
strings, and `__`-prefixed keys are read-only file info (`__path`, `__length`,
`__image`, ...). In `mp4.py`, a new atom needs an entry in both the
atom-to-name dict and the name-to-(getter, setter) dict. Cross-format aliases
are set by `setmapping()` at the bottom of `audioinfo/__init__.py`.

**Scripting engine.** `findfunc.py` parses pattern strings (`%field%`,
`$func(args)`) with pyparsing, for format, tag-to-filename, filename-to-tag and
actions. The functions are the `functions` dict in `functions.py`, whose top
docstring is the contract: the first parameter's name picks the input (`text`
for a field value; `tags`/`m_tags`/`r_tags` for tag dicts), `None` is returned
on failure, and the docstring format generates the function's editor UI in
`actiondlg.py`. Actions are saved function chains (`.action` files).

**Main table.** `tagmodel.py` holds `TagModel`/`TagTable`: the loaded files,
the per-file undo history, and preview mode (edits staged in memory until
written; see also `mainwin/previews.py`).

**Tag sources (`puddlestuff/tagsources/`, UI in `mainwin/tagsources.py`).**
Web lookups, each module exposing `info`, a class with `name`, `group_by`,
`search`/`keyword_search` and `retrieve`. Built-in modules are listed by name
in `tagsources/__init__.py`, where an `ImportError` (e.g. a missing optional
dependency) only logs at debug level, so the source silently disappears.
`tagsources/mp3tag/` runs Mp3tag `.src` web-source scripts.

**Plugins.** A directory with an `info` file (ConfigObj INI whose `[info]`
section needs `name`, `author`, `description`, `version` and
`puddletag_version`, or the plugin is skipped) and an `__init__.py` that may
export `functions`, `functions_no_preview`, `tagsources`, `dialogs`,
`musiclibs` and/or `init(parent)`. Plugins are found in `puddlestuff/plugins/`
and in the user plugin dir, and imported as `puddlestuff.plugins.<dir>` only if
enabled in the `plugins.to_load` config key.
