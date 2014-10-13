import ast
from collections import namedtuple
import os.path
import re
import stat

from fridge.cas import ContentAddressableStorage
import fridge.fs


class SnapshotItem(object):
    __slots__ = ['checksum', 'path', 'status']

    _SPLIT_REGEX = re.compile(r'\s+')
    RestoredStat = namedtuple(
        'RestoredStat', ['st_mode', 'st_size', 'st_atime', 'st_mtime'])

    def __init__(self, checksum, path, status):
        self.checksum = checksum
        self.path = path
        self.status = status

    def __eq__(self, other):
        return self.checksum == other.checksum and self.path == other.path

    def __repr__(self):
        return 'SnapshotItem(checksum={checksum}, path={path})'.format(
            checksum=repr(self.checksum), path=repr(self.path))

    @classmethod
    def parse(cls, serialized):
        key, mode, size, atime, mtime, path_repr = cls._SPLIT_REGEX.split(
            serialized, 5)
        status = cls.RestoredStat(
            st_mode=int(mode, 8) | stat.S_IFREG,
            st_size=int(size), st_atime=float(atime), st_mtime=float(mtime))
        return cls(key, ast.literal_eval(path_repr), status)

    def serialize(self):
        return ('{key:s} {mode:0>4o} {size:d} {atime:.3f} {mtime:.3f} ' +
                '{path!r}').format(
            key=self.checksum,
            mode=stat.S_IMODE(self.status.st_mode),
            size=self.status.st_size,
            atime=self.status.st_atime,
            mtime=self.status.st_mtime,
            path=self.path)


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

    @staticmethod
    def serialize_snapshot(snapshot):
        return u'\n'.join(item.serialize() for item in snapshot)

    def add_snapshot(self, snapshot):
        tmp_file = os.path.join(self._path, '.fridge', 'tmp')
        with self._fs.open(tmp_file, 'w') as f:
            f.write(self.serialize_snapshot(snapshot))
        try:
            return self._snapshots.store(tmp_file)
        finally:
            self._fs.unlink(tmp_file)

    @staticmethod
    def parse_snapshot(serialized_snapshot):
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
        self._fs.copy(source_path, path)


class Fridge(object):
    def __init__(self, fridge_core, fs=fridge.fs):
        self._core = fridge_core
        self._fs = fs

    def commit(self):
        snapshot = []
        for dirpath, dirnames, filenames in self._fs.walk('.'):
            if '.fridge' in dirnames:
                dirnames.remove('.fridge')
            for filename in filenames:
                path = os.path.join(dirpath, filename)
                checksum = self._core.add_blob(path)
                snapshot.append(SnapshotItem(
                    checksum, path, self._fs.stat(path)))
        checksum = self._core.add_snapshot(snapshot)
        self._core.set_head(checksum)

    def checkout(self):
        head = self._core.get_head()
        snapshot = self._core.read_snapshot(head)
        for item in snapshot:
            self._core.checkout_blob(item.checksum, item.path)
            self._fs.chmod(item.path, stat.S_IMODE(item.status.st_mode))
            self._fs.utime(
                item.path, (item.status.st_atime, item.status.st_mtime))
