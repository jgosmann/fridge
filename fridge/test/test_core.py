import errno
import os.path

from mock import MagicMock
import pytest

from fridge.memoryfs import MemoryFS
from fridge.core import FridgeCore, SnapshotItem


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


@pytest.fixture
def cas_factory():
    return CasMockFactory()


@pytest.fixture
def fs():
    return MemoryFS()


@pytest.fixture
def fridge(fs, cas_factory):
    return FridgeCore.init(os.curdir, fs, cas_factory)


def test_snapshot_item_serialization_roundtrip():
    path = '  some \n /weird \t path '
    a = SnapshotItem('key', path)
    ser = a.serialize()
    b = SnapshotItem.parse(ser)
    assert a == b




class TestFridgeCore(object):
    def _create_snapshot(self):
        return [
            SnapshotItem(checksum='a1b2', path='a'),
            SnapshotItem(checksum='cd34', path='b')
        ]

    def test_snapshot_roundtrip(self):
        snapshot = [
            SnapshotItem('key1', ' \n\t/weird path \n'),
            SnapshotItem('key2', '\n another path')]
        serialized = FridgeCore.serialize_snapshot(snapshot)
        parsed = FridgeCore.parse_snapshot(serialized)
        assert snapshot == parsed

    def test_add_blob(self, cas_factory, fridge):
        fridge.add_blob('path')
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
        s2 = [SnapshotItem('key', 'xyz')]

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

    def test_checkout_blob(self, fs, cas_factory, fridge):
        with fs.open('mockfile', 'w') as f:
            f.write(u'content')
        cas_factory['blobs'].get_path.return_value = 'mockfile'
        fridge.checkout_blob('key', 'target')
        assert fs.get_node(
            ['mockfile']).content == fs.get_node(['target']).content

    def test_checkout_blob_on_checkedout(self, fs, cas_factory, fridge):
        with fs.open('mockfile', 'w') as f:
            f.write(u'content')
        fs.symlink('mockfile', 'target')
        cas_factory['blobs'].get_path.return_value = 'mockfile'
        fridge.checkout_blob('key', 'target')
        assert fs.get_node(
            ['mockfile']).content == fs.get_node(['target']).content

    def test_checkout_blob_on_otherfile(self, fs, cas_factory, fridge):
        with fs.open('mockfile', 'w') as f:
            f.write(u'content')
        with fs.open('target', 'w') as f:
            f.write(u'otherfile')
        cas_factory['blobs'].get_path.return_value = 'mockfile'
        with pytest.raises(OSError) as excinfo:
            fridge.checkout_blob('key', 'target')
        assert excinfo.value.errno == errno.EEXIST
