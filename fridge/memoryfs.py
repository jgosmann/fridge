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
