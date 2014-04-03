import os.path

from mock import MagicMock

from fridge.memoryfs import MemoryFS
from fridge.core import FridgeCore


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


class TestFridgeCore(object):
    def test_add_blob(self):
        cas_factory = CasMockFactory()
        fridge = FridgeCore(MemoryFS(), cas_factory)
        fridge.add_blob('path')
        cas_factory['blobs'].store.assert_called_once_with('path')
