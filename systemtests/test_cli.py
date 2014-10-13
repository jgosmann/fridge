import errno
import os
import os.path
import stat
import sys

import scripttest


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
    env.run(sys.executable, FRIDGE, 'commit')
    os.unlink(os.path.join(env.base_path, 'somefile'))
    result = env.run(sys.executable, FRIDGE, 'checkout', 'somefile')
    assert result.files_created['somefile'].bytes == 'with some content'
    assert stat.S_IMODE(os.stat(
        result.files_created['somefile'].full).st_mode) == mode
