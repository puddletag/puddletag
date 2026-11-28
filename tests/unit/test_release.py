"""release.py: the command that cuts a release, and the checks CI makes
on its tag.

Expected values come from CONTRIBUTING.md's "Releasing" section, PEP 440,
Keep a Changelog 1.1.0, and GitHub's and gh's documentation. Every
repository, changelog, tag, gh answer and PyPI answer here is synthetic,
except TAGS (puddletag's own tags) and the real CHANGELOG.md read by
test_changelog_round_trips.
"""
import builtins
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from packaging.version import Version

import release

ROOT = Path(release.__file__).resolve().parent
REPO_URL = 'https://github.com/puddletag/puddletag'

TOP = '''<!--
Synthetic, in the layout of puddletag's CHANGELOG.md.
-->
# Changelog

'''

CHANGELOG = TOP + '''## [Unreleased]

### Fixed

- A synthetic fix.

## [2.5.0] - 2025-07-27

### Fixed

- A synthetic 2.5.0 fix.

## [2.4.0] - 2024-06-23

### Added

- A synthetic 2.4.0 feature.

[Unreleased]: https://github.com/puddletag/puddletag/compare/2.5.0...HEAD
[2.5.0]: https://github.com/puddletag/puddletag/compare/2.4.0...2.5.0
[2.4.0]: https://github.com/puddletag/puddletag/compare/2.3.0...2.4.0
'''

# CHANGELOG once 3.0.0b1 is released on 2026-12-01, its notes unchanged.
CHANGELOG_AT_3_0_0B1 = TOP + '''## [Unreleased]

## [3.0.0b1] - 2026-12-01

### Fixed

- A synthetic fix.

## [2.5.0] - 2025-07-27

### Fixed

- A synthetic 2.5.0 fix.

## [2.4.0] - 2024-06-23

### Added

- A synthetic 2.4.0 feature.

[Unreleased]: https://github.com/puddletag/puddletag/compare/3.0.0b1...HEAD
[3.0.0b1]: https://github.com/puddletag/puddletag/compare/2.5.0...3.0.0b1
[2.5.0]: https://github.com/puddletag/puddletag/compare/2.4.0...2.5.0
[2.4.0]: https://github.com/puddletag/puddletag/compare/2.3.0...2.4.0
'''

# Three pre-releases of 3.0.0, and lines under [Unreleased] since.
PRE_RELEASES = TOP + '''## [Unreleased]

### Fixed

- Fixed since the release candidate.

### Added

- Added since the release candidate.

## [3.0.0rc1] - 2026-12-20

### Fixed

- Fixed in the release candidate.

## [3.0.0b2] - 2026-12-10

### Changed

- Changed in the second beta.

### Fixed

- Fixed in the second beta.

## [3.0.0b1] - 2026-12-01

The first beta.

### Added

- Added in the first beta.

### Security

- Secured in the first beta.

## [2.5.0] - 2025-07-27

### Fixed

- A synthetic 2.5.0 fix.

[Unreleased]: https://github.com/puddletag/puddletag/compare/3.0.0rc1...HEAD
[3.0.0rc1]: https://github.com/puddletag/puddletag/compare/3.0.0b2...3.0.0rc1
[3.0.0b2]: https://github.com/puddletag/puddletag/compare/3.0.0b1...3.0.0b2
[3.0.0b1]: https://github.com/puddletag/puddletag/compare/2.5.0...3.0.0b1
[2.5.0]: https://github.com/puddletag/puddletag/compare/2.4.0...2.5.0
'''

# The editor's text for 3.0.0 after PRE_RELEASES.
MERGED = '''The first beta.

### Added

- Added since the release candidate.
- Added in the first beta.

### Changed

- Changed in the second beta.

### Fixed

- Fixed since the release candidate.
- Fixed in the release candidate.
- Fixed in the second beta.

### Security

- Secured in the first beta.'''

# PRE_RELEASES once 3.0.0 is released on 2027-01-15, MERGED its notes.
PRE_RELEASES_AT_3_0_0 = TOP + '''## [Unreleased]

## [3.0.0] - 2027-01-15

''' + MERGED + '''

## [2.5.0] - 2025-07-27

### Fixed

- A synthetic 2.5.0 fix.

[Unreleased]: https://github.com/puddletag/puddletag/compare/3.0.0...HEAD
[3.0.0]: https://github.com/puddletag/puddletag/compare/2.5.0...3.0.0
[2.5.0]: https://github.com/puddletag/puddletag/compare/2.4.0...2.5.0
'''

# 3.0.0, released on 2027-01-15, where the maintenance branch 3.0.x starts.
AT_3_0_0 = TOP + '''## [Unreleased]

## [3.0.0] - 2027-01-15

### Fixed

- A synthetic 3.0.0 fix.

## [2.5.0] - 2025-07-27

### Fixed

- A synthetic 2.5.0 fix.

[Unreleased]: https://github.com/puddletag/puddletag/compare/3.0.0...HEAD
[3.0.0]: https://github.com/puddletag/puddletag/compare/2.5.0...3.0.0
[2.5.0]: https://github.com/puddletag/puddletag/compare/2.4.0...2.5.0
'''

# master at 3.1.0b1 (2027-02-01), with a fix under [Unreleased].
MASTER_AT_3_1_0B1 = TOP + '''## [Unreleased]

### Fixed

- A synthetic maintenance fix.

## [3.1.0b1] - 2027-02-01

### Added

- A synthetic 3.1.0b1 feature.

## [3.0.0] - 2027-01-15

### Fixed

- A synthetic 3.0.0 fix.

## [2.5.0] - 2025-07-27

### Fixed

- A synthetic 2.5.0 fix.

[Unreleased]: https://github.com/puddletag/puddletag/compare/3.1.0b1...HEAD
[3.1.0b1]: https://github.com/puddletag/puddletag/compare/3.0.0...3.1.0b1
[3.0.0]: https://github.com/puddletag/puddletag/compare/2.5.0...3.0.0
[2.5.0]: https://github.com/puddletag/puddletag/compare/2.4.0...2.5.0
'''

# MASTER_AT_3_1_0B1 once 3.0.1 is released from 3.0.x on 2027-03-01.
MASTER_AT_3_0_1 = TOP + '''## [Unreleased]

### Fixed

- A synthetic maintenance fix.

## [3.1.0b1] - 2027-02-01

### Added

- A synthetic 3.1.0b1 feature.

## [3.0.1] - 2027-03-01

### Fixed

- A synthetic maintenance fix.

## [3.0.0] - 2027-01-15

### Fixed

- A synthetic 3.0.0 fix.

## [2.5.0] - 2025-07-27

### Fixed

- A synthetic 2.5.0 fix.

[Unreleased]: https://github.com/puddletag/puddletag/compare/3.1.0b1...HEAD
[3.1.0b1]: https://github.com/puddletag/puddletag/compare/3.0.0...3.1.0b1
[3.0.1]: https://github.com/puddletag/puddletag/compare/3.0.0...3.0.1
[3.0.0]: https://github.com/puddletag/puddletag/compare/2.5.0...3.0.0
[2.5.0]: https://github.com/puddletag/puddletag/compare/2.4.0...2.5.0
'''

# 3.0.x with the fix brought over under [Unreleased].
BRANCH_WITH_FIX = TOP + '''## [Unreleased]

### Fixed

- A synthetic maintenance fix.

## [3.0.0] - 2027-01-15

### Fixed

- A synthetic 3.0.0 fix.

## [2.5.0] - 2025-07-27

### Fixed

- A synthetic 2.5.0 fix.

[Unreleased]: https://github.com/puddletag/puddletag/compare/3.0.0...HEAD
[3.0.0]: https://github.com/puddletag/puddletag/compare/2.5.0...3.0.0
[2.5.0]: https://github.com/puddletag/puddletag/compare/2.4.0...2.5.0
'''

# BRANCH_WITH_FIX once 3.0.1 is released on 2027-03-01.
BRANCH_AT_3_0_1 = TOP + '''## [Unreleased]

## [3.0.1] - 2027-03-01

### Fixed

- A synthetic maintenance fix.

## [3.0.0] - 2027-01-15

### Fixed

- A synthetic 3.0.0 fix.

## [2.5.0] - 2025-07-27

### Fixed

- A synthetic 2.5.0 fix.

[Unreleased]: https://github.com/puddletag/puddletag/compare/3.0.1...3.0.x
[3.0.1]: https://github.com/puddletag/puddletag/compare/3.0.0...3.0.1
[3.0.0]: https://github.com/puddletag/puddletag/compare/2.5.0...3.0.0
[2.5.0]: https://github.com/puddletag/puddletag/compare/2.4.0...2.5.0
'''


class Clock:
    """Stands in for release.time: sleep() moves monotonic() on at once
    and keeps each wait."""

    def __init__(self):
        self.now = 0.0
        self.waits = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(release, 'time', clock)
    return clock


@pytest.fixture
def answers(monkeypatch):
    """Types the queued answers at input()'s prompts, in turn, echoing
    each prompt and answer as a terminal shows them; ``answers.prompts``
    keeps the prompts. A prompt with no answer left gets the end of input
    (Ctrl+D)."""

    class Answers:
        def __init__(self):
            self.prompts = []
            self.queue = []

        def __call__(self, *typed):
            self.queue.extend(typed)

    typed = Answers()

    def fake_input(prompt=''):
        print(prompt, end='')
        typed.prompts.append(prompt)
        if not typed.queue:
            raise EOFError
        answer = typed.queue.pop(0)
        print(answer)
        return answer

    monkeypatch.setattr(builtins, 'input', fake_input)
    yield typed
    assert typed.queue == [], 'answers nothing asked for'


@pytest.fixture(autouse=True)
def outside_any_repository(tmp_path, monkeypatch):
    """Tests start in an empty folder, so a test that forgot its
    repository can't reach puddletag's own, whose origin is GitHub."""
    monkeypatch.chdir(tmp_path)


FAKE_GH = '''\
import json
import os
import sys

state_path = os.environ['FAKE_GH_STATE']
with open(state_path) as file:
    state = json.load(file)
args = sys.argv[1:]
state['calls'].append(args)
for answer in state['answers']:
    if args[:len(answer['args'])] == answer['args']:
        output = answer['outputs'][0]
        if len(answer['outputs']) > 1:
            answer['outputs'].pop(0)
        break
else:
    state['unmatched'].append(args)
    output = {'returncode': 1, 'stderr': 'fake gh: no answer for this call\\n', 'stdout': ''}
with open(state_path, 'w') as file:
    json.dump(state, file)
sys.stdout.write(output['stdout'])
sys.stderr.write(output['stderr'])
sys.exit(output['returncode'])
'''


class FakeGh:
    """A gh on PATH that answers what the test told it to. ``answer``
    sets the outputs for calls whose arguments begin with ``args``: one
    per call, in turn, and the last one again for every call after. A
    later ``answer`` with the same args replaces it. ``calls`` keeps every
    call; a call with no answer fails the test."""

    def __init__(self, folder):
        folder.mkdir()
        self.folder = folder
        self.state = folder / 'state.json'
        self.state.write_text(json.dumps({'answers': [], 'calls': [], 'unmatched': []}))
        script = folder / 'gh'
        script.write_text(f'#!{sys.executable}\n{FAKE_GH}')
        script.chmod(0o755)

    def _read(self):
        return json.loads(self.state.read_text())

    def answer(self, *args, outputs):
        """outputs: (stdout, exit status) pairs."""
        state = self._read()
        state['answers'] = [answer for answer in state['answers'] if answer['args'] != list(args)]
        state['answers'].append({'args': list(args), 'outputs': [
            {'returncode': status, 'stderr': '', 'stdout': stdout} for stdout, status in outputs]})
        self.state.write_text(json.dumps(state))

    @property
    def calls(self):
        return self._read()['calls']

    @property
    def unmatched(self):
        return self._read()['unmatched']

    def check_run(self, sha, *results):
        """GitHub's answers, in turn, for "All tests passed" on sha: a
        conclusion ('success', 'failure'), the status of a job still
        going ('in_progress', 'queued'), or None for no such job yet."""
        outputs = []
        for result in results or ('success',):
            job = {'html_url': f'{REPO_URL}/actions/runs/101/job/202', 'id': 202,
                   'name': 'tests / All tests passed'}
            if result is None:
                runs = []
            elif result in ('in_progress', 'queued'):
                runs = [dict(job, conclusion=None, status=result)]
            else:
                runs = [dict(job, conclusion=result, status='completed')]
            outputs.append((json.dumps({'check_runs': runs, 'total_count': len(runs)}), 0))
        self.answer('api', '-X', 'GET', f'repos/puddletag/puddletag/commits/{sha}/check-runs',
                    '-f', 'check_name=tests / All tests passed', outputs=outputs)

    def push_runs(self, branch, sha, *statuses):
        """publish-to-pypi.yml's run for the push of sha to branch, in
        turn: its status, or None for no run yet."""
        outputs = [(json.dumps([] if status is None else [
            {'databaseId': 101, 'status': status, 'url': f'{REPO_URL}/actions/runs/101'}]), 0)
            for status in statuses]
        self.answer('run', 'list', '--repo', 'puddletag/puddletag', '--workflow',
                    'publish-to-pypi.yml', '--branch', branch, '--commit', sha, '--event', 'push',
                    '--json', 'databaseId,status,url', '--limit', '5', outputs=outputs)

    def tag_run(self, tag, *shown):
        """Whether the tag's run has shown up, in turn (at once by default)."""
        outputs = [(json.dumps([{'databaseId': 303, 'url': f'{REPO_URL}/actions/runs/303'}]
                               if run else []), 0) for run in shown or (True,)]
        self.answer('run', 'list', '--repo', 'puddletag/puddletag', '--workflow',
                    'publish-to-pypi.yml', '--branch', tag, '--event', 'push',
                    '--json', 'databaseId,url', '--limit', '1', outputs=outputs)

    def watch(self, status=0):
        """How the tag's run ends: 0 passed, 1 failed."""
        self.answer('run', 'watch', '303', '--repo', 'puddletag/puddletag', '--exit-status',
                    outputs=[('Synthetic run log.\n', status)])


@pytest.fixture(autouse=True)
def gh(tmp_path, monkeypatch):
    """Every test has the fake gh first on PATH, so none reaches GitHub
    through a real one."""
    fake = FakeGh(tmp_path / 'fake-gh')
    monkeypatch.setenv('FAKE_GH_STATE', str(fake.state))
    monkeypatch.setenv('PATH', f'{fake.folder}{os.pathsep}{os.environ["PATH"]}')
    yield fake
    assert fake.unmatched == [], 'gh calls the test gave no answer for'


def run_git(cwd, *args):
    return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout.strip()


class Repo:
    """A clone ("work") of a local bare repository standing in for GitHub
    ("origin"). Synthetic."""

    def __init__(self, path, origin):
        self.origin_path = origin
        self.path = path

    def git(self, *args):
        return run_git(self.path, *args)

    def origin(self, *args):
        return run_git(self.origin_path, *args)

    def head(self):
        return self.git('rev-parse', 'HEAD')

    def write(self, files):
        for name, text in files.items():
            path = self.path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def commit(self, files, message='A synthetic change'):
        """Commits exactly these files; other staged changes stay staged."""
        self.write(files)
        self.git('add', '--', *files)
        self.git('commit', '-q', '-m', message, '--', *files)
        return self.head()

    def tag(self, name, annotated=True):
        if annotated:
            self.git('tag', '-a', name, '-m', f'puddletag {name}')
        else:
            self.git('tag', name)

    def push(self, *refs):
        """Pushes exactly refs: push.followTags would add never-pushed."""
        self.git('push', '-q', '--no-follow-tags', 'origin', *refs)

    def state(self):
        """What a command that changes nothing leaves as it was."""
        return {
            'branch': self.git('branch', '--show-current'),
            'changelog': (self.path / 'CHANGELOG.md').read_text(),
            'head': self.head(),
            'origin': self.origin('for-each-ref', '--format=%(refname) %(objectname)'),
            'status': self.git('status', '--porcelain'),
            'tags': self.git('for-each-ref', '--format=%(refname) %(objectname)', 'refs/tags'),
            'version': (self.path / 'puddlestuff' / '__init__.py').read_text(),
            'worktrees': self.git('worktree', 'list', '--porcelain'),
        }


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """puddletag's tree as far as release.py reads it, at 2.5.0, pushed to
    origin with the tags 2.4.0 and 2.5.0, on master, with push.followTags
    on as the maintainer has it. Beside the release's two files: a staged
    new file, an unstaged change and an untracked file, which a release
    leaves as they are, and a local annotated tag never pushed."""
    if not shutil.which('git'):
        if os.environ.get('CI'):  # CI must not skip these
            pytest.fail('git is missing')
        pytest.skip('git is missing')
    for name, value in (('GIT_AUTHOR_EMAIL', 'author@example.invalid'),
                        ('GIT_AUTHOR_NAME', 'Synthetic Author'),
                        ('GIT_COMMITTER_EMAIL', 'author@example.invalid'),
                        ('GIT_COMMITTER_NAME', 'Synthetic Author'),
                        ('GIT_CONFIG_GLOBAL', os.devnull),
                        ('GIT_CONFIG_NOSYSTEM', '1')):
        monkeypatch.setenv(name, value)
    for name in ('EDITOR', 'GIT_EDITOR', 'VISUAL'):
        monkeypatch.delenv(name, raising=False)
    origin = tmp_path / 'origin.git'
    path = tmp_path / 'work'
    run_git(tmp_path, 'init', '-q', '--bare', '-b', 'master', str(origin))
    run_git(tmp_path, 'init', '-q', '-b', 'master', str(path))
    work = Repo(path, origin)
    work.git('remote', 'add', 'origin', str(origin))
    work.git('config', 'push.followTags', 'true')
    work.commit({'CHANGELOG.md': CHANGELOG, 'README.md': 'Synthetic.\n',
                 'puddlestuff/__init__.py': "version_string = '2.5.0'\n"}, 'Synthetic 2.5.0')
    work.tag('2.4.0', annotated=False)
    work.tag('2.5.0', annotated=False)
    work.push('master', '2.4.0', '2.5.0')
    work.git('branch', '-q', '--set-upstream-to', 'origin/master')
    work.git('tag', '-a', 'never-pushed', '-m', 'A synthetic local tag')
    work.write({'draft.md': 'A synthetic staged file.\n',
                'scratch.txt': 'A synthetic untracked file.\n'})
    work.git('add', 'draft.md')
    (path / 'README.md').write_text('Synthetic, changed.\n')
    monkeypatch.chdir(path)
    return work


# Versions -------------------------------------------------------------------

# puddletag's own tags (git tag -l, 2026-11-27).
TAGS = ['1.0.0', '1.0.0beta1', '1.0.0beta2', '1.0.0beta3', '1.0.0beta4', '1.0.0beta6',
        '1.0.1', '1.0.2', '1.0.4', '1.1.0', '1.1.1', '2.0.1', '2.1.0', '2.1.1', '2.2.0',
        '2.3.0', '2.4.0', '2.5.0', 'RC1', 'rm', 'v1.0.5', 'v1.2.0', 'v1.20', 'v2.0.0']


@pytest.mark.parametrize('typed, expected', [
    (('1', '1'), '3.0.0b1'),
    (('1', '3'), '3.0.0'),
    (('2', '2'), '2.6.0rc1'),
    (('3', '3'), '2.5.1'),
])
def test_menus_after_a_final_release(answers, capsys, typed, expected):
    # CONTRIBUTING.md: "after a final release (2.5.0): `1) major: 3.0.0`,
    # `2) minor: 2.6.0`, `3) patch: 2.5.1`; then, for the one chosen,
    # `1) beta: 3.0.0b1`, `2) release candidate: 3.0.0rc1`, `3) final: 3.0.0`"
    answers(*typed)
    assert str(release.choose_version(Version('2.5.0'))) == expected
    if typed == ('1', '1'):
        assert capsys.readouterr().out == (
            'puddletag is at 2.5.0. Which release comes next?\n'
            '1) major: 3.0.0\n'
            '2) minor: 2.6.0\n'
            '3) patch: 2.5.1\n'
            'Choose 1-3: 1\n'
            'Which stage of 3.0.0?\n'
            '1) beta: 3.0.0b1\n'
            '2) release candidate: 3.0.0rc1\n'
            '3) final: 3.0.0\n'
            'Choose 1-3: 1\n')


def test_menu_after_a_beta(answers, capsys):
    # CONTRIBUTING.md, after a beta (3.0.0b1): `1) next beta: 3.0.0b2`,
    # `2) release candidate: 3.0.0rc1`, `3) final: 3.0.0` (synthetic version)
    answers('1')
    assert str(release.choose_version(Version('3.0.0b1'))) == '3.0.0b2'
    lines = capsys.readouterr().out.splitlines()
    assert lines[1:4] == ['1) next beta: 3.0.0b2', '2) release candidate: 3.0.0rc1',
                          '3) final: 3.0.0']
    assert lines[4] == 'Choose 1-3: 1'
    assert not any(word in line for line in lines for word in ('major', 'minor', 'patch'))


def test_menu_after_a_release_candidate(answers, capsys):
    # CONTRIBUTING.md, after a release candidate (3.0.0rc1): `1) next release
    # candidate: 3.0.0rc2`, `2) final: 3.0.0` (synthetic version)
    answers('2')
    assert str(release.choose_version(Version('3.0.0rc1'))) == '3.0.0'
    lines = capsys.readouterr().out.splitlines()
    assert lines[1:3] == ['1) next release candidate: 3.0.0rc2', '2) final: 3.0.0']
    assert lines[3] == 'Choose 1-2: 2'


def test_menu_after_an_alpha(answers, capsys):
    # CONTRIBUTING.md, after an alpha (3.0.0a1): `1) next alpha: 3.0.0a2`,
    # `2) beta: 3.0.0b1`, `3) release candidate: 3.0.0rc1`, `4) final: 3.0.0`
    # (synthetic version)
    answers('2')
    assert str(release.choose_version(Version('3.0.0a1'))) == '3.0.0b1'
    lines = capsys.readouterr().out.splitlines()
    assert lines[1:5] == ['1) next alpha: 3.0.0a2', '2) beta: 3.0.0b1',
                          '3) release candidate: 3.0.0rc1', '4) final: 3.0.0']
    assert lines[5] == 'Choose 1-4: 2'


def test_menu_on_a_maintenance_branch(answers, capsys):
    # CONTRIBUTING.md, on a maintenance branch (3.0.x, at 3.0.0): the menu
    # offers the stages of 3.0.1: `1) beta: 3.0.1b1`, `2) release candidate:
    # 3.0.1rc1`, `3) final: 3.0.1` (synthetic version)
    answers('3')
    assert str(release.choose_version(Version('3.0.0'), maintenance=True)) == '3.0.1'
    lines = capsys.readouterr().out.splitlines()
    assert lines[:4] == ['puddletag is at 3.0.0. Which stage of 3.0.1?',
                         '1) beta: 3.0.1b1', '2) release candidate: 3.0.1rc1',
                         '3) final: 3.0.1']


def test_menu_asks_again_until_a_number_it_offers(answers, capsys):
    # CONTRIBUTING.md: "An answer that isn't one of the numbers asks again."
    answers('4', 'x', '', '1', '3')
    assert str(release.choose_version(Version('2.5.0'))) == '3.0.0'
    assert capsys.readouterr().out.count('Type a number from 1 to 3.\n') == 3


def test_menu_stops_at_the_end_of_input(answers):
    # CONTRIBUTING.md: the command ends with "Nothing changed." at the end
    # of input; the menu lets it go up.
    with pytest.raises(EOFError):
        release.choose_version(Version('2.5.0'))


@pytest.mark.parametrize('text', ['3.0.0', '3.0.0a1', '3.0.0b0', '3.0.0b1', '3.0.0rc1',
                                  '3.0.1', '10.20.30rc12'])
def test_release_versions(text):
    # PEP 440: "X.YaN # Alpha release", "X.YbN # Beta release",
    # "X.YrcN # Release Candidate", "X.Y # Final release" (synthetic versions)
    assert str(release.release_version(text)) == text


@pytest.mark.parametrize('text, message', [
    ('three', "three isn't a version: write one like 3.0.0, 3.0.0b1 or 3.0.0rc1"),
    ('3.0.0.dev1', "3.0.0.dev1 isn't a release: .dev, .post, local (+) and epoch (!) "
                   "versions aren't released"),
    ('3.0.0.post1', "3.0.0.post1 isn't a release: .dev, .post, local (+) and epoch (!) "
                    "versions aren't released"),
    ('3.0.0-1', "3.0.0-1 isn't a release: .dev, .post, local (+) and epoch (!) "
                "versions aren't released"),
    ('3.0.0+local', "3.0.0+local isn't a release: .dev, .post, local (+) and epoch (!) "
                    "versions aren't released"),
    ('1!3.0.0', "1!3.0.0 isn't a release: .dev, .post, local (+) and epoch (!) "
                "versions aren't released"),
    ('3.0.0b1.dev2', "3.0.0b1.dev2 isn't a release: .dev, .post, local (+) and epoch (!) "
                     "versions aren't released"),
    ('3.0', '3.0 needs three numbers, such as 3.0.0'),
    ('3.0.0.0', '3.0.0.0 needs three numbers, such as 3.0.0'),
    ('v3.0.0', "v3.0.0 isn't in normal form: write 3.0.0"),
    ('3.0.0-beta1', "3.0.0-beta1 isn't in normal form: write 3.0.0b1"),
    ('3.0.0c1', "3.0.0c1 isn't in normal form: write 3.0.0rc1"),
    ('3.0.0b', "3.0.0b isn't in normal form: write 3.0.0b0"),
    ('03.0.0', "03.0.0 isn't in normal form: write 3.0.0"),
])
def test_versions_refused(text, message):
    # CONTRIBUTING.md: "The command refuses any other spelling (`v3.0.0`,
    # `3.0.0-beta1`, `3.0`) and `.dev` and `.post` versions". PEP 440
    # normalization: "Pre-release separators", "Pre-release spelling",
    # "Preceding v character", "Implicit pre-release number" (synthetic
    # versions)
    with pytest.raises(release.Refusal) as error:
        release.release_version(text)
    assert str(error.value) == message


@pytest.mark.parametrize('version', ['3.0.0b1', '2.5.1'])
def test_a_release_is_above_every_tag(version):
    # CONTRIBUTING.md, check 1: "Tags that aren't versions (`RC1`, `rm`)
    # don't count; older spellings (`v2.0.0`, `1.0.0beta6`) count by their
    # value"
    release.check_above(Version(version), TAGS, None)


@pytest.mark.parametrize('version', ['2.4.1', '2.0.0'])
def test_a_release_below_a_tag_is_refused(version):
    # CONTRIBUTING.md, check 1: "Tags that aren't versions (`RC1`, `rm`)
    # don't count; older spellings (`v2.0.0`, `1.0.0beta6`) count by their
    # value"
    with pytest.raises(release.Refusal) as error:
        release.check_above(Version(version), TAGS, None)
    assert str(error.value) == f"{version} isn't above 2.5.0, the newest tag"


def test_a_maintenance_release_is_above_its_lines_tags():
    # CONTRIBUTING.md: a maintenance branch (3.0.x) is checked against the
    # 3.0 tags only, and releases 3.0 versions only.
    tags = TAGS + ['3.0.0', '3.1.0b1']
    release.check_above(Version('3.0.1'), tags, (3, 0))
    release.check_above(Version('3.0.1b1'), tags, (3, 0))
    with pytest.raises(release.Refusal) as error:
        release.check_above(Version('3.0.0'), tags, (3, 0))
    assert str(error.value) == "3.0.0 isn't above 3.0.0, the newest 3.0 tag"
    with pytest.raises(release.Refusal) as error:
        release.check_above(Version('3.1.0'), tags, (3, 0))
    assert str(error.value) == 'The 3.0.x branch releases 3.0 versions only, not 3.1.0'


@pytest.mark.parametrize('version, extra, expected', [
    ('3.0.0b1', [], '2.5.0'),
    ('3.0.0b1', ['3.0.0b1'], '2.5.0'),
    ('3.0.0b2', ['3.0.0b1'], '3.0.0b1'),
    ('3.0.0', ['3.0.0b1', '3.0.0b2', '3.0.0rc1'], '2.5.0'),
    ('3.0.1', ['3.0.0', '3.1.0b1'], '3.0.0'),
    ('3.1.0', ['3.0.0', '3.0.1', '3.1.0b1'], '3.0.1'),
    ('2.1.0', [], '2.0.1'),
])
def test_previous_tag(version, extra, expected):
    # CONTRIBUTING.md: "The list starts at the tag before a pre-release, and
    # at the last final for a final."
    assert release.previous_tag(Version(version), TAGS + extra) == expected


@pytest.mark.parametrize('version, extra, expected', [
    ('3.0.0', ['3.0.0'], True),
    ('3.0.0b1', ['3.0.0b1'], False),
    ('3.0.1', ['3.0.0', '3.1.0b1', '3.0.1'], True),
    ('3.0.2', ['3.0.0', '3.0.1', '3.1.0', '3.0.2'], False),
])
def test_latest(version, extra, expected):
    # GitHub, "Create a release": "Drafts and prereleases cannot be set as
    # latest". CONTRIBUTING.md: "The 3.0.1 GitHub Release is "Latest" unless
    # a higher final (3.1.0) is out."
    assert release.is_latest(Version(version), TAGS + extra) is expected


# Changelog ------------------------------------------------------------------

def test_changelog_round_trips():
    # puddletag's own CHANGELOG.md, not synthetic: the News page includes the
    # whole file, so formatting what was parsed must give it back byte for byte.
    text = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    assert release.format_changelog(release.parse_changelog(text)) == text


def test_unreleased_text():
    # Keep a Changelog 1.1.0: "Keep an Unreleased section at the top to
    # track upcoming changes."
    changelog = release.parse_changelog(CHANGELOG)
    assert changelog.sections[0].body == '### Fixed\n\n- A synthetic fix.'
    assert [section.name for section in changelog.sections] == ['Unreleased', '2.5.0', '2.4.0']
    assert [section.date for section in changelog.sections] == [None, '2025-07-27', '2024-06-23']


@pytest.mark.parametrize('notes, empty', [
    ('', True),
    ('### Added\n\n### Fixed\n', True),
    ('### Fixed', True),
    ('- A synthetic fix.', False),
])
def test_empty_notes(notes, empty):
    # CONTRIBUTING.md, "What it checks", 5: "There are notes: lines under
    # `[Unreleased]`, or, for a final release after pre-releases, in their
    # sections." Headings alone aren't notes.
    assert release.body_is_empty(notes) is empty


def test_stamp_a_pre_release():
    # CONTRIBUTING.md: "makes the notes `## [3.0.0b1] - 2026-12-01` (today's
    # date) under a new empty `## [Unreleased]`, with the comparison link at
    # the bottom". Keep a Changelog 1.1.0: "At release time, you can move the
    # `Unreleased` section changes into a new release version section", "The
    # latest version comes first", and its link lines
    # (`[unreleased]: .../compare/v1.1.2...HEAD`).
    stamped = release.stamp(release.parse_changelog(CHANGELOG), '3.0.0b1', '2026-12-01',
                            '### Fixed\n\n- A synthetic fix.', '2.5.0', 'master')
    assert release.format_changelog(stamped) == CHANGELOG_AT_3_0_0B1


def test_a_final_opens_on_its_pre_releases_merged():
    # CONTRIBUTING.md: "A final release after pre-releases holds everything
    # since the last final. For 3.0.0 after 3.0.0b1, 3.0.0b2 and 3.0.0rc1,
    # the editor opens on `[Unreleased]` and those sections merged under one
    # set of headings: Added, Changed, Deprecated, Removed, Fixed and
    # Security, in that order, each with `[Unreleased]`'s lines first and
    # then each pre-release's, newest first; text above a section's first
    # heading comes first."
    changelog = release.parse_changelog(PRE_RELEASES)
    assert release.editor_text(changelog, Version('3.0.0')) == MERGED


def test_a_final_replaces_its_pre_releases():
    # CONTRIBUTING.md: "The pre-releases' sections and their links leave
    # `CHANGELOG.md`, and 3.0.0 gets one section, compared with 2.5.0."
    stamped = release.stamp(release.parse_changelog(PRE_RELEASES), '3.0.0', '2027-01-15',
                            MERGED, '2.5.0', 'master')
    assert release.format_changelog(stamped) == PRE_RELEASES_AT_3_0_0


def test_a_pre_release_opens_on_unreleased_as_written():
    # CONTRIBUTING.md: "It opens the editor ... on `[Unreleased]`'s text, to
    # trim or reword." Only a final merges, so a pre-release's text isn't
    # reordered.
    changelog = release.parse_changelog(PRE_RELEASES)
    assert release.editor_text(changelog, Version('3.0.0rc2')) == (
        '### Fixed\n\n- Fixed since the release candidate.\n\n'
        '### Added\n\n- Added since the release candidate.')


def test_merge_keeps_other_headings_after():
    # CONTRIBUTING.md: the merged headings are "Added, Changed, Deprecated,
    # Removed, Fixed and Security, in that order"; Keep a Changelog doesn't
    # forbid others, so a synthetic "Notes" heading comes after them.
    assert release.merge(['### Notes\n\n- A synthetic note.', '### Fixed\n\n- A synthetic fix.']) == (
        '### Fixed\n\n- A synthetic fix.\n\n### Notes\n\n- A synthetic note.')


def test_merge_drops_empty_headings():
    # CONTRIBUTING.md: a merged text holds "lines" under the headings; a
    # synthetic heading with nothing under it has none to hold.
    assert release.merge(['### Added\n\n### Fixed\n\n- A synthetic fix.']) == (
        '### Fixed\n\n- A synthetic fix.')


def test_another_versions_pre_releases_stay():
    # CONTRIBUTING.md: "The pre-releases' sections and their links leave
    # `CHANGELOG.md`" are those of the version released: 3.1.0 merges only
    # 3.1.0's, and 3.0.0b1 stays below 3.0.0 as the real file keeps
    # 1.0.0beta1-6 below 1.0.0. Synthetic.
    changelog = release.parse_changelog(TOP + '''## [Unreleased]

### Fixed

- x

## [3.1.0rc1] - 2027-03-01

### Fixed

- rc

## [3.0.0] - 2027-01-15

### Fixed

- f

## [3.0.0b1] - 2026-12-01

### Added

- b
''')
    text = release.editor_text(changelog, Version('3.1.0'))
    assert text == '### Fixed\n\n- x\n- rc'
    stamped = release.stamp(changelog, '3.1.0', '2027-04-01', text, '3.0.0', 'master')
    assert [section.name for section in stamped.sections] == [
        'Unreleased', '3.1.0', '3.0.0', '3.0.0b1']


def test_a_maintenance_release_compares_unreleased_with_its_branch():
    # CONTRIBUTING.md, "Fix releases from a maintenance branch": the fix's
    # line goes "under the branch's `[Unreleased]`", so after 3.0.1 the
    # branch's `[Unreleased]` link compares the new tag with the branch.
    stamped = release.stamp(release.parse_changelog(BRANCH_WITH_FIX), '3.0.1', '2027-03-01',
                            '### Fixed\n\n- A synthetic maintenance fix.', '3.0.0', '3.0.x')
    assert release.format_changelog(stamped) == BRANCH_AT_3_0_1


def test_a_maintenance_release_joins_masters_changelog():
    # CONTRIBUTING.md: the release pushes "a commit to `master` that adds the
    # 3.0.1 section to `master`'s `CHANGELOG.md`, which the News page is built
    # from". Keep a Changelog 1.1.0: "The latest version comes first", so it
    # lands by version, below 3.1.0b1.
    added = release.add_section(
        release.parse_changelog(MASTER_AT_3_1_0B1), '3.0.1', '2027-03-01',
        '### Fixed\n\n- A synthetic maintenance fix.', '3.0.0')
    assert release.format_changelog(added) == MASTER_AT_3_0_1
    with pytest.raises(release.Refusal) as refusal:
        release.add_section(added, '3.0.1', '2027-03-01', '### Fixed\n\n- x', '3.0.0')
    assert str(refusal.value) == "master's CHANGELOG.md already has a 3.0.1 section"


def test_release_page_text():
    # CONTRIBUTING.md: the GitHub Release has "the version's section of
    # `CHANGELOG.md`"; "Its release page starts with a paragraph saying how
    # to install it, to back up `~/.config/puddletag` first, and how to
    # report problems." (for a pre-release)
    assert release.release_page_text(release.parse_changelog(CHANGELOG), '2.5.0') == (
        '### Fixed\n\n- A synthetic 2.5.0 fix.')
    paragraph = ('This is a pre-release, for testing. Install it with '
                 '`pip install --pre puddletag==3.0.0b1`. Back up '
                 '`~/.config/puddletag`, where your settings are, before you start it. '
                 'Report problems with Help > Report a problem.')
    assert release.release_page_text(
        release.parse_changelog(CHANGELOG_AT_3_0_0B1), '3.0.0b1') == (
            paragraph + '\n\n### Fixed\n\n- A synthetic fix.')


def test_release_page_text_of_a_missing_or_empty_section():
    # CONTRIBUTING.md: "`release.py notes VERSION` prints the text of
    # VERSION's release page: its `CHANGELOG.md` section"; with no section,
    # or nothing in it, there is no text to print. Synthetic.
    with pytest.raises(release.Refusal) as missing:
        release.release_page_text(release.parse_changelog(CHANGELOG), '3.0.0')
    assert str(missing.value) == 'CHANGELOG.md has no section for 3.0.0'
    empty = release.parse_changelog(
        TOP + '## [Unreleased]\n\n## [2.5.0] - 2025-07-27\n\n## [2.4.0] - 2024-06-23\n\n- x\n')
    with pytest.raises(release.Refusal) as refusal:
        release.release_page_text(empty, '2.5.0')
    assert str(refusal.value) == 'The 2.5.0 section of CHANGELOG.md is empty'


def test_a_heading_not_in_the_layout_is_refused():
    # Keep a Changelog 1.1.0: release headings are "## [1.1.1] - 2023-03-05",
    # and "Keep an Unreleased section at the top". Synthetic.
    with pytest.raises(release.Refusal) as refusal:
        release.parse_changelog(TOP + '## Unreleased\n\n- x\n')
    assert str(refusal.value).startswith("CHANGELOG.md line 6 isn't a release heading")


def test_a_changelog_without_unreleased_is_refused():
    # Keep a Changelog 1.1.0: "Keep an Unreleased section at the top to
    # track upcoming changes." Synthetic.
    with pytest.raises(release.Refusal) as refusal:
        release.parse_changelog(TOP + '## [2.5.0] - 2025-07-27\n\n- x\n')
    assert str(refusal.value) == 'CHANGELOG.md has no ## [Unreleased] section at the top'


# The command ----------------------------------------------------------------

@pytest.fixture
def pypi(web_server, monkeypatch):
    """PyPI's JSON API on the local web server: 404 for a version it
    lacks, the version's JSON for one it has."""
    monkeypatch.setattr(release, 'PYPI_URL', web_server.url)

    class PyPI:
        def has(self, version):
            web_server.add(f'/pypi/puddletag/{version}/json',
                           json.dumps({'info': {'version': version}}),
                           content_type='application/json')

        def lacks(self, version):
            web_server.add(f'/pypi/puddletag/{version}/json', '{"message": "Not Found"}',
                           status=404, content_type='application/json')

    return PyPI()


EDITOR = '''\
import shutil
import sys
from pathlib import Path

folder = Path(__file__).parent
notes = Path(sys.argv[1])
shutil.copy(notes, folder / 'saw.md')
if (folder / 'writes.md').exists():
    shutil.copy(folder / 'writes.md', notes)
'''


class Editor:
    """An editor: keeps the text it was opened on (``saw``) and, once
    told what to write, writes it instead. ``command`` runs it."""

    def __init__(self, folder):
        folder.mkdir()
        self.folder = folder
        (folder / 'editor.py').write_text(EDITOR)
        self.command = f'{sys.executable} {folder / "editor.py"}'

    @property
    def saw(self):
        path = self.folder / 'saw.md'
        return path.read_text() if path.exists() else None

    def writes(self, text):
        (self.folder / 'writes.md').write_text(text)


@pytest.fixture
def editor(repo, tmp_path, monkeypatch):
    """The editor in GIT_EDITOR, the variable git reads first. After repo,
    which clears the editor variables."""
    editor = Editor(tmp_path / 'editor')
    monkeypatch.setenv('GIT_EDITOR', editor.command)
    return editor


@pytest.fixture
def ready(repo, gh, pypi, editor, clock, monkeypatch):
    """What a release of 3.0.0b1 from repo needs: All tests passed on
    HEAD, PyPI without the version, the tag's run showing up at once and
    passing, and today 2026-12-01. Synthetic."""
    monkeypatch.setattr(release, 'today', lambda: '2026-12-01')
    gh.check_run(repo.head())
    gh.tag_run('3.0.0b1')
    gh.watch()
    pypi.lacks('3.0.0b1')
    return repo


@pytest.fixture
def maintenance(ready, gh, pypi, monkeypatch):
    """3.0.x, branched at 3.0.0 while master went on to 3.1.0b1, holding a
    fix and ready to release 3.0.1; the branch is checked out. Synthetic."""
    repo = ready
    repo.commit({'CHANGELOG.md': AT_3_0_0,
                 'puddlestuff/__init__.py': "version_string = '3.0.0'\n"},
                'chore(release): 3.0.0')
    repo.tag('3.0.0')
    repo.git('branch', '3.0.x')
    repo.commit({'CHANGELOG.md': MASTER_AT_3_1_0B1,
                 'puddlestuff/__init__.py': "version_string = '3.1.0b1'\n"},
                'chore(release): 3.1.0b1')
    repo.tag('3.1.0b1')
    repo.push('master', '3.0.x', '3.0.0', '3.1.0b1')
    repo.git('switch', '-q', '3.0.x')
    repo.git('branch', '-q', '--set-upstream-to', 'origin/3.0.x')
    repo.commit({'CHANGELOG.md': BRANCH_WITH_FIX}, 'fix: a synthetic maintenance fix')
    repo.push('3.0.x')
    monkeypatch.setattr(release, 'today', lambda: '2027-03-01')
    gh.check_run(repo.head())
    gh.tag_run('3.0.1')
    pypi.lacks('3.0.1')
    return repo


def refused(repo, capsys, argv, message):
    """The command refuses with message and leaves everything as it was."""
    before = repo.state()
    assert release.main(argv) == 1
    assert message in capsys.readouterr().err
    assert repo.state() == before


def refuse_tags(repo):
    """An origin that refuses every tag, so an atomic push fails whole."""
    hook = repo.origin_path / 'hooks' / 'update'
    hook.write_text('#!/bin/sh\ncase "$1" in refs/tags/*) exit 1;; esac\n')
    hook.chmod(0o755)


def test_release_commits_tags_and_pushes_the_two_files(ready, answers, capsys, gh):
    # CONTRIBUTING.md, "What it does": "sets `version_string`; makes the
    # notes `## [3.0.0b1] - 2026-12-01` (today's date) under a new empty
    # `## [Unreleased]` ...; commits only those two files, as
    # `chore(release): 3.0.0b1`; makes the annotated tag `3.0.0b1`, whose
    # message is `puddletag 3.0.0b1`; pushes the branch and the tag, and
    # nothing else". "Your other changes, staged or not, stay out of the
    # release commit and stay as they are."
    repo = ready
    before_status = repo.git('status', '--porcelain')
    answers('y')
    assert release.main(['3.0.0b1']) == 0
    assert answers.prompts == ['Release 3.0.0b1? [y/N] ']
    assert repo.git('show', '-s', '--format=%s') == 'chore(release): 3.0.0b1'
    assert repo.git('show', '--name-only', '--format=', 'HEAD').split('\n') == [
        'CHANGELOG.md', 'puddlestuff/__init__.py']
    assert (repo.path / 'puddlestuff' / '__init__.py').read_text() == (
        "version_string = '3.0.0b1'\n")
    assert (repo.path / 'CHANGELOG.md').read_text() == CHANGELOG_AT_3_0_0B1
    assert repo.git('cat-file', '-t', '3.0.0b1') == 'tag'
    assert repo.git('tag', '-l', '--format=%(contents:subject)', '3.0.0b1') == 'puddletag 3.0.0b1'
    assert repo.git('rev-parse', '3.0.0b1^{commit}') == repo.head()
    assert repo.origin('rev-parse', 'master') == repo.head()
    assert repo.origin('tag', '--list').split() == ['2.4.0', '2.5.0', '3.0.0b1']
    assert repo.git('status', '--porcelain') == before_status
    out = capsys.readouterr().out
    for text in ('Version: 3.0.0b1 (a pre-release)', 'Branch: master', '- A synthetic fix.',
                 'https://pypi.org/project/puddletag/3.0.0b1/',
                 'https://github.com/puddletag/puddletag/releases/tag/3.0.0b1'):
        assert text in out
    assert gh.calls[-1] == ['run', 'watch', '303', '--repo', 'puddletag/puddletag',
                            '--exit-status']


def test_the_menus_choose_the_version(ready, answers):
    # CONTRIBUTING.md, "Versions": "With no version given, it offers the
    # ones that can come next: after a final release (2.5.0): `1) major:
    # 3.0.0`, ...; then, for the one chosen, `1) beta: 3.0.0b1`, ...".
    answers('1', '1', 'y')
    assert release.main([]) == 0
    assert '3.0.0b1' in ready.origin('tag', '--list').split()


def test_yes_skips_the_question(ready, answers):
    # CONTRIBUTING.md: "`--yes` skips the last question."
    assert release.main(['3.0.0b1', '--yes']) == 0
    assert answers.prompts == []


def test_the_edited_notes_become_the_section(ready, editor):
    # CONTRIBUTING.md, "The notes": it opens the editor on `[Unreleased]`'s
    # text, "to trim or reword", and "The text becomes the version's
    # section of `CHANGELOG.md`".
    editor.writes('### Fixed\n\n- A reworded synthetic fix.\n')
    assert release.main(['3.0.0b1', '--yes']) == 0
    assert editor.saw == '### Fixed\n\n- A synthetic fix.\n'
    assert ('## [3.0.0b1] - 2026-12-01\n\n### Fixed\n\n- A reworded synthetic fix.\n\n## [2.5.0]'
            in (ready.path / 'CHANGELOG.md').read_text())


@pytest.mark.parametrize('chosen', ['core.editor', 'EDITOR', 'VISUAL'])
def test_the_editor_git_would_open(chosen, ready, editor, monkeypatch):
    # CONTRIBUTING.md, "The notes": "It opens the editor `git commit` opens
    # (`GIT_EDITOR`, `core.editor`, `VISUAL`, `EDITOR`)". Git skips VISUAL
    # on a dumb terminal, and the container has no TERM.
    monkeypatch.delenv('GIT_EDITOR')
    monkeypatch.setenv('TERM', 'xterm')
    if chosen == 'core.editor':
        ready.git('config', 'core.editor', editor.command)
        monkeypatch.setenv('VISUAL', 'false')
        monkeypatch.setenv('EDITOR', 'false')
    elif chosen == 'VISUAL':
        monkeypatch.setenv('VISUAL', editor.command)
        monkeypatch.setenv('EDITOR', 'false')
    else:
        monkeypatch.setenv('EDITOR', editor.command)
    assert release.main(['3.0.0b1', '--yes']) == 0
    assert editor.saw is not None


def test_refuses_a_version_not_in_normal_form(ready, capsys, gh):
    # CONTRIBUTING.md, "What it checks" 1: "The version is in normal form".
    refused(ready, capsys, ['v3.0.0', '--yes'], "v3.0.0 isn't in normal form: write 3.0.0")
    assert gh.calls == []


def test_refuses_off_master(ready, capsys):
    # CONTRIBUTING.md, "What it checks" 2: "The branch is `master` or a
    # maintenance branch".
    ready.git('switch', '-q', '-c', 'feature')
    refused(ready, capsys, ['3.0.0b1', '--yes'], 'not on feature')


def test_refuses_a_detached_head(ready, capsys):
    # CONTRIBUTING.md, "What it checks" 2: "The branch is `master` or a
    # maintenance branch".
    ready.git('switch', '-q', '--detach')
    refused(ready, capsys, ['3.0.0b1', '--yes'], "HEAD isn't on a branch")


def test_refuses_a_commit_to_push(ready, capsys):
    # CONTRIBUTING.md, "What it checks" 2: "after a fetch, HEAD is the same
    # commit on `origin`: nothing to push, nothing to pull."
    ready.commit({'other.txt': 'x\n'})
    refused(ready, capsys, ['3.0.0b1', '--yes'], '(1 to push, 0 to pull)')


def test_refuses_a_commit_to_pull(ready, capsys, tmp_path):
    # CONTRIBUTING.md, "What it checks" 2: "nothing to push, nothing to pull."
    other = tmp_path / 'other'
    run_git(tmp_path, 'clone', '-q', str(ready.origin_path), str(other))
    (other / 'other.txt').write_text('x\n')
    run_git(other, 'add', 'other.txt')
    run_git(other, 'commit', '-q', '-m', 'A synthetic change')
    run_git(other, 'push', '-q', 'origin', 'master')
    refused(ready, capsys, ['3.0.0b1', '--yes'], '(0 to push, 1 to pull)')


def test_refuses_a_changed_changelog(ready, capsys):
    # CONTRIBUTING.md, "What it checks" 2: "`puddlestuff/__init__.py` and
    # `CHANGELOG.md` have no local changes."
    with open(ready.path / 'CHANGELOG.md', 'a') as file:
        file.write('A synthetic line.\n')
    refused(ready, capsys, ['3.0.0b1', '--yes'], 'CHANGELOG.md has local changes')


def test_refuses_a_staged_version_file(ready, capsys):
    # CONTRIBUTING.md, "What it checks" 2: "`puddlestuff/__init__.py` and
    # `CHANGELOG.md` have no local changes."
    with open(ready.path / 'puddlestuff' / '__init__.py', 'a') as file:
        file.write('# A synthetic line.\n')
    ready.git('add', 'puddlestuff/__init__.py')
    refused(ready, capsys, ['3.0.0b1', '--yes'], 'puddlestuff/__init__.py has local changes')


def test_refuses_a_version_below_a_tag(ready, capsys):
    # CONTRIBUTING.md, "What it checks" 1: "The version is ... above every
    # tag."
    refused(ready, capsys, ['2.4.1', '--yes'], "2.4.1 isn't above 2.5.0, the newest tag")


def test_refuses_a_tag_here(ready, capsys):
    # CONTRIBUTING.md, "What it checks" 3: "The tag exists neither here nor
    # on GitHub".
    ready.tag('3.0.0b1', annotated=False)
    refused(ready, capsys, ['3.0.0b1', '--yes'], 'Tag 3.0.0b1 already exists here')


def test_refuses_a_tag_on_github(ready, capsys):
    # CONTRIBUTING.md, "What it checks" 3: "The tag exists neither here nor
    # on GitHub".
    ready.origin('tag', '3.0.0b1', 'master')
    refused(ready, capsys, ['3.0.0b1', '--yes'], 'Tag 3.0.0b1 already exists on GitHub')


def test_refuses_nothing_to_release(ready, capsys, gh):
    # CONTRIBUTING.md, "What it checks" 5: "There are notes: lines under
    # `[Unreleased]`". Synthetic changelog without them.
    ready.commit({'CHANGELOG.md': CHANGELOG.replace('### Fixed\n\n- A synthetic fix.\n\n', '', 1)})
    ready.push('master')
    gh.check_run(ready.head())
    refused(ready, capsys, ['3.0.0b1', '--yes'], "There's nothing to release")


def test_refuses_when_pypi_has_it(ready, capsys, pypi):
    # CONTRIBUTING.md, "What it checks" 3: "PyPI doesn't have the version."
    pypi.has('3.0.0b1')
    refused(ready, capsys, ['3.0.0b1', '--yes'], 'PyPI already has puddletag 3.0.0b1')


def test_refuses_when_pypi_is_unreachable(ready, capsys, web_server):
    # CONTRIBUTING.md, "What it checks" 3: "PyPI doesn't have the version."
    # An answer that isn't a plain yes or no can't be taken for a no.
    web_server.add('/pypi/puddletag/3.0.0b1/json', status=500)
    refused(ready, capsys, ['3.0.0b1', '--yes'], "Couldn't ask PyPI whether it has 3.0.0b1")


def test_refuses_when_the_tests_failed(ready, capsys, gh):
    # CONTRIBUTING.md, "What it checks" 4: ""All tests passed" passed on
    # HEAD's commit."
    gh.check_run(ready.head(), 'failure')
    refused(ready, capsys, ['3.0.0b1', '--yes'],
            f'All tests passed ended in failure on {ready.head()[:7]}: '
            'https://github.com/puddletag/puddletag/actions/runs/101/job/202')


def test_refuses_when_the_editor_failed(ready, capsys, monkeypatch):
    # CONTRIBUTING.md, "The notes": it opens the editor on the notes; an
    # editor that fails stops the release before anything changes.
    monkeypatch.setenv('GIT_EDITOR', 'false')
    refused(ready, capsys, ['3.0.0b1', '--yes'], 'The editor ended with status 1')


def test_refuses_empty_notes(ready, capsys, editor):
    # CONTRIBUTING.md, "The notes": "An empty text stops it".
    editor.writes('\n  \n')
    refused(ready, capsys, ['3.0.0b1', '--yes'], 'The notes are empty')


def test_refuses_a_heading_in_the_notes(ready, capsys, editor):
    # CONTRIBUTING.md, "The notes": "An empty text stops it, and so does a
    # `#` or `##` heading."
    editor.writes('## Fixed\n\n- x\n')
    refused(ready, capsys, ['3.0.0b1', '--yes'], "can't hold a # or ## heading")


@pytest.mark.parametrize('typed', ['n', '', None])
def test_no_changes_nothing(typed, ready, answers, capsys):
    # CONTRIBUTING.md, "What it does": it "asks `Release 3.0.0b1? [y/N]`";
    # only a yes goes on. The end of input is a no.
    if typed is not None:
        answers(typed)
    before = ready.state()
    assert release.main(['3.0.0b1']) == 1
    assert ready.state() == before
    out, err = capsys.readouterr()
    assert 'Nothing changed.' in out + err


def test_waits_while_all_tests_passed_runs(ready, clock, capsys, gh):
    # CONTRIBUTING.md, "What it checks" 4: "While CI is still running on
    # it, the command waits".
    head = ready.head()
    gh.check_run(head, 'in_progress', 'success')
    assert release.main(['3.0.0b1', '--yes']) == 0
    assert clock.waits[0] == 30
    assert f'Waiting for All tests passed on {head[:7]} (in_progress)' in capsys.readouterr().out


def test_waits_for_ci_to_reach_all_tests_passed(ready, clock, gh):
    # CONTRIBUTING.md, "What it checks" 4: "While CI is still running on
    # it, the command waits". The job doesn't exist until the tests it
    # needs are done, so the workflow's run is what shows CI is going.
    head = ready.head()
    gh.check_run(head, None, 'success')
    gh.push_runs('master', head, 'in_progress')
    assert release.main(['3.0.0b1', '--yes']) == 0
    assert clock.waits[0] == 30


def test_stops_when_no_ci_run_shows_up(ready, clock, capsys, gh):
    # CONTRIBUTING.md, "What it checks" 4: "if no run shows up within a
    # minute, it stops."
    head = ready.head()
    gh.check_run(head, None)
    gh.push_runs('master', head, None)
    refused(ready, capsys, ['3.0.0b1', '--yes'], f'No CI run on {head[:7]} after a minute')
    assert clock.waits == [30, 30]


def test_stops_when_the_run_ended_without_all_tests_passed(ready, capsys, gh):
    # CONTRIBUTING.md, "What it checks" 4: ""All tests passed" passed on
    # HEAD's commit." A finished run with no such job didn't get there.
    head = ready.head()
    gh.check_run(head, None)
    gh.push_runs('master', head, 'completed')
    refused(ready, capsys, ['3.0.0b1', '--yes'], 'ended without All tests passed')


def test_a_refused_push_puts_everything_back(ready, capsys):
    # CONTRIBUTING.md, "What it does": "pushes the branch and the tag, and
    # nothing else, in one atomic push: both land or neither does. If the
    # push is refused, it removes the commit and the tag and puts the two
    # files back."
    refuse_tags(ready)
    refused(ready, capsys, ['3.0.0b1', '--yes'], 'The push was refused')


def test_a_final_after_pre_releases(ready, editor, gh, pypi, monkeypatch):
    # CONTRIBUTING.md, "The notes": "A final release after pre-releases
    # holds everything since the last final. For 3.0.0 after 3.0.0b1,
    # 3.0.0b2 and 3.0.0rc1, the editor opens on `[Unreleased]` and those
    # sections merged under one set of headings".
    repo = ready
    repo.commit({'CHANGELOG.md': PRE_RELEASES,
                 'puddlestuff/__init__.py': "version_string = '3.0.0rc1'\n"})
    for tag in ('3.0.0b1', '3.0.0b2', '3.0.0rc1'):
        repo.tag(tag)
    repo.push('master', '3.0.0b1', '3.0.0b2', '3.0.0rc1')
    monkeypatch.setattr(release, 'today', lambda: '2027-01-15')
    gh.check_run(repo.head())
    gh.tag_run('3.0.0')
    pypi.lacks('3.0.0')
    assert release.main(['3.0.0', '--yes']) == 0
    assert editor.saw == MERGED + '\n'
    assert (repo.path / 'CHANGELOG.md').read_text() == PRE_RELEASES_AT_3_0_0


def test_a_release_candidate_becomes_final_with_nothing_new(ready, editor, gh, pypi, monkeypatch):
    # CONTRIBUTING.md, "What it checks" 5: "There are notes: lines under
    # `[Unreleased]`, or, for a final release after pre-releases, in their
    # sections." Synthetic: [Unreleased] emptied.
    repo = ready
    repo.commit({'CHANGELOG.md': PRE_RELEASES.replace(
                     '### Fixed\n\n- Fixed since the release candidate.\n\n### Added\n\n'
                     '- Added since the release candidate.\n\n', '', 1),
                 'puddlestuff/__init__.py': "version_string = '3.0.0rc1'\n"})
    for tag in ('3.0.0b1', '3.0.0b2', '3.0.0rc1'):
        repo.tag(tag)
    repo.push('master', '3.0.0b1', '3.0.0b2', '3.0.0rc1')
    monkeypatch.setattr(release, 'today', lambda: '2027-01-15')
    gh.check_run(repo.head())
    gh.tag_run('3.0.0')
    pypi.lacks('3.0.0')
    assert release.main(['3.0.0', '--yes']) == 0
    assert editor.saw.startswith(
        'The first beta.\n\n### Added\n\n- Added in the first beta.\n\n### Changed')


def test_a_failed_ci_run_says_to_re_run_it(ready, capsys, gh):
    # CONTRIBUTING.md: "A job that fails (an outage, a flaky test) is
    # re-run from the Actions page with "Re-run failed jobs"; nothing has
    # to be undone."
    gh.watch(1)
    assert release.main(['3.0.0b1', '--yes']) == 1
    assert ('re-run its failed jobs from https://github.com/puddletag/puddletag/actions/runs/303'
            in capsys.readouterr().out)
    assert '3.0.0b1' in ready.origin('tag', '--list').split()


def test_the_tag_run_shows_up_late(ready, clock, gh):
    # CONTRIBUTING.md, "What it does": "Then it follows CI's run on the tag
    # (`gh run watch`)". The run takes a few polls to appear.
    gh.tag_run('3.0.0b1', False, False, True)
    assert release.main(['3.0.0b1', '--yes']) == 0
    assert clock.waits[-2:] == [3, 3]
    assert ['run', 'watch', '303', '--repo', 'puddletag/puddletag', '--exit-status'] in gh.calls


def test_the_tag_run_never_shows_up(ready, clock, capsys, gh):
    # CONTRIBUTING.md, "What it does": "Then it follows CI's run on the tag
    # (`gh run watch`) and prints the PyPI and GitHub links." A run that
    # never shows up leaves the links and no watch.
    gh.tag_run('3.0.0b1', False)
    assert release.main(['3.0.0b1', '--yes']) == 0
    out = capsys.readouterr().out
    assert "hasn't shown up after a minute" in out
    assert 'https://pypi.org/project/puddletag/3.0.0b1/' in out
    assert 'https://github.com/puddletag/puddletag/releases/tag/3.0.0b1' in out
    assert not [call for call in gh.calls if call[:2] == ['run', 'watch']]
    assert clock.waits == [3] * 20


def test_a_fix_release_from_a_maintenance_branch(maintenance):
    # CONTRIBUTING.md, "Fix releases from a maintenance branch": run
    # `release.py` on the branch: "It offers 3.0.1, checks it against the
    # 3.0 tags only, and, in the same atomic push as the branch and the
    # tag, pushes a commit to `master` that adds the 3.0.1 section to
    # `master`'s `CHANGELOG.md`".
    repo = maintenance
    master_before = repo.origin('rev-parse', 'master')
    before_status = repo.git('status', '--porcelain')
    assert release.main(['3.0.1', '--yes']) == 0
    assert repo.origin('rev-parse', '3.0.x') == repo.head()
    assert repo.git('show', '-s', '--format=%s') == 'chore(release): 3.0.1'
    assert (repo.path / 'CHANGELOG.md').read_text() == BRANCH_AT_3_0_1
    assert (repo.path / 'puddlestuff' / '__init__.py').read_text() == "version_string = '3.0.1'\n"
    assert repo.origin('rev-parse', '3.0.1^{commit}') == repo.head()
    assert repo.origin('show', '-s', '--format=%s', 'master') == (
        'chore(release): add 3.0.1 to CHANGELOG.md')
    assert repo.origin('rev-parse', 'master^') == master_before
    assert repo.origin('show', '--name-only', '--format=', 'master') == 'CHANGELOG.md'
    assert repo.origin('show', 'master:CHANGELOG.md') + '\n' == MASTER_AT_3_0_1
    assert repo.git('branch', '--show-current') == '3.0.x'
    assert repo.git('status', '--porcelain') == before_status
    assert repo.git('worktree', 'list', '--porcelain').count('worktree ') == 1


def test_a_maintenance_branch_offers_its_next_patch(maintenance, answers):
    # CONTRIBUTING.md, "Versions": "on a maintenance branch (3.0.x, at
    # 3.0.0): `1) beta: 3.0.1b1`, `2) release candidate: 3.0.1rc1`,
    # `3) final: 3.0.1`."
    answers('3')
    assert release.main(['--yes']) == 0
    assert '3.0.1' in maintenance.origin('tag', '--list').split()


def test_a_maintenance_branch_releases_its_line_only(maintenance, capsys):
    # CONTRIBUTING.md, "What it checks" 1: "On a maintenance branch, the
    # version is of the branch's line (3.0 on 3.0.x)".
    refused(maintenance, capsys, ['3.1.0', '--yes'],
            'The 3.0.x branch releases 3.0 versions only, not 3.1.0')


def test_a_refused_push_leaves_master_alone(maintenance, capsys):
    # CONTRIBUTING.md, "What it does": "both land or neither does"; a fix
    # release's push to `master` is part of the same atomic push.
    refuse_tags(maintenance)
    refused(maintenance, capsys, ['3.0.1', '--yes'], 'The push was refused')


def interrupt_push(monkeypatch, after_pushing):
    """Makes the release's `git push` end in Ctrl+C, once the push has
    really run (after_pushing) or before it does."""
    real = subprocess.run

    def run(args, *rest, **options):
        if list(args[:2]) == ['git', 'push']:
            if after_pushing:
                real(args, *rest, **options)
            raise KeyboardInterrupt
        return real(args, *rest, **options)

    monkeypatch.setattr(release.subprocess, 'run', run)


def test_an_interrupt_after_the_push_landed_goes_on(ready, capsys, monkeypatch):
    # CONTRIBUTING.md, "What it does": "pushes the branch and the tag, and
    # nothing else, in one atomic push: both land or neither does." A push
    # that GitHub took and whose Ctrl+C reached git afterwards is a
    # release that went out: nothing is put back, and the command follows
    # CI. Synthetic.
    interrupt_push(monkeypatch, after_pushing=True)
    assert release.main(['3.0.0b1', '--yes']) == 0
    assert repo_subject(ready) == 'chore(release): 3.0.0b1'
    assert ready.git('cat-file', '-t', '3.0.0b1') == 'tag'
    assert ready.origin('rev-parse', 'master') == ready.head()
    assert '3.0.0b1' in ready.origin('tag', '--list').split()
    assert 'Published 3.0.0b1' in capsys.readouterr().out


def test_an_interrupt_before_the_push_landed_puts_everything_back(ready, capsys, monkeypatch):
    # CONTRIBUTING.md, "What it does": "both land or neither does. If the
    # push is refused, it removes the commit and the tag and puts the two
    # files back." An interrupted push that GitHub never took is the same,
    # said as an interruption. Synthetic.
    interrupt_push(monkeypatch, after_pushing=False)
    refused(ready, capsys, ['3.0.0b1', '--yes'], 'The push was interrupted')
    assert ready.origin('tag', '--list').split() == ['2.4.0', '2.5.0']


def repo_subject(repo):
    return repo.git('show', '-s', '--format=%s')


def objects(repo):
    """Every object in the repository, loose or packed."""
    return repo.git('cat-file', '--batch-all-objects', '--batch-check')


def test_a_dry_run_shows_the_release_and_changes_nothing(ready, answers, capsys, gh):
    # CONTRIBUTING.md, "Releasing": "`--dry-run` makes no release: it runs
    # every check and opens your editor as for real, then shows what a
    # release would change in `puddlestuff/__init__.py` and `CHANGELOG.md`
    # ... and the commit, tag and push it would make, and stops without
    # asking. Nothing is written or pushed."
    before = ready.state()
    before_objects = objects(ready)
    assert release.main(['3.0.0b1', '--dry-run']) == 0
    assert ready.state() == before
    assert objects(ready) == before_objects
    assert answers.prompts == []
    out = capsys.readouterr().out
    for text in ('Dry run: nothing changed. A release would:',
                 "version_string = '3.0.0b1'",
                 '--- a/CHANGELOG.md', '+++ b/CHANGELOG.md',
                 '+## [3.0.0b1] - 2026-12-01',
                 '+[3.0.0b1]: https://github.com/puddletag/puddletag/compare/2.5.0...3.0.0b1',
                 'git commit --only -m "chore(release): 3.0.0b1"',
                 'git tag -a 3.0.0b1 -m "puddletag 3.0.0b1"',
                 'git push --atomic --no-follow-tags origin master refs/tags/3.0.0b1'):
        assert text in out
    assert not [call for call in gh.calls if call[:2] == ['run', 'watch']]
    assert not [call for call in gh.calls if '--branch' in call and '3.0.0b1' in call]


def test_a_dry_run_refuses_as_the_release_does(ready, capsys):
    # CONTRIBUTING.md, "Releasing": "A check that fails stops it as it
    # would stop a release". Synthetic: the tag is already on GitHub.
    ready.origin('tag', '3.0.0b1', 'master')
    refused(ready, capsys, ['3.0.0b1', '--dry-run'], 'Tag 3.0.0b1 already exists on GitHub')


def test_a_dry_run_of_a_fix_release_shows_masters_changelog(maintenance, answers, capsys):
    # CONTRIBUTING.md, "Releasing": "`--dry-run` ... shows what a release
    # would change in ... `master`'s `CHANGELOG.md`, for a fix release ...
    # Nothing is written or pushed."
    repo = maintenance
    before = repo.state()
    before_objects = objects(repo)
    assert release.main(['3.0.1', '--dry-run', '--yes']) == 0
    assert repo.state() == before
    assert objects(repo) == before_objects
    assert answers.prompts == []
    out = capsys.readouterr().out
    assert out.count('--- a/CHANGELOG.md') == 2  # the branch's, then master's
    assert out.count('+## [3.0.1] - 2027-03-01') == 2
    assert ("<a commit adding 3.0.1 to master's CHANGELOG.md>:refs/heads/master" in out)
    assert repo.origin('for-each-ref', '--format=%(refname) %(objectname)') == before['origin']


# The commands CI runs ---------------------------------------------------------

def release_commit(repo, version, changelog=CHANGELOG, tag=None, push=None, annotated=True):
    """Makes a release commit and its tag the way the command does."""
    repo.commit({'CHANGELOG.md': changelog,
                 'puddlestuff/__init__.py': f"version_string = '{version}'\n"},
                f'chore(release): {version}')
    repo.tag(tag or version, annotated=annotated)
    repo.push(push or repo.git('branch', '--show-current'), tag or version)


@pytest.mark.parametrize('version, latest, prerelease', [
    ('3.0.0', 'true', 'false'),
    ('3.0.0b1', 'false', 'true'),
])
def test_check_passes_a_tag_the_command_made(repo, capsys, version, latest, prerelease):
    # CONTRIBUTING.md: "`release.py check TAG` exits non-zero unless ... It
    # prints the GitHub Release's settings for `$GITHUB_OUTPUT`: `latest`,
    # `notes-start-tag` and `prerelease`." Synthetic repository.
    release_commit(repo, version)
    assert release.main(['check', version]) == 0
    assert capsys.readouterr().out == (
        f'latest={latest}\nnotes-start-tag=2.5.0\nprerelease={prerelease}\n')


def test_check_refuses_a_tag_that_isnt_the_version(repo, capsys):
    # CONTRIBUTING.md: "`release.py check TAG` exits non-zero unless the tag
    # is annotated, is the `version_string` of its commit". Synthetic.
    release_commit(repo, '3.0.0b1', tag='3.0.0b2')
    assert release.main(['check', '3.0.0b2']) == 1
    assert "3.0.0b2's commit has version_string 3.0.0b1" in capsys.readouterr().err


def test_check_refuses_a_commit_off_master(repo, capsys):
    # CONTRIBUTING.md: "`release.py check TAG` exits non-zero unless ... the
    # commit is on `origin/master` or on the tag's maintenance branch".
    # Synthetic.
    repo.git('switch', '-q', '-c', 'feature')
    release_commit(repo, '3.0.0b1')
    assert release.main(['check', '3.0.0b1']) == 1
    assert 'is on neither origin/master nor origin/3.0.x' in capsys.readouterr().err


def test_check_refuses_a_tag_not_in_normal_form(repo, capsys):
    # PEP 440 normal form: "v3.0.0" normalizes to "3.0.0"; CONTRIBUTING.md:
    # the tag is "in normal form". Synthetic.
    assert release.main(['check', 'v3.0.0']) == 1
    assert "v3.0.0 isn't in normal form: write 3.0.0" in capsys.readouterr().err


def test_check_refuses_a_lightweight_tag(repo, capsys):
    # CONTRIBUTING.md: "`release.py check TAG` exits non-zero unless the tag
    # is annotated". Synthetic.
    release_commit(repo, '3.0.0b1', annotated=False)
    assert release.main(['check', '3.0.0b1']) == 1
    assert '3.0.0b1 is a lightweight tag' in capsys.readouterr().err


def test_check_refuses_a_missing_tag(repo, capsys):
    # CONTRIBUTING.md: "`release.py check TAG` exits non-zero unless" the tag
    # exists. Synthetic.
    assert release.main(['check', '3.0.0b1']) == 1
    assert "There's no tag 3.0.0b1 here" in capsys.readouterr().err


def test_check_passes_a_fix_on_its_maintenance_branch(repo, capsys):
    # CONTRIBUTING.md: a fix on a maintenance branch (3.0.x) is released
    # from there; GitHub's "Latest" stays on the highest final. Synthetic.
    release_commit(repo, '3.0.0', AT_3_0_0)
    repo.git('switch', '-q', '-c', '3.0.x')
    release_commit(repo, '3.0.1', BRANCH_AT_3_0_1)
    assert release.main(['check', '3.0.1']) == 0
    assert capsys.readouterr().out == 'latest=true\nnotes-start-tag=3.0.0\nprerelease=false\n'
    repo.git('tag', '3.1.0', 'master')
    assert release.main(['check', '3.0.1']) == 0
    assert capsys.readouterr().out == 'latest=false\nnotes-start-tag=3.0.0\nprerelease=false\n'


def test_notes_prints_the_section(repo, capsys):
    # CONTRIBUTING.md: "`release.py notes VERSION` prints the text of
    # VERSION's release page: its `CHANGELOG.md` section". Synthetic.
    assert release.main(['notes', '2.5.0']) == 0
    assert capsys.readouterr().out == '### Fixed\n\n- A synthetic 2.5.0 fix.\n'


def test_notes_of_a_pre_release_start_with_how_to_try_it(repo, capsys):
    # CONTRIBUTING.md: "Its release page starts with a paragraph saying how
    # to install it, to back up `~/.config/puddletag` first, and how to
    # report problems." (for a pre-release) Synthetic.
    repo.write({'CHANGELOG.md': CHANGELOG_AT_3_0_0B1})
    assert release.main(['notes', '3.0.0b1']) == 0
    paragraph = ('This is a pre-release, for testing. Install it with '
                 '`pip install --pre puddletag==3.0.0b1`. Back up '
                 '`~/.config/puddletag`, where your settings are, before you start it. '
                 'Report problems with Help > Report a problem.')
    assert capsys.readouterr().out == paragraph + '\n\n### Fixed\n\n- A synthetic fix.\n'


def test_notes_of_a_missing_version_fail(repo, capsys):
    # CONTRIBUTING.md: "`release.py notes VERSION` prints the text of
    # VERSION's release page"; with no section there is none. Synthetic.
    assert release.main(['notes', '3.0.0']) == 1
    assert 'CHANGELOG.md has no section for 3.0.0' in capsys.readouterr().err


def test_release_py_runs_as_a_script(repo):
    # CONTRIBUTING.md: CI runs `release.py notes "$GITHUB_REF_NAME"` as a
    # script. Synthetic.
    result = subprocess.run([sys.executable, str(ROOT / 'release.py'), 'notes', '2.5.0'],
                            cwd=repo.path, capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout == '### Fixed\n\n- A synthetic 2.5.0 fix.\n'
