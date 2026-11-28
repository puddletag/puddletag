# Releasing

How the maintainer cuts a puddletag release, beta or final, and what CI
publishes. Contributors don't need any of this: see
[CONTRIBUTING.md](CONTRIBUTING.md).

A release is one command, run on `master` once "All tests passed" has
passed on its last commit:

    venv/bin/python release.py

It asks which version, checks that the release can go out, opens your
editor on the notes, shows what it will do and asks once; then it
commits, tags and pushes, and CI publishes. `venv/bin/python release.py
3.0.0b1` names the version and skips the menus; `--yes` skips the last
question. It needs `gh`, logged in (`gh auth login`).

`--dry-run` makes no release: it runs every check and opens your editor
as for real, then shows what a release would change in
`puddlestuff/__init__.py` and `CHANGELOG.md` (and in `master`'s
`CHANGELOG.md`, for a fix release) and the commit, tag and push it would
make, and stops without asking. Nothing is written or pushed. A check
that fails stops it as it would stop a release, so a dry run that gets
to the end means the release can go out.

## Versions

Versions are written in PEP 440's normal form, the one pip and PyPI
use: `3.0.0b1` (a beta), `3.0.0rc1` (a release candidate), `3.0.0`
(final), `3.0.1`. A version has three numbers; `a`, `b` or `rc` and a
number make it a pre-release. The command refuses any other spelling
(`v3.0.0`, `3.0.0-beta1`, `3.0`) and `.dev` and `.post` versions. The
tag is the bare version, as since 2.0.1: `3.0.0b1`, no `v`.
`version_string` in `puddlestuff/__init__.py` is the one place the
version lives, and only the release command writes it.

With no version given, it offers the ones that can come next:

- after a final release (2.5.0): `1) major: 3.0.0`, `2) minor: 2.6.0`,
  `3) patch: 2.5.1`; then, for the one chosen, `1) beta: 3.0.0b1`,
  `2) release candidate: 3.0.0rc1`, `3) final: 3.0.0`;
- after a beta (3.0.0b1): `1) next beta: 3.0.0b2`, `2) release
  candidate: 3.0.0rc1`, `3) final: 3.0.0`;
- after a release candidate (3.0.0rc1): `1) next release candidate:
  3.0.0rc2`, `2) final: 3.0.0`;
- after an alpha (3.0.0a1): `1) next alpha: 3.0.0a2`, `2) beta:
  3.0.0b1`, `3) release candidate: 3.0.0rc1`, `4) final: 3.0.0`;
- on a maintenance branch (3.0.x, at 3.0.0): `1) beta: 3.0.1b1`,
  `2) release candidate: 3.0.1rc1`, `3) final: 3.0.1`.

An answer that isn't one of the numbers asks again.

## What it checks

Each check stops the command before anything changes, saying why:

1. The version is in normal form and above every tag. Tags that aren't
   versions (`RC1`, `rm`) don't count; older spellings (`v2.0.0`,
   `1.0.0beta6`) count by their value. On a maintenance branch, the
   version is of the branch's line (3.0 on 3.0.x) and above that line's
   tags.
2. The branch is `master` or a maintenance branch, and, after a fetch,
   HEAD is the same commit on `origin`: nothing to push, nothing to
   pull. `puddlestuff/__init__.py` and `CHANGELOG.md` have no local
   changes. Your other changes, staged or not, stay out of the release
   commit and stay as they are.
3. The tag exists neither here nor on GitHub, and PyPI doesn't have the
   version.
4. "All tests passed" passed on HEAD's commit. While CI is still
   running on it, the command waits; if no run shows up within a
   minute, it stops.
5. There are notes: lines under `[Unreleased]`, or, for a final release
   after pre-releases, in their sections.

## The notes

It opens the editor `git commit` opens (`GIT_EDITOR`, `core.editor`,
`VISUAL`, `EDITOR`) on `[Unreleased]`'s text, to trim or reword. An
empty text stops it, and so does a `#` or `##` heading. The text
becomes the version's section of `CHANGELOG.md`, under a new empty
`[Unreleased]`, and the text of its GitHub Release page.

A final release after pre-releases holds everything since the last
final. For 3.0.0 after 3.0.0b1, 3.0.0b2 and 3.0.0rc1, the editor opens
on `[Unreleased]` and those sections merged under one set of headings:
Added, Changed, Deprecated, Removed, Fixed and Security, in that order,
each with `[Unreleased]`'s lines first and then each pre-release's,
newest first; text above a section's first heading comes first. The
pre-releases' sections and their links leave `CHANGELOG.md`, and 3.0.0
gets one section, compared with 2.5.0. Their GitHub Release pages keep
their notes.

## What it does

It shows the version, whether it's a pre-release, and the notes, and
asks `Release 3.0.0b1? [y/N]`. On yes, it:

- sets `version_string`;
- makes the notes `## [3.0.0b1] - 2026-12-01` (today's date) under a
  new empty `## [Unreleased]`, with the comparison link at the bottom:
  `[3.0.0b1]: https://github.com/puddletag/puddletag/compare/2.5.0...3.0.0b1`.
  A pre-release is compared with the tag before it, a final with the
  last final; `[Unreleased]` is compared from the new tag;
- commits only those two files, as `chore(release): 3.0.0b1`;
- makes the annotated tag `3.0.0b1`, whose message is
  `puddletag 3.0.0b1` (git signs it once you set `tag.gpgSign` and a
  signing key);
- pushes the branch and the tag, and nothing else, in one atomic push:
  both land or neither does. If the push is refused, it removes the
  commit and the tag and puts the two files back.

Then it follows CI's run on the tag (`gh run watch`) and prints the
PyPI and GitHub links.

## What CI does with the tag

`publish-to-pypi.yml` runs these jobs, each once the one before has
passed (PyPI's trusted publisher for puddletag names that file, so it
keeps its name):

1. Check the tag: `release.py check 3.0.0b1` makes sure the tag is
   annotated, is `version_string` in its commit, in normal form, and
   that the commit is on `master` (or on the tag's maintenance branch);
   `release.py notes 3.0.0b1` writes the release page's text.
2. The tests, as on every push.
3. The sdist and the wheel, built once, on Python 3.15:
   `puddletag-3.0.0b1.tar.gz` and `puddletag-3.0.0b1-py3-none-any.whl`.
4. PyPI, by trusted publishing, with the attestations the publish
   action adds.
5. The GitHub Release, titled with the version: the version's section
   of `CHANGELOG.md`, then GitHub's generated list of pull requests and
   new contributors, with both files attached. The list starts at the
   tag before a pre-release, and at the last final for a final.

A version with `a`, `b` or `rc` is a pre-release: pip installs it only
when asked (`pip install --pre puddletag`, or `puddletag==3.0.0b1`),
and GitHub marks it Pre-release, so the last final stays "Latest". Its
release page starts with a paragraph saying how to install it, to back
up `~/.config/puddletag` first, and how to report problems.

A job that fails (an outage, a flaky test) is re-run from the Actions
page with "Re-run failed jobs"; nothing has to be undone. A release
found broken is fixed forward with the next number: PyPI never takes a
file name twice.

## What each push publishes

`publish-to-pypi.yml` also runs on every push to `master` or to a
maintenance branch, and publishes nothing unless every test passed.

- A push to `master` appends `.post<run number>` to the version (via
  `_buildid` in `puddlestuff/__init__.py`) and publishes to TestPyPI, so
  it is a public pre-release there. It also deploys the docs site,
  [docs.puddletag.net](https://docs.puddletag.net/), to GitHub Pages; if that deploy fails, "Re-run
  failed jobs" works for a day, while the built site is kept.
- A push to a maintenance branch (`3.0.x`) runs the tests and publishes
  nothing.

Your direct pushes to `master` skip the branch protection's required
check (`git push` reports "Bypassed rule violations"); the tests still
run before anything is published.

## Fix releases from a maintenance branch

To release a fix of 3.0.0 while `master` holds 3.1.0b1, make a
maintenance branch at the last final of that line, once:

    git switch -c 3.0.x 3.0.0
    git push -u origin 3.0.x

Bring each fix over with `git cherry-pick -x`, its `CHANGELOG.md` line
under the branch's `[Unreleased]`, and push: CI runs the tests on every
push to a branch named like `3.0.x`, and publishes nothing. Then run
`venv/bin/python release.py` on the branch. It offers 3.0.1, checks it
against the 3.0 tags only, and, in the same atomic push as the branch
and the tag, pushes a commit to `master` that adds the 3.0.1 section
to `master`'s `CHANGELOG.md`, which the News page is built from (a
push to `master` needs an admin). The fix's line also stays under
`master`'s `[Unreleased]`, for 3.1.0's notes. The 3.0.1 GitHub Release
is "Latest" unless a higher final (3.1.0) is out.

The branch's workflows are its own: a change to `master`'s reaches it
only if you bring it over. If its "Create the GitHub Release" job is
refused (GitHub may not let CI's token make a release whose commit's
workflow files differ from `master`'s), make it from your machine:
`gh run download <run> -n dist -n notes`, then `gh release create` as
the workflow does, with the settings `release.py check 3.0.1` prints.

A branch made at a tag older than 3.0.0 (2.5.0) can't be released this
way: its tree has no release command, and its workflow publishes any
tag.

## The commands CI runs

- `release.py check TAG` exits non-zero unless the tag is annotated, is
  the `version_string` of its commit, in normal form, and the commit is
  on `origin/master` or on the tag's maintenance branch (`origin/3.0.x`
  for 3.0.1). It needs the whole history and every tag
  (`fetch-depth: 0`). It prints the GitHub Release's settings for
  `$GITHUB_OUTPUT`: `latest`, `notes-start-tag` and `prerelease`.
- `release.py notes VERSION` prints the text of VERSION's release page:
  its `CHANGELOG.md` section, after the pre-release paragraph for a
  pre-release.
