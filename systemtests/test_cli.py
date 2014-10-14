import errno
import os
import os.path
import re
import stat
import sys

import scripttest


HASH_REGEX = r'[0-9a-f]{40}'
# FIXME dependent on locale
DATE_REGEX = (
    r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun) ' +
    r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) ' +
    r'\d{1,2} \d{1,2}:\d{2}:\d{2} \d+ [-+]\d{4}')


def find_executable(name):
    for path in os.environ['PATH'].split(os.pathsep):
        full_path = os.path.join(path, name)
        if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
            return full_path
    raise OSError(errno.ENOENT, 'Command not found.', name)


FRIDGE = find_executable('fridge')


def test_persists_data():
    env = scripttest.TestFileEnvironment()
    env.run(sys.executable, FRIDGE, 'init')
    f = env.writefile('somefile', b'with some content')
    mode = stat.S_IRWXU
    os.chmod(f.full, mode)
    # Some systems (Windows) do not fully support chmod. Thus check the actual
    # mode set.
    mode = stat.S_IMODE(os.stat(f.full).st_mode)
    env.run(sys.executable, FRIDGE, 'commit')
    os.unlink(os.path.join(env.base_path, 'somefile'))
    result = env.run(sys.executable, FRIDGE, 'checkout', 'somefile')
    assert result.files_created['somefile'].bytes == 'with some content'
    assert stat.S_IMODE(os.stat(
        result.files_created['somefile'].full).st_mode) == mode


def test_has_log():
    env = scripttest.TestFileEnvironment()
    env.run(sys.executable, FRIDGE, 'init')
    env.writefile('somefile', b'with some content')
    env.run(sys.executable, FRIDGE, 'commit', '-m', 'First commit.')
    env.writefile('somefile2', b'with some content')
    env.run(sys.executable, FRIDGE, 'commit', '-m', 'Second commit.')
    result = env.run(sys.executable, FRIDGE, 'log')
    assert re.match(r"""commit {hash}
Date: {date}

    Second commit.

commit {hash}
Date: {date}

    First commit.

""".format(hash=HASH_REGEX, date=DATE_REGEX), result.stdout)
