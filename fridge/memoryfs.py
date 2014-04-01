import collections
import errno
import os
import StringIO


class MemoryFile(object):
    def __init__(self):
        self.content = ''
        self.delegate = None
        self.open()

    def open(self):
        self.delegate = StringIO.StringIO(self.content)

    def flush(self):
        self.content = self.delegate.getvalue()

    def close(self):
        self.content = self.delegate.getvalue()
        self.delegate.close()

    def __getattr__(self, name):
        return getattr(self.delegate, name)

    def __enter__(self):
        return self

    def __exit__(self, err_type, value, traceback):
        self.close()


class MemoryFS(object):
    def __init__(self, parent=None):
        self.children = {}
        if parent is None:
            parent = self
        self.parent = parent

    def _split_whole_path(self, path):
        split = collections.deque()
        while path != '':
            path, tail = os.path.split(path)
            split.appendleft(tail)
        return split

    def get_node(self, split_path):
        it = iter(split_path)
        try:
            name = it.next()
        except StopIteration:
            return self

        if name == os.path.curdir:
            node = self
        elif name == os.path.pardir:
            node = self.parent
        else:
            node = self.children[name]
        return node.get_node(it)

    def mkdir(self, path):
        split_path = self._split_whole_path(path)
        dirname = split_path.pop()
        node = self.get_node(split_path)

        if dirname in node.children:
            raise OSError(errno.EEXIST, 'Directory exists already.', path)

        node.children[dirname] = MemoryFS(self)

    def makedirs(self, path):
        split_path = self._split_whole_path(path)

        node = self
        while len(split_path) > 0:
            dirname = split_path.popleft()
            if dirname not in node.children:
                node.mkdir(dirname)
            node = node.get_node([dirname])

    def open(self, path, mode='r'):
        split_path = self._split_whole_path(path)
        filename = split_path.pop()
        node = self.get_node(split_path)

        create = 'w' in mode or ('a' in mode and filename not in node.children)
        if create:
            node.children[filename] = MemoryFile()
        f = node.children[filename]
        f.open()
        if 'a' in mode:
            f.seek(0, os.SEEK_END)
        return f
