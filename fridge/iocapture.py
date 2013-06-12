import io
import sys


class CaptureStdout(io.TextIOBase):
    def __init__(self, redirection):
        self.redirection = redirection

    def __enter__(self):
        self.orig_fd = sys.stdout
        sys.stdout = self

    def __exit__(self, type, value, traceback):
        sys.stdout = self.orig_fd

    def write(self, s):
        self.orig_fd.write(s)
        self.redirection.write(s)


class CaptureStderr(io.TextIOBase):
    def __init__(self, redirection):
        self.redirection = redirection

    def __enter__(self):
        self.orig_fd = sys.stderr
        sys.stderr = self

    def __exit__(self, type, value, traceback):
        sys.stderr = self.orig_fd

    def write(self, s):
        self.orig_fd.write(s)
        self.redirection.write(s)
