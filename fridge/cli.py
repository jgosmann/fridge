from .api import Fridge
import argparse
import os
import subprocess
import tempfile


class FridgeCli(object):
    def __init__(self):
        self.environ = os.environ
        self.call = subprocess.call

    def main(self, args):
        parser = argparse.ArgumentParser(
            prog='fridge',
            description='Fridge stores your scientific simulation results ' +
            'and keeps them fresh.')
        parser.add_argument(
            'cmd', nargs=1, type=str, choices=self.dispatch.keys(),
            help='Subcommand to execute.')
        parser.add_argument('args', nargs=argparse.REMAINDER)
        parsed = parser.parse_args(args)

        self.dispatch[parsed.cmd[0]](self, parsed.args)

    def init(self, args):
        Fridge.init_dir(os.getcwd())

    def experiment(self, args):
        parser = argparse.ArgumentParser(
            prog='fridge experiment',
            description='List the existing experiments or create a new one.')
        parser.add_argument(
            'name', nargs=1, type=str, help='Name of experiment to create')
        parsed = parser.parse_args(args)

        description = self._get_from_editor('description.')
        fridge = Fridge(os.getcwd())
        fridge.create_experiment(parsed.name[0], description)
        fridge.commit()

    def _get_from_editor(self, tempfile_prefix=''):
        # FIXME use fridge dir
        with tempfile.NamedTemporaryFile('r+', prefix=tempfile_prefix) as file:
            if self.call([self.environ['EDITOR'], file.name]) != 0:
                raise Exception  # FIXME use a reasonable exception
            return file.read()

    dispatch = {
        'init': init,
        'experiment': experiment
    }
