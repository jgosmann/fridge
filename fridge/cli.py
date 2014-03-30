from .api import Fridge, sha1sum
import argparse
from importlib import import_module
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
            '-p', '--plugins', nargs='+', type=str, default=[],
            help='Plugins to load.')
        parser.add_argument(
            'cmd', nargs=1, type=str, choices=self.dispatch.keys(),
            help='Subcommand to execute.')
        parser.add_argument('args', nargs=argparse.REMAINDER)
        parsed = parser.parse_args(args)

        for plugin in parsed.plugins:
            import_module(plugin)

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

    def run(self, args):
        parser = argparse.ArgumentParser(
            prog='fridge run',
            description='Run a trial and store results.')
        parser.add_argument('-e', '--experiment', nargs=1, type=str)
        parser.add_argument('-r', '--reason', nargs=1, type=str)
        parser.add_argument('args', nargs=argparse.REMAINDER)
        parsed = parser.parse_args(args)

        fridge = Fridge(os.getcwd())
        exp = fridge.experiments.get(parsed.experiment[0])
        trial = exp.create_trial()
        if parsed.reason is None:
            trial.reason = self._get_from_editor('reason.')
        else:
            trial.reason = parsed.reason[0]
        trial.run_external(*parsed.args)

    def show(self, args):
        # FIXME test this function
        parser = argparse.ArgumentParser(
            prog='fridge show', description='Show the results of a trial.')
        parser.add_argument('-f', '--file', nargs=1, type=str, required=True)
        parsed = parser.parse_args(args)

        fridge = Fridge(os.getcwd())

        sha1 = sha1sum(parsed.file[0])
        files = fridge.files.filter_by(hash=sha1)
        assert files.count() == 1  # FIXME handling of multiple files
        trial = files[0].trial
        self._show_trial(trial)

    def _show_trial(self, trial):
        print('''id: {id}
reason: {reason}
outcome: {outcome}
start: {start}
end: {end}
return value: {return_value}
experiment name: {experiment_name}
'''.format(
            id=trial.id, reason=trial.reason, outcome=trial.outcome,
            start=trial.start, end=trial.end, return_value=trial.return_value,
            experiment_name=trial.experiment_name))

        for file in trial.files:
            show = file.filename.endswith('stdout.txt') or \
                file.filename.endswith('stderr.txt')
            if show:
                print(file.filename)
                with file.open('r') as f:
                    for line in f:
                        print(line)
                print()

    def _get_from_editor(self, tempfile_prefix=''):
        # FIXME use fridge dir
        fd, filename = tempfile.mkstemp(prefix=tempfile_prefix)
        os.close(fd)
        try:
            if self.call([self.environ['EDITOR'], filename]) != 0:
                raise Exception  # FIXME use a reasonable exception
            with open(filename, 'r') as file:
                return file.read()
        finally:
            os.unlink(filename)

    dispatch = {
        'init': init,
        'experiment': experiment,
        'run': run,
        'show': show
    }
