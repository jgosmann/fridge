#!/usr/bin/env python

from fridge.fridge import Fridge
from fridge.config import Config, Specification, Option
import unittest


class TestFridge(unittest.TestCase):
    spec = Specification(0, {
        'some_opt': Option(int),
    })

    def test_stores_trial_data(self):
        frd = Fridge(':memory:', self.spec)
        frd.init()
        experiment = frd.create_experiment('test', 'desc')

        config = Config()
        config.root.some_opt = 42
        trial = experiment.create_trial(config)
        trial.reason = 'For testing.'
        trial.start()
        # call to program producing data
        trial.finished()

        self.assertEqual(frd.trials.count(), 1)
        trial = frd.trials[0]
        # TODO store config
        #self.assertEqual(trial.config.root.some_opt, 42)
        self.assertEqual(trial.reason, 'For testing.')
        self.assertEqual(trial.experiment.name, 'test')

        # TODO result comments, start, stop, experiment


if __name__ == '__main__':
    unittest.main()
