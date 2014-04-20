"""Provides a content addressable storage."""

import errno
import hashlib
import os
import os.path

import fridge.fs


class ContentAddressableStorage(object):
    """Content addressable storage.

    Parameters
    ----------
    root : str
        Path to the root directory of the storage.
    fs : obj
        Object providing file system functions.
    """
    def __init__(self, root, fs=fridge.fs):
        self._root = root
        self._fs = fs

    @property
    def root(self):
        """The root directory of the storage."""
        return self._root

    def store(self, filepath):
        """Stores a file in the storage.

        The original file will be deleted and replaced by a symbolic link.

        Parameters
        ----------
        filepath : str
            The path to the file to store.

        Returns
        -------
        str
            Key to retrieve the stored file.
        """
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
        """Get the path to a stored file.

        Parameters
        ----------
        key : str
            Key of the stored file.

        Returns
        -------
        str
            Path to the file with the corresponding key.
        """
        return os.path.join(self._root, key[:2], key[2:])

    def _calc_checksum(self, path):
        # We'll stick to sha1 for now. It's almost as fast as md5, while more
        # secure hash function (i.e. sha256/512) need up to twice as long. As
        # this CAS might be used with huge data, speed is important.
        h = hashlib.sha1()
        with self._fs.open(path, 'rb') as f:
            buf = b'\0'
            while buf != b'':
                buf = f.read(4096)  # 4KiB is the block size of most HDD
                h.update(buf)
        return h.hexdigest()
