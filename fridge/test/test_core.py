import os.path
import stat

from mock import MagicMock
import pytest

from fridge.memoryfs import MemoryFS
from fridge.core import Fridge, FridgeCore, SnapshotItem


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
    status = MagicMock()
    status.st_mode = (
        stat.S_IFREG |
        stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP |
        stat.S_IROTH | stat.S_IWOTH)
    status.st_size = 123
    status.st_atime = 4.56
    status.st_mtime = 7.89
    return status


@pytest.fixture
def cas_factory():
    return CasMockFactory()


@pytest.fixture
def fs():
    return MemoryFS()


@pytest.fixture
def fridge_core(fs, cas_factory):
    return FridgeCore.init(os.curdir, fs, cas_factory)


def test_snapshot_item_serialization_roundtrip():
    path = '  some \n /weird \t path '
    status = create_file_status()
    a = SnapshotItem('key', path, status)
    ser = a.serialize()
    b = SnapshotItem.parse(ser)
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
        core_mock.add_snapshot.return_value = 'hash2'
        fridge = Fridge(core_mock, fs)
        fridge.commit()

        core_mock.add_blob.assert_called_once_with('./mockfile')
        core_mock.add_snapshot.assert_called_once_with([SnapshotItem(
            'hash', './mockfile', fs.stat('mockfile'))])
        core_mock.set_head.assert_called_once('hash2')

    def test_checkout(self):
        fs = MagicMock()
        core_mock = MagicMock()
        core_mock.get_head.return_value = 'headhash'
        status = create_file_status()
        core_mock.read_snapshot.return_value = [
            SnapshotItem('hash', 'file', status)]

        fridge = Fridge(core_mock, fs)
        fridge.checkout()

        core_mock.get_head.assert_called_once_with()
        core_mock.read_snapshot.assert_called_once_with('headhash')
        core_mock.checkout_blob.assert_called_once_with('hash', 'file')
        fs.chmod.assert_called_once_with('file', stat.S_IMODE(status.st_mode))
        fs.utime.assert_called_once_with(
            'file', (status.st_atime, status.st_mtime))
