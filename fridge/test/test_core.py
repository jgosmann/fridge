import hashlib
import os.path

from mock import ANY, MagicMock
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
            self._cas[path].store.contents = []

            def store(p):
                try:
                    with fs.open(p) as f:
                        self._cas[path].store.contents.append(f.read())
                except KeyError:  # FIXME should be OSError
                    pass
            self._cas[path].store.side_effect = store

        return self._cas[path]

    def __getitem__(self, key):
        return self._cas[key]


@pytest.fixture
def cas_factory():
    return CasMockFactory()

@pytest.fixture
def fridge(cas_factory):
    return FridgeCore.init('.', MemoryFS(), cas_factory)


class TestFridgeCore(object):
    def _create_snapshot(self):
        # FIXME dont call sha1 directly.
        return [
            SnapshotItem(
                checksum=hashlib.sha1('a').hexdigest(),
                path='a'),
            SnapshotItem(
                checksum=hashlib.sha1('b').hexdigest(),
                path='b')
        ]

    def test_add_blob(self, cas_factory, fridge):
        fridge.add_blob('path')
        cas_factory['blobs'].store.assert_called_once_with('path')

    def test_writing_and_parsing_snapshot(self, cas_factory, fridge):
        s = self._create_snapshot()
        fridge.add_snapshot(s)
        cas_factory['snapshots'].store.assert_called_once_with(ANY)
        assert s == fridge.parse_snapshot(
            cas_factory['snapshots'].store.contents[0])
