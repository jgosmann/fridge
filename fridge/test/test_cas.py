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
            f.write('dummy content')
        key = cas.store('testfile')
        # Close and reopen
        del cas
        cas = self.create_cas(fs)
        with fs.open(cas.get_path(key), 'r') as f:
            content = f.read()
        assert content == 'dummy content'

    # TODO test write protection
    # TODO do symlinking (test whether file can still be accessed)
