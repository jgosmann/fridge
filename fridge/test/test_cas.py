import pytest

from fridge.cas import ContentAddressableStorage
from fridge.fstest import (
    assert_file_content_equal, assert_open_raises, write_file)
from fridge.memoryfs import MemoryFS


@pytest.fixture
def fs():
    return MemoryFS()


@pytest.fixture
def cas(fs):
    return ContentAddressableStorage('cas', fs)


class TestContentAddressableStorage(object):
    def has_root_property(self, fs):
        cas = ContentAddressableStorage(root='cas_root', fs=fs)
        assert cas.root == 'cas_root'

    def test_allows_to_store_and_retrieve_files(self, fs):
        write_file(fs, 'testfile', u'dummy content')
        cas = ContentAddressableStorage('cas', fs=fs)
        key = cas.store('testfile')
        # Close and reopen
        del cas
        cas = ContentAddressableStorage('cas', fs=fs)
        with fs.open(cas.get_path(key), 'r') as f:
            content = f.read()
        assert content == u'dummy content'

    def test_allows_to_store_files_with_identical_content(self, fs, cas):
        write_file(fs, 'file1', u'content')
        write_file(fs, 'file2', u'content')
        key1 = cas.store('file1')
        key2 = cas.store('file2')
        assert key1 == key2

    def test_file_removed_after_store(self, fs, cas):
        with fs.open('testfile', 'w') as f:
            f.write(u'dummy content')
        cas.store('testfile')
        assert not fs.exists('testfile')

    def test_writing_original_files_keeps_stored_file_unchanged(self, fs):
        write_file(fs, 'testfile', u'dummy content')

        cas = ContentAddressableStorage('cas', fs=fs)
        key = cas.store('testfile')
        del cas  # Close

        write_file(fs, 'testfile', u'replaced content')
        cas = ContentAddressableStorage('cas', fs=fs)
        assert_file_content_equal(fs, cas.get_path(key), u'dummy content')
