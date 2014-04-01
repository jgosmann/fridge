import errno
import os

import pytest

from fridge.memoryfs import MemoryFile, MemoryFS


class TestMemoryFile(object):
    def test_can_be_written(self):
        f = MemoryFile()
        f.write('test')
        f.flush()
        assert f.content == 'test'

    def test_close_flushes_content(self):
        f = MemoryFile()
        f.write('test')
        f.close()
        assert f.content == 'test'

    def test_can_be_reopened_and_read(self):
        f = MemoryFile()
        f.write('test')
        f.close()
        f.open()
        assert f.read() == 'test'

    def test_can_be_used_in_with(self):
        with MemoryFile() as f:
            f.write('test')
        assert f.content == 'test'


class TestMemoryFS(object):
    def test_parent_of_top_node_is_node_itself(self):
        fs = MemoryFS()
        assert fs.parent == fs

    def test_get_node_without_path(self):
        fs = MemoryFS()
        assert fs == fs.get_node([])

    def test_get_subnodes(self):
        fs = MemoryFS()
        fs1 = MemoryFS(fs)
        fs2 = MemoryFS(fs1)
        fs.children['1'] = fs1
        fs1.children['2'] = fs2
        assert fs2 == fs.get_node(['1', os.curdir, os.pardir, '1', '2'])

    def test_get_parent_node_of_parent_is_parent(self):
        # This corresponds to Unix behavior
        fs = MemoryFS()
        assert fs.get_node([os.pardir]) == fs

    def test_get_non_existent_node(self):
        fs = MemoryFS()
        with pytest.raises(KeyError):
            fs.get_node(['nonexistent'])

    def test_mkdir(self):
        fs = MemoryFS()
        fs.mkdir('test')
        fs.mkdir('test/subdir')
        assert 'test' in fs.children
        assert 'subdir' in fs.children['test'].children

    def test_mkdir_raises_exception_if_dir_exists(self):
        fs = MemoryFS()
        fs.mkdir('dir')
        with pytest.raises(OSError) as excinfo:
            fs.mkdir('dir')
        assert excinfo.value.errno == errno.EEXIST
        assert excinfo.value.filename == 'dir'

    @pytest.mark.parametrize('mode', ['w', 'w+', 'a', 'a+'])
    def test_allows_writing_of_files(self, mode):
        fs = MemoryFS()
        with fs.open('filename', mode) as f:
            f.write('dummy content')
        assert fs.children['filename'].content == 'dummy content'
