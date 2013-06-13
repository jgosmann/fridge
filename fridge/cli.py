from .api import Fridge
import argparse
import os


class FridgeCli(object):
    def main(self, *args):
        parser = argparse.ArgumentParser(
            prog='fridge',
            description='Fridge stores your scientific simulation results ' +
            'and keeps them fresh.')
        parser.add_argument(
            'cmd', nargs=1, type=str, choices=self.dispatch.keys(),
            help='Subcommand to execute.')
        parser.add_argument('args', nargs=argparse.REMAINDER)
        parsed = parser.parse_args(args)

        self.dispatch[parsed.cmd[0]](self, *parsed.args)

    def init(self, *args):
        Fridge.init_dir(os.getcwd())

    dispatch = {
        'init': init
    }
