import ast
import errno
import os.path

from fridge.cas import ContentAddressableStorage
import fridge.fs


class SnapshotItem(object):
    __slots__ = ['checksum', 'path']

    def __init__(self, checksum, path):
        self.checksum = checksum
        self.path = path

    def __eq__(self, other):
        return self.checksum == other.checksum and self.path == other.path

    def __repr__(self):
        return 'SnapshotItem(checksum={checksum}, path={path})'.format(
            checksum=repr(self.checksum), path=repr(self.path))

    @classmethod
    def parse(cls, serialized):
        # The splitting could be more robust. But the data should have been
        # written by this program in the correct format anyways. Thus, using
        # just a space for splitting is good for now.
        key, path_repr = serialized.split(' ', 1)
        return cls(key, ast.literal_eval(path_repr))

    def serialize(self):
        return self.checksum + ' ' + repr(self.path)


class FridgeCore(object):
    def __init__(
            self, path, fs=fridge.fs, cas_factory=ContentAddressableStorage):
        self._path = path
        self._fs = fs
        self._blobs = cas_factory(os.path.join(path, '.fridge', 'blobs'), fs)
        self._snapshots = cas_factory(os.path.join(
            path, '.fridge', 'snapshots'), fs)

    @classmethod
    def init(cls, path, fs=fridge.fs, cas_factory=ContentAddressableStorage):
        fs.mkdir(os.path.join(path, '.fridge'))
        return cls(path, fs, cas_factory)

    def add_blob(self, path):
        return self._blobs.store(path)

    def add_snapshot(self, snapshot):
        data = u'\n'.join(item.serialize() for item in snapshot)
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

    def checkout_blob(self, key, path):
        source_path = self._blobs.get_path(key)
        try:
            self._fs.symlink(source_path, path)
        except OSError as err:
            is_checked_out = err.errno == errno.EEXIST and \
                self._fs.samefile(source_path, path)
            if is_checked_out:
                pass
            else:
                raise
