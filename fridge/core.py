import os.path


class FridgeCore(object):
    def __init__(self, fs, cas_factory):
        self._fs = fs
        self._blobs = cas_factory(os.path.join('.fridge', 'blobs'), fs)

    def add_blob(self, path):
        self._blobs.store(path)
