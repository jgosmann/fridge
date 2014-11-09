import pytest

from fridge.cas import ContentAddressableStorage
from fridge.memoryfs import MemoryFS


class TestContentAddressableStorage(object):
    def create_cas(self, fs=None, path='cas'):
        if fs is None:
            fs = MemoryFS()
        return ContentAddressableStorage(path, fs)

    def has_root_property(self):
        cas = self.create_cas(path='cas_root')
        assert cas.root == 'cas_root'

    def test_allows_to_store_and_retrieve_files(self):
        fs = MemoryFS()
        cas = self.create_cas(fs)
        with fs.open('testfile', 'w') as f:
            f.write(u'dummy content')
        key = cas.store('testfile')
        # Close and reopen
        del cas
        cas = self.create_cas(fs)
        with fs.open(cas.get_path(key), 'r') as f:
            content = f.read()
        assert content == u'dummy content'

    def test_file_removed_after_store(self):
        fs = MemoryFS()
        cas = self.create_cas(fs)
        with fs.open('testfile', 'w') as f:
            f.write(u'dummy content')
        cas.store('testfile')
        assert not fs.exists('testfile')

    def test_writing_original_files_keeps_stored_file_unchanged(self):
        fs = MemoryFS()
        cas = self.create_cas(fs)
        with fs.open('testfile', 'w') as f:
            f.write(u'dummy content')
        key = cas.store('testfile')
        del cas  # Close

        with fs.open('testfile', 'w') as f:
            f.write(u'replaced content')
        cas = self.create_cas(fs)
        with fs.open(cas.get_path(key), 'r') as f:
            content = f.read()
        assert content == u'dummy content'

    def test_stores_blobs_write_protected(self):
        fs = MemoryFS()
        cas = self.create_cas(fs)
        with fs.open('testfile', 'w') as f:
            f.write(u'dummy content')
        key = cas.store('testfile')

        with pytest.raises(OSError):
            with fs.open(cas.get_path(key), 'w'):
                pass
