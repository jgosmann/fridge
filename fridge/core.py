import ast
import os.path
import re
import stat
import time

from fridge.cas import ContentAddressableStorage
import fridge.fs


class DataObject(object):
    __slots__ = []

    def __init__(self, *args, **kwargs):
        if len(args) > len(self.__slots__):
            raise TypeError("Takes {} arguments, but got {}.".format(
                len(self.__slots__), len(args)))

        for i, name in enumerate(self.__slots__):
            if i < len(args):
                if name in kwargs:
                    raise TypeError("Multiple arguments for {}.".format(name))
                setattr(self, name, args[i])
            else:
                if name not in kwargs:
                    raise TypeError("Argument {} missing.".format(name))
                setattr(self, name, kwargs.pop(name))

        if len(kwargs) > 0:
            raise TypeError("Unknown keyword argument {}.", kwargs.keys()[0])

    def __eq__(self, other):
        if hasattr(other, '__slots__') and self.__slots__ != other.__slots__:
            return False

        for name in self.__slots__:
            try:
                if getattr(self, name) != getattr(other, name):
                    return False
            except AttributeError:
                return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return '{cls}({args})'.format(
            cls=self.__class__.__name__,
            args=', '.join('{name}={value!r}'.format(
                name=n, value=getattr(self, n)) for n in self.__slots__))


class Serializable(object):
    class DeserializationError(RuntimeError):
        pass

    @classmethod
    def parse(cls, serialized):
        raise NotImplementedError()

    def serialize(self):
        raise NotImplementedError()


class Stat(DataObject):
    __slots__ = ['st_mode', 'st_size', 'st_atime', 'st_mtime']


class SnapshotItem(DataObject, Serializable):
    __slots__ = ['checksum', 'path', 'status']

    _SPLIT_REGEX = re.compile(r'\s+')

    @classmethod
    def parse(cls, serialized):
        key, mode, size, atime, mtime, path_repr = cls._SPLIT_REGEX.split(
            serialized, 5)
        status = Stat(
            st_mode=int(mode, 8) | stat.S_IFREG,
            st_size=int(size), st_atime=float(atime), st_mtime=float(mtime))
        return cls(key, ast.literal_eval(path_repr), status)

    def serialize(self):
        # pylint: disable=no-member
        return ('{key:s} {mode:0>4o} {size:d} {atime:.3f} {mtime:.3f} ' +
                '{path!r}').format(
            key=self.checksum,
            mode=stat.S_IMODE(self.status.st_mode),
            size=self.status.st_size,
            atime=self.status.st_atime,
            mtime=self.status.st_mtime,
            path=self.path)


class Commit(DataObject, Serializable):
    __slots__ = ['timestamp', 'snapshot', 'message', 'parent']

    _NEWLINE_REGEX = re.compile(r'\r*\n\r*')
    _SPLIT_MESSAGE_REGEX = re.compile('(?:{}){{2}}'.format(
        _NEWLINE_REGEX.pattern))
    _SPLIT_REGEX = re.compile(r'\s+')

    @classmethod
    def parse(cls, serialized):
        serialized, message = cls._SPLIT_MESSAGE_REGEX.split(serialized, 1)
        lines = cls._NEWLINE_REGEX.split(serialized)
        kwargs = {'message': message}
        for line in lines:
            split = cls._SPLIT_REGEX.split(line.strip(), 1)
            if len(split) > 1:
                kw, value = split
            else:
                kw = split[0]
                value = None
            if kw in kwargs:
                raise cls.DeserializationError("Duplicate key.")
            if kw == 'timestamp':
                value = float(value)
            kwargs[kw] = value
        try:
            return cls(**kwargs)
        except TypeError as err:
            raise cls.DeserializationError(err.message)

    def serialize(self):
        # pylint: disable=no-member
        return (
            'timestamp {timestamp:.3f}\nparent {parent}\n' +
            'snapshot {snapshot}\n\n{message}').format(
                timestamp=self.timestamp, parent=self.parent or '',
                snapshot=self.snapshot, message=self.message)


class FridgeCore(object):
    def __init__(
            self, path, fs=fridge.fs, cas_factory=ContentAddressableStorage):
        self._path = path
        self._fs = fs
        self._blobs = cas_factory(os.path.join(path, '.fridge', 'blobs'), fs)
        self._snapshots = cas_factory(os.path.join(
            path, '.fridge', 'snapshots'), fs)
        self._commits = cas_factory(os.path.join(
            path, '.fridge', 'commits'), fs)

    @classmethod
    def init(cls, path, fs=fridge.fs, cas_factory=ContentAddressableStorage):
        fs.mkdir(os.path.join(path, '.fridge'))
        with fs.open(os.path.join(path, '.fridge', 'head'), 'w'):
            pass
        return cls(path, fs, cas_factory)

    def add_blob(self, path):
        key = self._blobs.store(path)
        return key

    @staticmethod
    def serialize_snapshot(snapshot):
        return u'\n'.join(item.serialize() for item in snapshot)

    def add_snapshot(self, snapshot):
        tmp_file = os.path.join(self._path, '.fridge', 'tmp')
        with self._fs.open(tmp_file, 'w') as f:
            f.write(self.serialize_snapshot(snapshot))
        return self._snapshots.store(tmp_file)

    def add_commit(self, snapshot_key, message):
        # FIXME ensure UTC time
        c = Commit(time.time(), snapshot_key, message, self.get_head())
        tmp_file = os.path.join(self._path, '.fridge', 'tmp')
        with self._fs.open(tmp_file, 'w') as f:
            f.write(c.serialize())
        return self._commits.store(tmp_file)

    @staticmethod
    def parse_snapshot(serialized_snapshot):
        return [SnapshotItem.parse(line)
                for line in serialized_snapshot.split('\n')]

    def read_snapshot(self, key):
        with self._fs.open(self._snapshots.get_path(key)) as f:
            return self.parse_snapshot(f.read())

    def read_commit(self, key):
        with self._fs.open(self._commits.get_path(key)) as f:
            return Commit.parse(f.read())

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

    def commit(self, message=""):
        snapshot = []
        for dirpath, dirnames, filenames in self._fs.walk('.'):
            if '.fridge' in dirnames:
                dirnames.remove('.fridge')
            for filename in filenames:
                path = os.path.join(dirpath, filename)
                checksum = self._core.add_blob(path)
                snapshot.append(SnapshotItem(
                    checksum, path, self._fs.stat(path)))
        snapshot_hash = self._core.add_snapshot(snapshot)
        commit_hash = self._core.add_commit(snapshot_hash, message)
        self._core.set_head(commit_hash)
        self.checkout()

    def checkout(self):
        head = self._core.get_head()
        commit = self._core.read_commit(head)
        snapshot = self._core.read_snapshot(commit.snapshot)
        for item in snapshot:
            self._core.checkout_blob(item.checksum, item.path)
            self._fs.chmod(item.path, stat.S_IMODE(item.status.st_mode))
            # FIXME ensure UTC
            self._fs.utime(
                item.path, (item.status.st_atime, item.status.st_mtime))

    def log(self):
        head = self._core.get_head()
        commits = [(head, self._core.read_commit(head))]
        while commits[-1][1].parent is not None:
            key = commits[-1][1].parent
            commits.append((key, self._core.read_commit(key)))
        return commits
