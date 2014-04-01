import collections
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


class MemoryFS(object):
    def __init__(self, parent=None):
        self.children = {}
        self.parent = parent

    def _split_whole_path(self, path):
        split = collections.deque()
        while path != '':
            path, tail = os.path.split(path)
            split.appendleft(tail)
        return list(split)

    def get_node(self, split_path):
        if len(split_path) <= 0:
            return self

        if split_path[0] == os.path.curdir:
            node = self
        elif split_path[0] == os.path.pardir:
            node = self.parent
        else:
            node = self.children[split_path[0]]
        return node.get_node(split_path[1:])

    def mkdir(self, path):
        split_path = self._split_whole_path(path)
        node = self.get_node(split_path[:-1])
        node.children[split_path[-1]] = MemoryFS(self)
