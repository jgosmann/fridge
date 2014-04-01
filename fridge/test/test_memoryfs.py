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
    def test_mkdir(self):
        fs = MemoryFS()
        fs.mkdir('test')
        assert 'test' in fs.children
