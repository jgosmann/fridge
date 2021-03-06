"""Provides an in-memory file system with functions resembling those of
``os.path``."""

import collections
import errno
from io import BytesIO, StringIO
import os
import stat as st


class __TimeCounter(object):
    slots = ['t']

    def __init__(self):
        self.t = 0.

    def __call__(self):
        self.t += 1.
        return self.t


_get_time = __TimeCounter()


class Stat(object):
    def __init__(self, other=None):
        self.st_mode = 0
        self.st_atime = 0.
        self.st_mtime = 0.
        self.st_size = 0

        if other is not None:
            for attr in dir(self):
                if not attr.startswith('_'):
                    setattr(self, attr, getattr(other, attr))

    def __eq__(self, other):
        for attr in dir(self):
            if not attr.startswith('_'):
                if getattr(self, attr) != getattr(other, attr):
                    return False
        return True


class MemoryFSNode(object):
    """Base class for nodes in an in-memory file system.

    Parameters
    ----------
    stat : :class:`Stat`
        Status flags for the node.
    parent : :class:`MemoryFSNode`, optional
        Parent of the node. Will be set to the node itself, if ``None``.

    Attributes
    ----------
    parent : :class:`MemoryFSNode`
        Parent of the node.
    children : dict
        The children of the node.
    """

    def __init__(self, parent=None, stat=None):
        if stat is None:
            stat = Stat()
            stat.st_mode = (
                st.S_IRWXU | st.S_IRGRP | st.S_IXGRP |
                st.S_IROTH | st.S_IXOTH | st.S_IFDIR)
        if parent is None:
            parent = self
        self.status = stat
        self.parent = parent
        self.children = {}

    def get_node(self, split_path):
        """Returns a child node.

        Parameters
        ----------
        split_path : list
            List of keys constituting the path to the subnode.

        Returns
        -------
        node : :class:`MemoryFSNode`
            The found child node.
        """
        it = iter(split_path)
        try:
            name = next(it)
        except StopIteration:
            return self

        if name == os.path.curdir:
            node = self
        elif name == os.path.pardir:
            node = self.parent
        else:
            node = self.children[name]
        return node.get_node(it)


class MemoryFile(MemoryFSNode):
    """In-memory file (behaves like a :term:`file object`).

    Parameters
    ----------
    parent : :class:`MemoryFSNode`, optional
        Parent of the node. Will be set to the node itself, if ``None``.

    Attributes
    ----------
    content : bytes
        Content of the file.
    """
    def __init__(self, parent=None):
        stat = Stat()
        stat.st_mode = (
            st.S_IRUSR | st.S_IWUSR | st.S_IRGRP | st.S_IWGRP |
            st.S_IROTH | st.S_IWOTH | st.S_IFREG)
        super(MemoryFile, self).__init__(parent, stat)
        self.content = b''
        self._delegate = None
        self._mode = None

    def open(self, mode='r'):
        """Opens the file for reading or writing.

        Valid mode flags are:

        * ``'r'``: Open file for reading.
        * ``'w'``: Open file for writing.
        * ``'a'``: Open file for appending.
        * ``'+'``: Open file for reading and writing. In combination with
          ``'w'`` the file will be truncated.
        * ``'t'``: Open file in text mode.
        * ``'b'``: Open file in binary mode.

        Parameters
        ----------
        mode : str, optional
            Combination of mode flags (see above) to define the open mode.

        Returns
        -------
        self : :class:`MemoryFile`

        See also
        --------
        io.open
        """
        need_read_perm = 'r' in mode or '+' in mode
        need_write_perm = 'w' in mode or 'a' in mode
        if need_read_perm and not st.S_IMODE(self.status.st_mode) & st.S_IREAD:
            raise OSError(errno.EACCES, "Permission denied.")
        if (need_write_perm and
                not st.S_IMODE(self.status.st_mode) & st.S_IWRITE):
            raise OSError(errno.EACCES, "Permission denied.")

        if 'w' in mode:
            self.content = b''

        self._mode = mode
        if 'b' in mode:
            self._delegate = BytesIO(self.content)
        else:
            self._delegate = StringIO(self.content.decode())
        if 'a' in mode:
            self._delegate.seek(0, os.SEEK_END)
        return self

    def flush(self):
        """Flushes the written data to :attr:`content`."""
        self._delegate.flush()
        if 'b' in self._mode:
            self.content = self._delegate.getvalue()
        else:
            self.content = self._delegate.getvalue().encode()
        self.status.st_size = len(self.content)
        self.status.st_mtime = _get_time()

    def close(self):
        """Flushes and closes the file.

        See also
        --------
        flush
        """
        self.flush()
        self._delegate.close()

    def __getattr__(self, name):
        return getattr(self._delegate, name)

    def __enter__(self):
        return self

    def __exit__(self, err_type, value, traceback):
        self.close()


class MemoryFS(MemoryFSNode):
    """In memory file system.

    The methods of this class are meant resemble functions in :mod:`os`.
    """

    def _split_whole_path(self, path):
        split = collections.deque()
        while path != '':
            path, tail = os.path.split(path)
            split.appendleft(tail)
        return split

    def mkdir(self, path):
        """Creates a directory.

        If the directory exists, an :class:`OSError` will be raised.

        Parameters
        ----------
        path : str
            Path of the directory to create.

        See also
        --------
        makedirs, os.mkdir
        """
        split_path = self._split_whole_path(path)
        dirname = split_path.pop()
        node = self.get_node(split_path)

        if dirname in node.children:
            raise OSError(errno.EEXIST, 'Directory exists already.', path)

        node.children[dirname] = MemoryFS(self)

    def makedirs(self, path):
        """Creates a directory with all intermediate directories recursively.

        If the directory exists, an :class:`OSError` will be raised.

        Parameters
        ----------
        path : str
            Path of the directory to create.

        See also
        --------
        mkdir, os.makedirs
        """
        split_path = self._split_whole_path(path)

        created_dir = False
        node = self
        while len(split_path) > 0:
            dirname = split_path.popleft()
            if dirname not in node.children:
                node.mkdir(dirname)
                created_dir = True
            node = node.get_node([dirname])

        if not created_dir:
            raise OSError(errno.EEXIST, 'Directory exists already.', path)

    def chmod(self, path, mode):
        s = self.get_node(self._split_whole_path(path)).status
        s.st_mode = st.S_IFMT(s.st_mode) | st.S_IMODE(mode)

    def copy(self, src, dest):
        """Copy a file.

        Parameters
        ----------
        src : str
            Source path.
        dest : str
            Destination path.

        See also
        --------
        shutil.copy
        """
        src_split = self._split_whole_path(src)
        src_base = src_split.pop()
        src_node = self.get_node(src_split)

        dest_split = self._split_whole_path(dest)
        dest_base = dest_split.pop()
        dest_node = self.get_node(dest_split)

        copied = MemoryFile(dest_node)
        with src_node.children[src_base].open('rb') as sf:
            with copied.open('wb') as df:
                df.write(sf.read())

        dest_node.children[dest_base] = copied

    def exists(self, path):
        try:
            self.get_node(self._split_whole_path(path))
        except KeyError:
            return False
        return True

    def rename(self, src, dest):
        """Renames a file or directory.

        If the destination exists, an :class:`OSError` will be raised.

        Parameters
        ----------
        src : str
            Source path.
        dest : str
            Destination path.

        See also
        --------
        os.rename
        """
        src_split = self._split_whole_path(src)
        src_base = src_split.pop()
        src_node = self.get_node(src_split)

        dest_split = self._split_whole_path(dest)
        dest_base = dest_split.pop()
        dest_node = self.get_node(dest_split)

        if dest_base in dest_node.children:
            raise OSError(errno.EEXIST, 'Destination exists already.', dest)

        dest_node.children[dest_base] = src_node.children[src_base]
        del src_node.children[src_base]

    def rmdir(self, path):
        # TODO documentation
        split_path = self._split_whole_path(path)
        dirname = split_path.pop()
        node = self.get_node(split_path)
        if len(node.children[dirname].children) > 0:
            raise OSError(errno.ENOTEMPTY, "Directory not empty.")
        del node.children[dirname]

    def stat(self, path):
        return Stat(self.get_node(self._split_whole_path(path)).status)

    def symlink(self, src, link_name):
        """Create a symbolic link.

        Raises :class:`OSError` if `link_name` exists already.

        Parameters
        ----------
        src : str
            Path to point the link to.
        link_name : str
            Path/name of the link.

        See also
        --------
        os.symlink
        """
        src_node = self.get_node(self._split_whole_path(src))

        dest_split = self._split_whole_path(link_name)
        dest_base = dest_split.pop()
        dest_node = self.get_node(dest_split)

        if dest_base in dest_node.children:
            raise OSError(errno.EEXIST, 'File exists already.', link_name)

        # This is actually a hard link. Might be necessary to change this in
        # the future, but for now it will work as we provide no method which
        # would allow to differentiate between the two.
        dest_node.children[dest_base] = src_node

    def open(self, path, mode='r'):
        """Opens the file for reading or writing.

        Valid mode flags are:

        * ``'r'``: Open file for reading.
        * ``'w'``: Open file for writing.
        * ``'a'``: Open file for appending.
        * ``'+'``: Open file for reading and writing. In combination with
          ``'w'`` the file will be truncated.
        * ``'t'``: Open file in text mode.
        * ``'b'``: Open file in binary mode.

        Parameters
        ----------
        path : str
            Path of file to open.
        mode : str, optional
            Combination of mode flags (see above) to define the open mode.

        Returns
        -------
        f : :class:`MemoryFile`
            Opened file object.

        See also
        --------
        MemoryFile.open, io.open
        """
        split_path = self._split_whole_path(path)
        filename = split_path.pop()
        node = self.get_node(split_path)

        create = ('w' in mode or 'a' in mode) and filename not in node.children
        if create:
            node.children[filename] = MemoryFile()
        try:
            f = node.children[filename]
        except KeyError:
            raise OSError(errno.ENOENT, 'No such file or directory.', path)
        try:
            f.open(mode)
        except OSError as e:
            e.filename = path
            raise
        return f

    def samefile(self, a, b):
        """Checks whether two paths point to the same file.

        Parameters
        ----------
        a, b : str
            The two paths

        Returns
        -------
        bool
            ``True`` if both paths are the same file and ``False`` otherwise.

        See also
        --------
        os.path.samefile
        """
        return self.get_node(self._split_whole_path(a)) is self.get_node(
            self._split_whole_path(b))

    def unlink(self, path):
        """Removes a file.

        Will raise :class:`OSError` if `path` is a file.

        Parameters
        ----------
        path : str
            Path to the file to delete.

        See also
        --------
        os.unlink, os.remove
        """
        split_path = self._split_whole_path(path)
        filename = split_path.pop()
        try:
            node = self.get_node(split_path)
            del node.children[filename]
        except KeyError:
            raise OSError(errno.ENOENT, 'No such file or directory.', path)

    def utime(self, path, times):
        atime, mtime = times
        node = self.get_node(self._split_whole_path(path))
        node.status.st_atime = atime
        node.status.st_mtime = mtime

    def walk(self, path, topdown=True):
        # TODO documentation
        if not topdown:
            for item in reversed(list(self.walk(path, topdown=True))):
                yield item
            return

        stack = [(path, self.get_node(self._split_whole_path(path)))]
        while len(stack) > 0:
            node_path, node = stack.pop()
            dirnames = []
            filenames = []
            for name, child in node.children.items():
                if isinstance(child, MemoryFile):
                    filenames.append(name)
                else:
                    dirnames.append(name)
            yield node_path, dirnames, filenames

            for name, child in node.children.items():
                if name in dirnames:
                    stack.append((os.path.join(node_path, name), child))
