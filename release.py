#!/usr/bin/env python3
"""Cuts a puddletag release, and checks its tag in CI.

On master (or a maintenance branch such as 3.0.x), once CI has passed:

    venv/bin/python release.py [VERSION] [--yes] [--dry-run]

asks which version, checks that the release can go out, opens git's
editor on the notes, asks once, then commits version_string and
CHANGELOG.md, tags, pushes, and follows the CI run that publishes. For
CI, on the tag:

    release.py check TAG      the tag is the version in its commit, in
                              normal form, on master or its maintenance
                              branch; prints the GitHub Release's
                              settings, name=value lines for
                              $GITHUB_OUTPUT
    release.py notes VERSION  prints the text of VERSION's GitHub
                              Release

CONTRIBUTING.md ("Releasing") describes the whole process.
"""
import argparse
import datetime
import difflib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from packaging.version import InvalidVersion, Version

MASTER = 'master'
# A maintenance branch is named after its line: 3.0.x releases 3.0.1, 3.0.2...
MAINTENANCE = re.compile(r'(\d+)\.(\d+)\.x')
REPO = 'puddletag/puddletag'
REPO_URL = f'https://github.com/{REPO}'
PYPI_URL = 'https://pypi.org'
PYPI_PAGE = 'https://pypi.org/project/puddletag'
CHANGELOG = 'CHANGELOG.md'
VERSION_FILE = 'puddlestuff/__init__.py'
VERSION_LINE = re.compile(r"^version_string = '([^']*)'$", re.MULTILINE)
WORKFLOW = 'publish-to-pypi.yml'
# tests.yml's "All tests passed" job as publish-to-pypi.yml runs it on a
# push (a pull request's run shows it without "tests / ").
CHECK_NAME = 'tests / All tests passed'
# Keep a Changelog's kinds of change, in its order.
HEADINGS = ('Added', 'Changed', 'Deprecated', 'Removed', 'Fixed', 'Security')
APPEAR_SECONDS = 60  # how long a CI run may take to show up
POLL_SECONDS = 30  # between two looks at CI before releasing
RUN_POLL_SECONDS = 3  # between two looks for the tag's run
PRERELEASE_NOTE = (
    'This is a pre-release, for testing. Install it with '
    '`pip install --pre puddletag=={version}`. Back up '
    '`~/.config/puddletag`, where your settings are, before you start '
    'it. Report problems with Help > Report a problem.')


class Refusal(Exception):
    """Stops the command; the message says why. Nothing has changed, or
    what changed has been put back."""


def run(*args, cwd=None):
    """Runs a program and returns its output, without the last newline.
    A program that fails, or is missing, is a Refusal."""
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    except FileNotFoundError:
        raise Refusal(f'{args[0]} not found: install it') from None
    if result.returncode:
        message = (result.stderr or result.stdout).strip()
        raise Refusal(f"{' '.join(args[:2])} failed: {message}")
    return result.stdout.rstrip('\n')


def git(*args, cwd=None):
    return run('git', *args, cwd=cwd)


def gh(*args):
    return run('gh', *args)


def go_to_top():
    """Works from the top of the repository the command runs in."""
    os.chdir(git('rev-parse', '--show-toplevel'))


def read_version(text):
    """version_string's value in the text of puddlestuff/__init__.py."""
    match = VERSION_LINE.search(text)
    if not match:
        raise Refusal(f'{VERSION_FILE} has no version_string line')
    return match.group(1)


def today():
    """The release date: today, where the command runs."""
    return datetime.date.today().isoformat()


def main(argv=None):
    """The command line; returns the exit status."""
    argv = sys.argv[1:] if argv is None else list(argv)
    try:
        if argv[:1] == ['check']:
            parser = argparse.ArgumentParser(prog='release.py check')
            parser.add_argument('tag')
            print('\n'.join(check_tag(parser.parse_args(argv[1:]).tag)))
            return 0
        if argv[:1] == ['notes']:
            parser = argparse.ArgumentParser(prog='release.py notes')
            parser.add_argument('version')
            print(release_notes(parser.parse_args(argv[1:]).version))
            return 0
        parser = argparse.ArgumentParser(
            prog='release.py',
            description='Cuts a puddletag release; CONTRIBUTING.md has the details.')
        parser.add_argument(
            'version', nargs='?',
            help='such as 3.0.0b1; without it, menus offer the versions that can come next')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='run every check and show what a release would do, changing nothing')
        parser.add_argument('--yes', action='store_true', help="don't ask before releasing")
        args = parser.parse_args(argv)
        return release_command(args.version, args.yes, args.dry_run)
    except Refusal as refusal:
        print(f'release.py: {refusal}', file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print('\nNothing changed.', file=sys.stderr)
        return 1


# Versions -------------------------------------------------------------------

def parse_tag(name):
    """The Version a tag name spells, or None when packaging can't read it."""
    try:
        return Version(name)
    except InvalidVersion:
        return None


def release_version(text):
    """The version the text names, refused unless it is a release in normal
    form."""
    try:
        version = Version(text)
    except InvalidVersion:
        raise Refusal(
            f"{text} isn't a version: write one like 3.0.0, 3.0.0b1 or 3.0.0rc1") from None
    if (version.dev is not None or version.post is not None or version.local
            or version.epoch):
        raise Refusal(
            f"{text} isn't a release: .dev, .post, local (+) and epoch (!) versions "
            "aren't released")
    if len(version.release) != 3:
        raise Refusal(f'{text} needs three numbers, such as 3.0.0')
    if str(version) != text:
        raise Refusal(f"{text} isn't in normal form: write {version}")
    return version


def bumps(current):
    """The releases that can follow a final one: major, minor and patch."""
    major, minor, patch = current.release
    return [('major', f'{major + 1}.0.0'),
            ('minor', f'{major}.{minor + 1}.0'),
            ('patch', f'{major}.{minor}.{patch + 1}')]


def stages(base):
    """The stages a release of base goes through, from the first one."""
    return [('beta', f'{base}b1'), ('release candidate', f'{base}rc1'), ('final', base)]


def next_stages(current):
    """What can follow a pre-release."""
    base = current.base_version
    kind, number = current.pre
    final = ('final', base)
    if kind == 'a':
        return [('next alpha', f'{base}a{number + 1}'), ('beta', f'{base}b1'),
                ('release candidate', f'{base}rc1'), final]
    if kind == 'b':
        return [('next beta', f'{base}b{number + 1}'), ('release candidate', f'{base}rc1'), final]
    return [('next release candidate', f'{base}rc{number + 1}'), final]


def pick(options):
    """Shows the numbered options and asks until one is chosen; returns its
    version. The end of input and Ctrl+C go up."""
    for number, (label, version) in enumerate(options, 1):
        print(f'{number}) {label}: {version}')
    numbers = [str(number) for number in range(1, len(options) + 1)]
    while True:
        answer = input(f'Choose 1-{len(options)}: ').strip()
        if answer in numbers:
            return options[int(answer) - 1][1]
        print(f'Type a number from 1 to {len(options)}.')


def choose_version(current, maintenance=False):
    """Asks which release comes after current."""
    if current.is_prerelease:
        print(f'puddletag is at {current}. Which release comes next?')
        return Version(pick(next_stages(current)))
    if maintenance:
        major, minor, patch = current.release
        patch = f'{major}.{minor}.{patch + 1}'
        print(f'puddletag is at {current}. Which stage of {patch}?')
        return Version(pick(stages(patch)))
    print(f'puddletag is at {current}. Which release comes next?')
    base = pick(bumps(current))
    print(f'Which stage of {base}?')
    return Version(pick(stages(base)))


def check_above(version, tags, line):
    """Refuses a version that isn't above every tag (of its line, on a
    maintenance branch). Tags that aren't versions don't count."""
    parsed = [(parse_tag(tag), tag) for tag in tags]
    parsed = [(found, tag) for found, tag in parsed if found is not None]
    if line is not None:
        if version.release[:2] != line:
            raise Refusal(
                f'The {line[0]}.{line[1]}.x branch releases {line[0]}.{line[1]} '
                f'versions only, not {version}')
        parsed = [(found, tag) for found, tag in parsed if found.release[:2] == line]
    if not parsed:
        return
    newest, name = max(parsed, key=lambda pair: pair[0])
    if version <= newest:
        if line is None:
            raise Refusal(f"{version} isn't above {name}, the newest tag")
        raise Refusal(f"{version} isn't above {name}, the newest {line[0]}.{line[1]} tag")


def previous_tag(version, tags):
    """The tag a release is compared with: the highest below it, of any kind
    for a pre-release, only finals for a final. None when there is none."""
    below = []
    for tag in tags:
        found = parse_tag(tag)
        if found is None or found >= version:
            continue
        if not version.is_prerelease and found.is_prerelease:
            continue
        below.append((found, tag))
    return max(below, key=lambda pair: pair[0])[1] if below else None


def is_latest(version, tags):
    """Whether GitHub's "Latest" belongs to this release: a final that no
    final tag is above."""
    if version.is_prerelease:
        return False
    for tag in tags:
        found = parse_tag(tag)
        if found is not None and not found.is_prerelease and found > version:
            return False
    return True


# Changelog ------------------------------------------------------------------

LINK_LINE = re.compile(r'^\[([^\]]+)\]: (\S+)$')
SECTION_LINE = re.compile(r'^## \[([^\]]+)\](?: - (\d{4}-\d{2}-\d{2}))?$')


@dataclass
class Section:
    name: str  # 'Unreleased', or the version as its heading writes it
    date: str | None  # 'YYYY-MM-DD'; None when the heading has none
    body: str  # the text under the heading, without the blank lines around it


@dataclass
class Changelog:
    header: str  # everything before the first '## [' heading
    sections: list[Section] = field(default_factory=list)
    links: list[tuple[str, str]] = field(default_factory=list)  # (name, url), in file order


def parse_changelog(text):
    """CHANGELOG.md's text as a Changelog."""
    lines = text[:-1].split('\n') if text.endswith('\n') else text.split('\n')
    links = []
    while lines and LINK_LINE.match(lines[-1]):
        links.insert(0, LINK_LINE.match(lines.pop()).groups())
    header_lines = []
    sections = []
    for number, line in enumerate(lines, 1):
        if line.startswith('## '):
            match = SECTION_LINE.match(line)
            if not match:
                raise Refusal(f"{CHANGELOG} line {number} isn't a release heading such as "
                              f"## [3.0.0] - 2026-12-01: {line}")
            sections.append((match.group(1), match.group(2), []))
        elif sections:
            sections[-1][2].append(line)
        else:
            header_lines.append(line)
    if not sections or sections[0][0] != 'Unreleased':
        raise Refusal(f'{CHANGELOG} has no ## [Unreleased] section at the top')
    return Changelog(
        '\n'.join(header_lines) + '\n',
        [Section(name, date, '\n'.join(body).strip('\n')) for name, date, body in sections],
        links)


def format_changelog(changelog):
    """The text of a Changelog; the inverse of parse_changelog."""
    parts = [changelog.header]
    for section in changelog.sections:
        heading = f'## [{section.name}]'
        if section.date:
            heading += f' - {section.date}'
        parts.append(f'{heading}\n\n')
        if section.body:
            parts.append(f'{section.body}\n\n')
    if not changelog.links:
        return ''.join(parts).rstrip('\n') + '\n'
    parts.extend(f'[{name}]: {url}\n' for name, url in changelog.links)
    return ''.join(parts)


def body_is_empty(text):
    """Whether the notes have no line but blank ones and '### ' headings."""
    return all(not line.strip() or line.startswith('### ') for line in text.split('\n'))


def is_pre_release_of(name, version):
    """Whether the section name is a pre-release of the final version."""
    try:
        other = Version(name)
    except InvalidVersion:
        return False
    return other.is_prerelease and other.release == version.release and other != version


def merge(bodies):
    """The notes of several sections under one set of headings."""
    intros = []
    chunks = {}
    for body in bodies:
        name = None
        current = []

        def close():
            text = '\n'.join(current).strip('\n')
            if text:
                if name is None:
                    intros.append(text)
                else:
                    chunks.setdefault(name, []).append(text)

        for line in body.split('\n'):
            if line.startswith('### '):
                close()
                name = line[4:].strip()
                current = []
            else:
                current.append(line)
        close()
    order = [name for name in HEADINGS if name in chunks]
    order += [name for name in chunks if name not in HEADINGS]
    blocks = intros + [f'### {name}\n\n' + '\n'.join(chunks[name]) for name in order]
    return '\n\n'.join(blocks)


def editor_text(changelog, version):
    """The text the editor opens on for this release."""
    unreleased = changelog.sections[0].body
    if version.is_prerelease:
        return unreleased
    earlier = [section.body for section in changelog.sections[1:]
               if is_pre_release_of(section.name, version)]
    return merge([unreleased] + earlier) if earlier else unreleased


def stamp(changelog, version, date, notes, previous, branch):
    """The Changelog once version is released with these notes."""
    final = not Version(version).is_prerelease
    dropped = {section.name for section in changelog.sections[1:]
               if final and is_pre_release_of(section.name, Version(version))}
    sections = [Section('Unreleased', None, ''), Section(version, date, notes)]
    sections += [section for section in changelog.sections[1:] if section.name not in dropped]
    head = 'HEAD' if branch == MASTER else branch
    links = [('Unreleased', f'{REPO_URL}/compare/{version}...{head}'),
             (version, f'{REPO_URL}/compare/{previous}...{version}' if previous
              else f'{REPO_URL}/tree/{version}')]
    gone = dropped | {'Unreleased', version}
    links += [(name, url) for name, url in changelog.links if name not in gone]
    return Changelog(changelog.header, sections, links)


def _below(name, version):
    try:
        return Version(name) < version
    except InvalidVersion:
        return False


def add_section(changelog, version, date, body, previous):
    """Master's Changelog with a maintenance release's section."""
    if any(section.name == version for section in changelog.sections):
        raise Refusal(f"master's {CHANGELOG} already has a {version} section")
    new = Version(version)
    sections = list(changelog.sections)
    index = len(sections)
    for number, section in enumerate(sections[1:], 1):
        if _below(section.name, new):
            index = number
            break
    sections.insert(index, Section(version, date, body))
    links = list(changelog.links)
    index = len(links)
    for number, (name, _) in enumerate(links):
        if name != 'Unreleased' and _below(name, new):
            index = number
            break
    links.insert(index, (version, f'{REPO_URL}/compare/{previous}...{version}'))
    return Changelog(changelog.header, sections, links)


def release_page_text(changelog, version):
    """The text of version's GitHub Release page."""
    for section in changelog.sections:
        if section.name == version:
            break
    else:
        raise Refusal(f'{CHANGELOG} has no section for {version}')
    if body_is_empty(section.body):
        raise Refusal(f'The {version} section of {CHANGELOG} is empty')
    if Version(version).is_prerelease:
        return PRERELEASE_NOTE.format(version=version) + '\n\n' + section.body
    return section.body


# The command ----------------------------------------------------------------

HEADING_IN_NOTES = re.compile(r'^#{1,2}(\s|$)', re.MULTILINE)


def release_command(version_text, yes, dry_run=False):
    """Cuts a release from the branch the command runs on; returns the exit
    status."""
    go_to_top()
    version = release_version(version_text) if version_text else None
    branch = git('branch', '--show-current')
    if not branch:
        raise Refusal("HEAD isn't on a branch: switch to master")
    match = MAINTENANCE.fullmatch(branch)
    if branch != MASTER and not match:
        raise Refusal(f'Releases are made on master or on a maintenance branch such as 3.0.x, '
                      f'not on {branch}')
    line = (int(match.group(1)), int(match.group(2))) if match else None
    git('fetch', '--quiet', 'origin', *([branch, MASTER] if line else [branch]))
    ahead, behind = git('rev-list', '--left-right', '--count',
                        f'HEAD...refs/remotes/origin/{branch}').split()
    if (ahead, behind) != ('0', '0'):
        raise Refusal(f"HEAD isn't origin/{branch} ({ahead} to push, {behind} to pull): "
                      "push or pull first")
    changed = [entry[3:] for entry in git(
        'status', '--porcelain', '--untracked-files=no', '--', VERSION_FILE, CHANGELOG
    ).split('\n') if entry]
    if changed:
        raise Refusal(f"{', '.join(changed)} {'has' if len(changed) == 1 else 'have'} "
                      "local changes: commit or stash them first")
    current = Version(read_version(Path(VERSION_FILE).read_text(encoding='utf-8')))
    changelog = parse_changelog(Path(CHANGELOG).read_text(encoding='utf-8'))
    if version is None:
        version = choose_version(current, maintenance=line is not None)
    local = git('tag', '--list').split()
    remote = []
    for entry in git('ls-remote', '--tags', 'origin').split('\n'):
        if '\t' in entry:
            name = entry.split('\t')[1].removeprefix('refs/tags/').removesuffix('^{}')
            if name not in remote:
                remote.append(name)
    if str(version) in local:
        raise Refusal(f'Tag {version} already exists here')
    if str(version) in remote:
        raise Refusal(f'Tag {version} already exists on GitHub')
    check_above(version, local + remote, line)
    text = editor_text(changelog, version)
    if body_is_empty(text):
        raise Refusal(f"There's nothing to release: {CHANGELOG}'s [Unreleased] is empty")
    if pypi_has(version):
        raise Refusal(f'PyPI already has puddletag {version}')
    head = git('rev-parse', 'HEAD')
    wait_for_tests(head, branch)
    notes = edit(text)
    previous = previous_tag(version, local + remote)
    date = today()
    print(f"Version: {version} ({'a pre-release' if version.is_prerelease else 'final'})")
    print(f'Branch: {branch}')
    if line:
        print(f'Master: gets the {version} section of {CHANGELOG}')
    print(f'Notes:\n\n{notes}\n')
    if dry_run:
        show_release(version, date, notes, previous, branch, changelog, line is not None)
        return 0
    if not yes and input(f'Release {version}? [y/N] ').strip().lower() not in ('y', 'yes'):
        print('Nothing changed.')
        return 1
    pushing = False
    tag_object = None
    try:
        version_text = with_version(Path(VERSION_FILE).read_text(encoding='utf-8'), version)
        Path(VERSION_FILE).write_text(version_text, encoding='utf-8')
        Path(CHANGELOG).write_text(format_changelog(
            stamp(changelog, str(version), date, notes, previous, branch)), encoding='utf-8')
        git('commit', '--quiet', '--only', '-m', f'chore(release): {version}', '--',
            VERSION_FILE, CHANGELOG)
        git('tag', '-a', str(version), '-m', f'puddletag {version}')
        refs = [branch]
        if line:
            refs.append(
                f'{notes_on_master(version, date, notes, previous)}:refs/heads/{MASTER}')
        refs.append(f'refs/tags/{version}')
        tag_object = git('rev-parse', f'refs/tags/{version}')
        pushing = True
        pushed = subprocess.run(['git', 'push', '--atomic', '--no-follow-tags', 'origin', *refs])
        pushing = False
        if pushed.returncode:
            raise Refusal('The push was refused: the release commit and tag are gone, '
                          'and nothing changed')
    except BaseException as error:
        if pushing:
            # The server may have taken the push before git died: ask it.
            try:
                found = git('ls-remote', 'origin', f'refs/tags/{version}')
            except Refusal:
                found = None
            if found and found.split()[0] == tag_object:
                print(f'The push was interrupted, but GitHub has {version}: going on.')
                return follow(version, branch)
            undo(head, version)
            if found is None:
                raise Refusal(
                    "The push was interrupted and GitHub can't be asked whether it has "
                    f'{version}: check {REPO_URL}/tags before running this again. Here, the '
                    'release commit and tag are gone') from None
            raise Refusal('The push was interrupted before GitHub took it: the release '
                          'commit and tag are gone, and nothing changed') from None
        undo(head, version)
        if isinstance(error, KeyboardInterrupt):
            raise Refusal('Interrupted before the push: the release commit and tag are '
                          'gone, and nothing changed') from None
        raise
    return follow(version, branch)


def with_version(text, version):
    """The text of puddlestuff/__init__.py with version_string set."""
    text, count = VERSION_LINE.subn(lambda _: f"version_string = '{version}'", text)
    if count != 1:
        raise Refusal(f'{VERSION_FILE} has no single version_string line')
    return text


def show_diff(old, new):
    """Prints CHANGELOG.md's change as a unified diff."""
    print(''.join(difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True),
        f'a/{CHANGELOG}', f'b/{CHANGELOG}')), end='')


def show_release(version, date, notes, previous, branch, changelog, fix):
    """What a release would do, for --dry-run: nothing is written."""
    print('Dry run: nothing changed. A release would:')
    print(f'\nSet in {VERSION_FILE}:\n  version_string = \'{version}\'')
    print(f'\nChange {CHANGELOG}:')
    show_diff(Path(CHANGELOG).read_text(encoding='utf-8'),
              format_changelog(stamp(changelog, str(version), date, notes, previous, branch)))
    refs = [branch]
    if fix:
        old = git('show', f'refs/remotes/origin/{MASTER}:{CHANGELOG}') + '\n'
        print(f"\nChange {MASTER}'s {CHANGELOG}:")
        show_diff(old, format_changelog(add_section(
            parse_changelog(old), str(version), date, notes, previous)))
        refs.append(f"<a commit adding {version} to {MASTER}'s {CHANGELOG}>:refs/heads/{MASTER}")
    refs.append(f'refs/tags/{version}')
    print('\nThen run:')
    print(f'  git commit --only -m "chore(release): {version}" -- {VERSION_FILE} {CHANGELOG}')
    print(f'  git tag -a {version} -m "puddletag {version}"')
    print(f"  git push --atomic --no-follow-tags origin {' '.join(refs)}")


def undo(head, version):
    """Puts back what the release changed, as far as it can; never raises."""
    steps = [('tag', '-d', str(version)),
             ('reset', '--quiet', '--soft', head),
             ('restore', f'--source={head}', '--staged', '--worktree', '--', VERSION_FILE,
              CHANGELOG)]
    for step in steps:
        try:
            git(*step)
        except Refusal:
            pass


def pypi_has(version):
    """Whether PyPI has this version of puddletag."""
    url = f'{PYPI_URL}/pypi/puddletag/{version}/json'
    try:
        with urllib.request.urlopen(url, timeout=30):
            return True
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False
        raise Refusal(f"Couldn't ask PyPI whether it has {version}: {error}") from None
    except (urllib.error.URLError, OSError) as error:
        raise Refusal(f"Couldn't ask PyPI whether it has {version}: {error}") from None


def wait_for_tests(sha, branch):
    """Returns once "All tests passed" has passed on sha; refuses when it
    didn't, or when no CI run shows up."""
    short = sha[:7]
    start = time.monotonic()
    said = False
    while True:
        found = json.loads(gh('api', '-X', 'GET', f'repos/{REPO}/commits/{sha}/check-runs',
                              '-f', f'check_name={CHECK_NAME}'))['check_runs']
        job = max(found, key=lambda check: check['id']) if found else None
        if job and job['status'] == 'completed':
            if job['conclusion'] == 'success':
                return
            raise Refusal(f"All tests passed ended in {job['conclusion']} on {short}: "
                          f"{job['html_url']}")
        if job:
            state, url = job['status'], job['html_url']
        else:
            runs = json.loads(gh(
                'run', 'list', '--repo', REPO, '--workflow', WORKFLOW, '--branch', branch,
                '--commit', sha, '--event', 'push', '--json', 'databaseId,status,url',
                '--limit', '5'))
            running = [run for run in runs if run['status'] != 'completed']
            if running:
                state, url = running[0]['status'], running[0]['url']
            elif runs:
                raise Refusal(f"CI's run on {short} ended without All tests passed: "
                              f"{runs[0]['url']}")
            elif time.monotonic() - start >= APPEAR_SECONDS:
                raise Refusal(f'No CI run on {short} after a minute: {REPO_URL}/actions')
            else:
                state, url = 'not started', f'{REPO_URL}/actions'
        if not said:
            print(f'Waiting for All tests passed on {short} ({state}): {url}')
            said = True
        time.sleep(POLL_SECONDS)


def edit(text):
    """Opens git's editor on the notes and returns what was saved."""
    editor = git('var', 'GIT_EDITOR')
    path = Path(git('rev-parse', '--absolute-git-dir')) / 'RELEASE_NOTES.md'
    path.write_text(text + '\n', encoding='utf-8')
    try:
        print(f'Opening {editor} on the notes: save and close it to go on.')
        status = subprocess.run(['sh', '-c', f'{editor} "$@"', editor, str(path)]).returncode
        if status:
            raise Refusal(f'The editor ended with status {status}: nothing changed')
        saved = path.read_text(encoding='utf-8')
    finally:
        path.unlink(missing_ok=True)
    notes = '\n'.join(line.rstrip() for line in saved.split('\n')).strip('\n')
    if not notes:
        raise Refusal('The notes are empty: nothing changed')
    if HEADING_IN_NOTES.search(notes):
        raise Refusal(f"The notes can't hold a # or ## heading: {CHANGELOG}'s sections "
                      "are ## headings")
    return notes


def notes_on_master(version, date, notes, previous):
    """The commit to push to master: its CHANGELOG.md with this maintenance
    release's section."""
    with tempfile.TemporaryDirectory() as folder:
        tree = str(Path(folder) / 'master')
        git('worktree', 'add', '--quiet', '--detach', tree, f'refs/remotes/origin/{MASTER}')
        try:
            path = Path(tree) / CHANGELOG
            changelog = add_section(parse_changelog(path.read_text(encoding='utf-8')),
                                    str(version), date, notes, previous)
            path.write_text(format_changelog(changelog), encoding='utf-8')
            git('commit', '--quiet', '--only', '-m', f'chore(release): add {version} to {CHANGELOG}',
                '--', CHANGELOG, cwd=tree)
            return git('rev-parse', 'HEAD', cwd=tree)
        finally:
            git('worktree', 'remove', '--force', tree)


def links(version):
    print(f'  PyPI:   {PYPI_PAGE}/{version}/')
    print(f'  GitHub: {REPO_URL}/releases/tag/{version}')


def follow(version, branch):
    """Follows CI's run on the tag; returns the exit status."""
    print(f'Pushed {branch} and {version}.')
    try:
        start = time.monotonic()
        while True:
            runs = json.loads(gh(
                'run', 'list', '--repo', REPO, '--workflow', WORKFLOW, '--branch', str(version),
                '--event', 'push', '--json', 'databaseId,url', '--limit', '1'))
            if runs:
                break
            if time.monotonic() - start >= APPEAR_SECONDS:
                print(f"CI's run on {version} hasn't shown up after a minute: "
                      f"follow it on {REPO_URL}/actions")
                print('Once CI has published it:')
                links(version)
                return 0
            time.sleep(RUN_POLL_SECONDS)
        url = runs[0]['url']
        print(f"Following CI's run on {version}: {url}")
        watched = subprocess.run(['gh', 'run', 'watch', str(runs[0]['databaseId']),
                                  '--repo', REPO, '--exit-status'])
        if watched.returncode:
            print(f"CI's run on {version} failed: re-run its failed jobs from {url}. "
                  "Nothing has to be undone.")
            return 1
        print(f'Published {version}:')
        links(version)
        return 0
    except Refusal as refusal:
        print(f'release.py: {refusal}')
        print(f'Follow the run on {REPO_URL}/actions. Once CI has published it:')
        links(version)
        return 1
    except KeyboardInterrupt:
        print('\nOnce CI has published it:')
        links(version)
        return 0


# The commands CI runs -------------------------------------------------------

def check_tag(tag):
    """Refuses a tag that release.py didn't make, or that isn't on master or
    its maintenance branch; returns the GitHub Release's settings as
    name=value lines."""
    go_to_top()
    version = release_version(tag)
    try:
        commit = git('rev-parse', '--verify', '--quiet', f'refs/tags/{tag}^{{commit}}')
    except Refusal:
        raise Refusal(f"There's no tag {tag} here") from None
    if git('cat-file', '-t', f'refs/tags/{tag}') != 'tag':
        raise Refusal(f'{tag} is a lightweight tag: release.py makes annotated ones')
    found = read_version(git('show', f'{commit}:{VERSION_FILE}'))
    if found != tag:
        raise Refusal(f"{tag}'s commit has version_string {found}")
    line = f'{version.major}.{version.minor}.x'
    for branch in (MASTER, line):
        ref = f'refs/remotes/origin/{branch}'
        if subprocess.run(['git', 'merge-base', '--is-ancestor', commit, ref],
                          capture_output=True).returncode == 0:
            break
    else:
        raise Refusal(f"{tag}'s commit is on neither origin/{MASTER} nor origin/{line}")
    tags = git('tag', '--list').split()
    return [f'latest={"true" if is_latest(version, tags) else "false"}',
            f'notes-start-tag={previous_tag(version, tags) or ""}',
            f'prerelease={"true" if version.is_prerelease else "false"}']


def release_notes(version):
    """The text of the version's GitHub Release."""
    go_to_top()
    release_version(version)
    return release_page_text(parse_changelog(Path(CHANGELOG).read_text(encoding='utf-8')), version)


if __name__ == '__main__':
    sys.exit(main())
