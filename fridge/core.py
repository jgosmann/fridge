import ast
import errno
import os.path
import re
import stat

from fridge.cas import ContentAddressableStorage
import fridge.fs
from fridge.time import utc2timestamp, timestamp2utc, utc_time


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
            st_size=int(size), st_atime=utc2timestamp(float(atime)),
            st_mtime=utc2timestamp(float(mtime)))
        return cls(key, ast.literal_eval(path_repr), status)

    def serialize(self):
        # pylint: disable=no-member
        return ('{key:s} {mode:0>4o} {size:d} {atime:.3f} {mtime:.3f} ' +
                '{path!r}').format(
                    key=self.checksum,
                    mode=stat.S_IMODE(self.status.st_mode),
                    size=self.status.st_size,
                    atime=timestamp2utc(self.status.st_atime),
                    mtime=timestamp2utc(self.status.st_mtime),
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
            u'timestamp {timestamp:.3f}\nparent {parent}\n' +
            u'snapshot {snapshot}\n\n{message}').format(
                timestamp=self.timestamp, parent=self.parent or '',
                snapshot=self.snapshot, message=self.message)


class Branch(DataObject, Serializable):
    __slots__ = ['commit']

    @classmethod
    def parse(cls, serialized):
        return cls(commit=serialized)

    def serialize(self):
        # pylint: disable=no-member
        return u'{c}'.format(c=self.commit)


class Reference(DataObject, Serializable):
    __slots__ = ['type', 'ref']

    COMMIT = u'commit'
    BRANCH = u'branch'

    @classmethod
    def parse(cls, serialized):
        tp, ref = [s.strip() for s in serialized.split(':')]
        return cls(type=tp, ref=ref)

    def serialize(self):
        # pylint: disable=no-member
        return u'{t}: {r}'.format(t=self.type, r=self.ref)


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
        self._branch_dir = os.path.join(self._path, '.fridge', 'branches')

    @classmethod
    def init(cls, path, fs=fridge.fs, cas_factory=ContentAddressableStorage):
        fs.mkdir(os.path.join(path, '.fridge'))
        obj = cls(path, fs, cas_factory)
        obj.set_branch(u'master', '')
        obj.set_head(Reference(Reference.BRANCH, u'master'))
        return obj

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
        # pylint: disable=no-member
        commit = self.resolve_ref(self.get_head())
        c = Commit(utc_time(), snapshot_key, message, commit)
        tmp_file = os.path.join(self._path, '.fridge', 'tmp')
        with self._fs.open(tmp_file, 'w') as f:
            f.write(c.serialize())
        return self._commits.store(tmp_file)

    def is_commit(self, key):
        return self._fs.exists(self._commits.get_path(key))

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

    def set_head(self, head):
        path = os.path.join(self._path, '.fridge', 'head')
        with self._fs.open(path, 'w') as f:
            f.write(head.serialize())

    def get_head(self):
        path = os.path.join(self._path, '.fridge', 'head')
        with self._fs.open(path, 'r') as f:
            return Reference.parse(f.read())

    def get_head_key(self):
        return self.resolve_ref(self.get_head())

    def set_branch(self, name, commit):
        try:
            self._fs.makedirs(self._branch_dir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
        path = os.path.join(self._branch_dir, name)
        with self._fs.open(path, 'w') as f:
            f.write(Branch(commit).serialize())

    def is_branch(self, name):
        branch_path = os.path.join(self._branch_dir, name)
        return self._fs.exists(branch_path)

    def resolve_branch(self, name):
        branch_path = os.path.join(self._branch_dir, name)
        with self._fs.open(branch_path, 'r') as f:
            # pylint: disable=no-member
            return Branch.parse(f.read()).commit

    def resolve_ref(self, ref):
        if ref.type == Reference.COMMIT:
            return ref.ref
        elif ref.type == Reference.BRANCH:
            return self.resolve_branch(ref.ref)

    def checkout_blob(self, key, path):
        source_path = self._blobs.get_path(key)
        self._fs.copy(source_path, path)


class Fridge(object):
    def __init__(self, fridge_core, fs=fridge.fs):
        self._core = fridge_core
        self._fs = fs

    def refparse(self, ref):
        potential_types = []
        if self._core.is_branch(ref):
            potential_types.append(Reference.BRANCH)
        if self._core.is_commit(ref):
            potential_types.append(Reference.COMMIT)

        if len(potential_types) < 1:
            raise UnknownReferenceError()
        elif len(potential_types) > 1:
            raise AmbiguousReferenceError()
        else:
            return Reference(potential_types[0], ref)

    def commit(self, message=""):
        snapshot = []
        for dirpath, dirnames, filenames in self._fs.walk('.'):
            if '.fridge' in dirnames:
                dirnames.remove('.fridge')
            for filename in filenames:
                path = os.path.join(dirpath, filename)
                stat = self._fs.stat(path)
                checksum = self._core.add_blob(path)
                snapshot.append(SnapshotItem(checksum, path, stat))
        snapshot_hash = self._core.add_snapshot(snapshot)
        commit_hash = self._core.add_commit(snapshot_hash, message)

        head = self._core.get_head()
        if head.type == Reference.COMMIT:
            head.ref = commit_hash
            self._core.set_head(head)
        elif head.type == Reference.BRANCH:
            self._core.set_branch(head.ref, commit_hash)
        else:
            raise AssertionError("Invalid head type '{t}'.".format(
                t=head.type))

        self.checkout()

    def branch(self, name):
        if self._core.is_branch(name):
            raise BranchExistsError()
        self._core.set_branch(name, self._core.get_head_key())
        self._core.set_head(Reference(Reference.BRANCH, name))

    def checkout(self, ref=None):
        head_key = self._core.get_head_key()
        if ref is None:
            key = head_key
        else:
            ref = self.refparse(ref)
            self._core.set_head(ref)
            key = self._core.resolve_ref(ref)

        commit = self._core.read_commit(key)
        head_commit = self._core.read_commit(head_key)

        snapshot = self._core.read_snapshot(commit.snapshot)
        head_snapshot = self._core.read_snapshot(head_commit.snapshot)

        # FIXME do not delete or overwrite non-restorable files
        for item in head_snapshot:
            try:
                self._fs.unlink(item.path)
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise

        for item in snapshot:
            self._core.checkout_blob(item.checksum, item.path)
            self._fs.chmod(item.path, stat.S_IMODE(item.status.st_mode))
            self._fs.utime(
                item.path, (item.status.st_atime, item.status.st_mtime))

    def log(self):
        head = self._core.get_head_key()
        commits = [(head, self._core.read_commit(head))]
        while commits[-1][1].parent is not None:
            key = commits[-1][1].parent
            commits.append((key, self._core.read_commit(key)))
        return commits


class FridgeError(RuntimeError):
    pass


class FridgeReferenceError(FridgeError):
    pass


class AmbiguousReferenceError(FridgeReferenceError):
    pass


class BranchExistsError(FridgeError):
    pass


class UnknownReferenceError(FridgeReferenceError):
    pass
