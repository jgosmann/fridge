import errno
import hashlib
import os
import os.path


# FIXME move to another module
class FileSystem(object):
    def mkdir(self, path):
        os.mkdir(path)

    def makedirs(self, path):
        os.makedirs(path)

    def rename(self, src, dest):
        os.rename(src, dest)

    def symlink(self, src, link_name):
        os.symlink(src, link_name)

    def open(self, path, mode='r'):
        return open(path, mode)


class ContentAddressableStorage(object):
    def __init__(self, root, fs=FileSystem()):
        self._root = root
        self._fs = fs

    @property
    def root(self):
        return self._root

    def store(self, filepath):
        key = self._calc_checksum(filepath)
        target_path = self.get_path(key)

        try:
            self._fs.makedirs(os.path.dirname(target_path))
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise

        self._fs.rename(filepath, target_path)
        self._fs.symlink(target_path, filepath)
        return key

    def get_path(self, key):
        return os.path.join(self._root, key[:2], key[2:])

    def _calc_checksum(self, path):
        # TODO which hash function should be used?
        h = hashlib.sha1()
        with self._fs.open(path, 'rb') as f:
            buf = b'\0'
            while buf != b'':
                buf = f.read(1024 * 1024)  # TODO which read size to use?
                h.update(buf)
        return h.hexdigest()
