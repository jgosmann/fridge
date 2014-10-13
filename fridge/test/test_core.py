import os.path
import stat

from mock import MagicMock
import pytest

from fridge.memoryfs import MemoryFS
from fridge.core import (
    DataObject, Commit, Fridge, FridgeCore, SnapshotItem, Stat)


class CasMockFactory(object):
    def __init__(self):
        self._cas = {}

    def __call__(self, path, fs):
        path = os.path.relpath(path, '.fridge')
        if path not in self._cas:
            self._cas[path] = MagicMock()
        return self._cas[path]

    def __getitem__(self, key):
        return self._cas[key]


def create_file_status():
    return Stat(
        st_mode=(
            stat.S_IFREG |
            stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP |
            stat.S_IROTH | stat.S_IWOTH),
        st_size=123, st_atime=4.56, st_mtime=7.89)


@pytest.fixture
def cas_factory():
    return CasMockFactory()


@pytest.fixture
def fs():
    return MemoryFS()


@pytest.fixture
def fridge_core(fs, cas_factory):
    return FridgeCore.init(os.curdir, fs, cas_factory)


class TestDataObject(object):
    # pylint: disable=no-member

    class A(DataObject):
        __slots__ = ['a', 'b']

    class LikeA(DataObject):
        __slots__ = ['a', 'b']

    class B(DataObject):
        __slots__ = 'b'

    def test_raises_on_too_many_args(self):
        with pytest.raises(TypeError):
            self.A(1, 2, 3)

    def test_raises_on_too_few_args(self):
        with pytest.raises(TypeError):
            self.A(1)

    def test_accepts_positional_args(self):
        a = self.A(1, 2)
        assert a.a == 1 and a.b == 2

    def test_raises_on_wrong_keyword_arg(self):
        with pytest.raises(TypeError):
            self.A(1, 2, z=3)
        with pytest.raises(TypeError):
            self.A(1, z=3)

    def test_raises_on_duplicate_arg(self):
        with pytest.raises(TypeError):
            self.A(1, 2, a=1)
        with pytest.raises(TypeError):
            self.A(1, a=1)

    def test_accepts_keyword_args(self):
        a = self.A(b=1, a=2)
        assert a.b == 1 and a.a == 2

    def test_accepts_mixed_args(self):
        a = self.A(1, b=2)
        assert a.a == 1 and a.b == 2

    def test_equality(self):
        a1 = self.A(1, 2)
        a2 = self.A(1, 2)
        a3 = self.LikeA(1, 2)
        different = self.B(2)
        different2 = self.A(2, 2)

        assert a1 == a1
        assert a1 == a2 and a2 == a1
        assert a1 == a3 and a3 == a1
        assert a1 != different and different != a1
        assert a1 != different2 and different2 != a1


def test_snapshot_item_serialization_roundtrip():
    path = '  some \n /weird \t path '
    status = create_file_status()
    a = SnapshotItem('key', path, status)
    ser = a.serialize()
    b = SnapshotItem.parse(ser)
    assert a == b


def test_commit_serialization_roundtrip():
    a = Commit(123.45, 'snapshot', 'message', None)
    ser = a.serialize()
    b = Commit.parse(ser)
    assert a == b


class TestFridgeCore(object):
    def _create_snapshot(self):
        return [
            SnapshotItem(
                checksum='a1b2', path='a', status=create_file_status()),
            SnapshotItem(
                checksum='cd34', path='b', status=create_file_status())
        ]

    def test_snapshot_roundtrip(self):
        snapshot = [
            SnapshotItem('key1', ' \n\t/weird path \n', create_file_status()),
            SnapshotItem('key2', '\n another path', create_file_status())]
        serialized = FridgeCore.serialize_snapshot(snapshot)
        parsed = FridgeCore.parse_snapshot(serialized)
        assert snapshot == parsed

    def test_add_blob(self, cas_factory, fridge_core):
        fridge_core.add_blob('path')
        cas_factory['blobs'].store.assert_called_once_with('path')

    def test_writing_and_reading_snapshot(self, fs):
        s = self._create_snapshot()

        fridge = FridgeCore.init(os.curdir, fs)
        key = fridge.add_snapshot(s)
        del fridge

        fridge = FridgeCore(os.curdir, fs)
        assert s == fridge.read_snapshot(key)

    def test_writing_two_snapshots(self, fs):
        s1 = self._create_snapshot()
        s2 = [SnapshotItem('key', 'xyz', create_file_status())]

        fridge = FridgeCore.init(os.curdir, fs)
        key1 = fridge.add_snapshot(s1)
        key2 = fridge.add_snapshot(s2)
        assert s1 == fridge.read_snapshot(key1)
        assert s2 == fridge.read_snapshot(key2)

    def test_setting_and_getting_head(self, fs):
        fridge = FridgeCore.init(os.curdir, fs)
        fridge.set_head(u'ab12cd')
        del fridge

        fridge = FridgeCore(os.curdir, fs)
        assert fridge.get_head() == u'ab12cd'

    def test_checkout_blob(self, fs, cas_factory, fridge_core):
        with fs.open('mockfile', 'w') as f:
            f.write(u'content')
        cas_factory['blobs'].get_path.return_value = 'mockfile'
        fridge_core.checkout_blob('key', 'target')
        assert fs.get_node(
            ['mockfile']).content == fs.get_node(['target']).content

    def test_checkout_blob_on_checkedout(self, fs, cas_factory, fridge_core):
        with fs.open('mockfile', 'w') as f:
            f.write(u'content')
        fs.symlink('mockfile', 'target')
        cas_factory['blobs'].get_path.return_value = 'mockfile'
        fridge_core.checkout_blob('key', 'target')
        assert fs.get_node(
            ['mockfile']).content == fs.get_node(['target']).content


class TestFridge(object):
    def test_commit(self, fs):
        with fs.open('mockfile', 'w') as f:
            f.write(u'content')
        core_mock = MagicMock()
        core_mock.add_blob.return_value = 'hash'
        core_mock.add_snapshot.return_value = 'snapshot_hash'
        core_mock.add_commit.return_value = 'commit_hash'
        fridge = Fridge(core_mock, fs)
        fridge.commit(message='msg')

        call_path = os.path.join(os.curdir, 'mockfile')
        core_mock.add_blob.assert_called_once_with(call_path)
        core_mock.add_snapshot.assert_called_once_with([SnapshotItem(
            'hash', call_path, fs.stat('mockfile'))])
        core_mock.add_commit.assert_called_once_with(
            'snapshot_hash', 'msg')
        core_mock.set_head.assert_called_once('commit_hash')

    def test_checkout(self):
        fs = MagicMock()
        core_mock = MagicMock()
        core_mock.get_head.return_value = 'headhash'
        core_mock.read_commit.return_value = Commit(
            timestamp=1.23, snapshot='snapshot_hash', message='msg',
            parent=None)
        status = create_file_status()
        core_mock.read_snapshot.return_value = [
            SnapshotItem('hash', 'file', status)]

        fridge = Fridge(core_mock, fs)
        fridge.checkout()

        # pylint: disable=no-member
        core_mock.get_head.assert_called_once_with()
        core_mock.read_commit.assert_called_once_with('headhash')
        core_mock.read_snapshot.assert_called_once_with('snapshot_hash')
        core_mock.checkout_blob.assert_called_once_with('hash', 'file')
        fs.chmod.assert_called_once_with('file', stat.S_IMODE(status.st_mode))
        fs.utime.assert_called_once_with(
            'file', (status.st_atime, status.st_mtime))
