import os.path

from fridge.cas import ContentAddressableStorage


class SnapshotItem(object):
    __slots__ = ['checksum', 'path']

    def __init__(self, checksum, path):
        self.checksum = checksum
        self.path = path

    def __eq__(self, other):
        return self.checksum == other.checksum and self.path == other.path

    # TODO test
    @classmethod
    def parse(cls, serialized):
        # FIXME more robust splitting?
        return cls(*serialized.strip().split(' '))


class FridgeCore(object):
    def __init__(self, path, fs, cas_factory=ContentAddressableStorage):
        self._path = path
        self._fs = fs
        self._blobs = cas_factory(os.path.join(path, '.fridge', 'blobs'), fs)
        self._snapshots = cas_factory(os.path.join(
            path, '.fridge', 'snapshots'), fs)

    @classmethod
    def init(cls, path, fs, cas_factory=ContentAddressableStorage):
        fs.mkdir(os.path.join(path, '.fridge'))
        return cls(path, fs, cas_factory)

    def add_blob(self, path):
        self._blobs.store(path)

    def add_snapshot(self, snapshot):
        data = '\n'.join(
            '{} {}'.format(item.checksum, item.path) for item in snapshot)
        tmp_file = os.path.join(self._path, '.fridge', 'tmp')
        with self._fs.open(tmp_file, 'w') as f:
            f.write(data)
        return self._snapshots.store(tmp_file)

    # TODO test this function
    def parse_snapshot(self, serialized_snapshot):
        return [SnapshotItem.parse(line)
                for line in serialized_snapshot.split('\n')]

    def read_snapshot(self, key):
        with self._fs.open(self._snapshots.get_path(key)) as f:
            return self.parse_snapshot(f.read())

    def set_head(self, key):
        path = os.path.join(self._path, '.fridge', 'head')
        with self._fs.open(path, 'w') as f:
            f.write(key)

    def get_head(self):
        path = os.path.join(self._path, '.fridge', 'head')
        with self._fs.open(path, 'r') as f:
            return f.read()
