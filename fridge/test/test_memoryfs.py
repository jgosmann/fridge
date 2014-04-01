import os

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

    def test_mkdir(self):
        fs = MemoryFS()
        fs.mkdir('test')
        fs.mkdir('test/subdir')
        assert 'test' in fs.children
        assert 'subdir' in fs.children['test'].children
