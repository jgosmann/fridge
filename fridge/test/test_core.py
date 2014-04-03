import hashlib
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


class TestFridgeCore(object):
    def _create_snapshot(self):
        return [
            SnapshotItem(checksum='a1b2', path='a'),
            SnapshotItem(checksum='cd34', path='b')
        ]

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

    def test_setting_and_getting_head(self, fs):
        fridge = FridgeCore.init(os.curdir, fs)
        fridge.set_head('ab12cd')
        del fridge

        fridge = FridgeCore(os.curdir, fs)
        assert fridge.get_head() == 'ab12cd'
