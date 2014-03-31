import os
import os.path

from scripttest import TestFileEnvironment


def test_persists_data():
    env = TestFileEnvironment()
    # FIXME path to fridge script should be determined in some other way
    env.run('../../bin/fridge', 'init')
    env.writefile('somefile', 'with some content')
    env.run('../../bin/fridge', 'commit')
    os.unlink(os.path.join(env.base_path, 'somefile'))
    result = env.run('../../bin/fridge', 'checkout', 'somefile')
    assert result.files_created['somefile'].bytes == 'with some content'
