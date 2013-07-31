try:
    from subprocess import DEVNULL
except:
    import os
    DEVNULL = open(os.devnull, 'w')
import subprocess


class GitRepo(object):
    def __init__(self, path):
        self.path = path

    @classmethod
    def init(cls, path):
        subprocess.check_output(['git', 'init', path])
        return cls(path)

    def add(self, files):
        self.do('add', *files)

    def commit(self, message):
        self.do('commit', '-m', message)

    def current_revision(self):
        return self.do('rev-parse', 'HEAD')

    def do(self, cmd, *args):
        return subprocess.check_output(
            ['git', cmd] + list(args), cwd=self.path)

    def isdirty(self):
        # FIXME is it wise to ignore untracked files? But always aborting
        # because of them is also quite annoying and they might be config files
        # you do not want to commit.
        return self.do(
            'status', '--porcelain', '--untracked-files=no').strip() != b''

    @classmethod
    def isrepo(cls, path):
        return subprocess.call(
            ['git', 'rev-parse'], cwd=path, stdout=DEVNULL,
            stderr=DEVNULL) == 0
