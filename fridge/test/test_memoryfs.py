import errno
import os
import stat

import pytest

from fridge.memoryfs import MemoryFile, MemoryFS


def write_file(fs, path, content=u'foo'):
    with fs.open(path, 'w') as f:
        f.write(content)


def assert_file_content_equal(fs, path, content):
    with fs.open(path, 'r') as f:
        assert f.read() == content


def assert_open_raises(fs, path, err, mode='r'):
    with pytest.raises(OSError) as excinfo:
        with fs.open(path, mode):
            pass
    assert excinfo.value.errno == err
    assert excinfo.value.filename == path


@pytest.fixture
def fs():
    return MemoryFS()


class TestMemoryFile(object):
    @pytest.fixture(params=['t', 'b'])
    def mode(self, request):
        return request.param

    @pytest.fixture
    def mf(self, mode):
        f = MemoryFile()
        f.open(mode)
        return f

    @pytest.fixture
    def test_content(self, mode):
        if mode == 'b':
            return b'testbytes'
        else:
            return u'testbytes'

    def test_can_be_written(self, mf, test_content):
        mf.write(test_content)
        mf.flush()
        assert mf.content == b'testbytes'

    def test_close_flushes_content(self, mf, test_content):
        mf.write(test_content)
        mf.close()
        assert mf.content == b'testbytes'

    def test_can_be_reopened_and_read(self, mf, test_content):
        mf.write(test_content)
        mf.close()
        mf.open()
        assert mf.read() == u'testbytes'

    def test_can_be_used_in_with(self, mode, test_content):
        with MemoryFile().open(mode) as f:
            f.write(test_content)
        assert f.content == b'testbytes'

    def test_can_append(self, mf, mode, test_content):
        mf.write(test_content)
        mf.close()
        with mf.open(mode + 'a') as f:
            f.write(test_content)
        assert mf.content == 2 * b'testbytes'


class TestMemoryFS(object):
    def test_parent_of_top_node_is_node_itself(self, fs):
        assert fs.parent == fs

    def test_get_node_without_path(self, fs):
        assert fs == fs.get_node([])

    def test_get_subnodes(self, fs):
        fs1 = MemoryFS(fs)
        fs2 = MemoryFS(fs1)
        fs.children['1'] = fs1
        fs1.children['2'] = fs2
        assert fs2 == fs.get_node(['1', os.curdir, os.pardir, '1', '2'])

    def test_get_parent_node_of_parent_is_parent(self, fs):
        # This corresponds to Unix behavior
        assert fs.get_node([os.pardir]) == fs

    def test_get_non_existent_node(self, fs):
        with pytest.raises(KeyError):
            fs.get_node(['nonexistent'])

    def test_default_dir_mode(self, fs):
        fs.mkdir('dir')
        s = fs.stat('dir')
        assert stat.S_ISDIR(s.st_mode)
        assert stat.S_IMODE(s.st_mode) == (
            stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP |
            stat.S_IROTH | stat.S_IXOTH)

    def test_default_file_mode(self, fs):
        write_file(fs, 'file')
        s = fs.stat('file')
        assert stat.S_ISREG(s.st_mode)
        assert stat.S_IMODE(s.st_mode) == (
            stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP |
            stat.S_IROTH | stat.S_IWOTH)

    def test_chmod(self, fs):
        fs.mkdir('dir')
        s = stat.S_IRWXU
        fs.chmod('dir', s)
        assert fs.stat('dir').st_mode == s

    def test_respects_writable_mode_of_files(self, fs):
        fs = MemoryFS()
        write_file(fs, 'file', u'foo')
        fs.chmod('file', stat.S_IRUSR)
        assert_file_content_equal(fs, 'file', u'foo')
        assert_open_raises(fs, 'file', errno.EACCES, 'a')
        assert_open_raises(fs, 'file', errno.EACCES, 'w')

    def test_copy(self, fs):
        fs.mkdir('sub1')
        fs.mkdir('sub2')
        src = os.path.join('sub1', 'src')
        dest = os.path.join('sub2', 'dest')
        write_file(fs, src, u'dummy')
        fs.copy(src, dest)
        with fs.open(src, 'a+') as f:
            f.seek(0, os.SEEK_SET)
            assert f.read() == u'dummy'
            f.write(u' content')
        assert_file_content_equal(fs, dest, u'dummy')

    def test_exists(self, fs):
        fs.mkdir('dir')
        write_file(fs, 'file')

        assert fs.exists('dir')
        assert fs.exists('file')
        assert not fs.exists('missing')

    def test_mkdir(self, fs):
        fs.mkdir('test')
        fs.mkdir('test/subdir')
        assert 'test' in fs.children
        assert 'subdir' in fs.children['test'].children

    def test_mkdir_raises_exception_if_dir_exists(self, fs):
        fs.mkdir('dir')
        with pytest.raises(OSError) as excinfo:
            fs.mkdir('dir')
        assert excinfo.value.errno == errno.EEXIST
        assert excinfo.value.filename == 'dir'

    def test_makedirs(self, fs):
        fs.mkdir('existing')
        fs.makedirs(os.path.join('existing', 'test', 'subdir'))
        existing = fs.children['existing']
        assert 'test' in existing.children
        assert 'subdir' in existing.children['test'].children

    def test_makedirs_raises_exception_if_dir_exists(self, fs):
        path = os.path.join('one', 'two')
        fs.makedirs(path)
        with pytest.raises(OSError) as excinfo:
            fs.makedirs(path)
        assert excinfo.value.errno == errno.EEXIST
        assert excinfo.value.filename == path

    def test_rename(self, fs):
        src = os.path.join('sub1', 'original')
        fs.makedirs(src)
        fs.mkdir('sub2')
        instance = fs.children['sub1'].children['original']
        fs.rename(src, os.path.join('sub2', 'new'))
        assert 'original' not in fs.children['sub1'].children
        assert fs.children['sub2'].children['new'] is instance

    def test_rename_raises_exception_if_dest_exists(self, fs):
        fs.mkdir('src')
        fs.mkdir('dest')
        with pytest.raises(OSError) as excinfo:
            fs.rename('src', 'dest')
        assert excinfo.value.errno == errno.EEXIST
        assert excinfo.value.filename == 'dest'

    def test_symlink(self, fs):
        fs.mkdir('sub1')
        fs.mkdir('sub2')
        src = os.path.join('sub1', 'src')
        dest = os.path.join('sub2', 'dest')
        write_file(fs, src, u'dummy')
        fs.symlink(src, dest)
        with fs.open(dest, 'a+') as f:
            f.seek(0, os.SEEK_SET)
            assert f.read() == u'dummy'
            f.write(u' content')
        assert_file_content_equal(fs, src, u'dummy content')

    def test_symlink_raises_error_if_file_exists(self, fs):
        fs.mkdir('sub1')
        fs.mkdir('sub2')
        src = os.path.join('sub1', 'src')
        dest = os.path.join('sub2', 'dest')
        write_file(fs, src, u'dummy')
        write_file(fs, dest, u'dummy2')
        with pytest.raises(OSError) as excinfo:
            fs.symlink(src, dest)
        assert excinfo.value.errno == errno.EEXIST
        assert excinfo.value.filename == dest

    @pytest.mark.parametrize('mode', ['w', 'w+', 'a', 'a+'])
    def test_allows_writing_of_files(self, mode, fs):
        with fs.open('filename', mode) as f:
            f.write(u'dummy content')
        assert fs.children['filename'].content == b'dummy content'

    @pytest.mark.parametrize('mode', ['a', 'a+'])
    def test_allows_appending_to_files(self, mode, fs):
        write_file(fs, 'filename', u'dummy ')
        with fs.open('filename', mode) as f:
            f.write(u'content')
        assert fs.children['filename'].content == b'dummy content'

    @pytest.mark.parametrize('mode', ['w', 'w+'])
    def test_allows_overwriting_of_files(self, mode, fs):
        write_file(fs, 'filename', u'dummy')
        with fs.open('filename', mode) as f:
            f.write(u'content')
        assert fs.children['filename'].content == b'content'

    @pytest.mark.parametrize('mode', ['r', 'r+'])
    def test_allows_reading_of_files(self, mode, fs):
        write_file(fs, 'filename', u'dummy content')
        with fs.open('filename', mode) as f:
            data = f.read()
        assert data == u'dummy content'

    def test_rmdir(self, fs):
        fs.mkdir('dir')
        fs.rmdir('dir')
        assert not fs.exists('dir')

        fs.mkdir('dirx')
        write_file(fs, os.path.join('dirx', 'filename'), u'content')
        with pytest.raises(OSError) as excinfo:
            fs.rmdir('dirx')
        assert excinfo.value.errno == errno.ENOTEMPTY

    def test_samefile(self, fs):
        write_file(fs, 'file1', u'file1')
        write_file(fs, 'file2', u'file2')
        fs.symlink('file1', 'file1b')
        assert fs.samefile('file1', 'file1b')
        assert not fs.samefile('file1', 'file2')

    def test_unlink(self, fs):
        write_file(fs, 'file')
        fs.unlink('file')
        assert_open_raises(fs, 'file', errno.ENOENT)

    def test_walk(self, fs):
        fs = MemoryFS()
        write_file(fs, 'file')
        fs.mkdir('dir')
        write_file(fs, 'dir/file2')
        native_dir_path = os.path.join(os.curdir, 'dir')
        assert [item for item in fs.walk('.')] == [
            ('.', ['dir'], ['file']), (native_dir_path, [], ['file2'])]

    def test_bottomup_walk(self, fs):
        fs = MemoryFS()
        write_file(fs, 'file')
        fs.mkdir('dir')
        write_file(fs, 'dir/file2')
        native_dir_path = os.path.join(os.curdir, 'dir')
        assert [item for item in fs.walk('.', topdown=False)] == [
            (native_dir_path, [], ['file2']), ('.', ['dir'], ['file'])]

    def test_utime(self, fs):
        write_file(fs, 'file')
        fs.utime('file', (1.1, 2.2))
        st = fs.stat('file')
        assert st.st_atime == 1.1
        assert st.st_mtime == 2.2
