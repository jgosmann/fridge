#!/usr/bin/env python

from datetime import datetime
from fridge import Fridge, FridgeError
from hamcrest import assert_that, equal_to, has_item, is_
from matchers import class_with
from nose.tools import raises
import shutil
import tempfile


class DateTimeProviderMock(datetime):
    timestamp = 0

    @classmethod
    def now(cls, tz=None):
        assert tz is None, 'Timezone handling not mocked'
        return datetime.fromtimestamp(cls.timestamp)


class FrigdeFixture(object):
    def setUp(self):
        self.datetime_provider = DateTimeProviderMock
        self.fridge_path = tempfile.mkdtemp()
        Fridge.init_dir(self.fridge_path)
        self.open_fridge()

    def tearDown(self):
        self.fridge.close()
        shutil.rmtree(self.fridge_path)

    def open_fridge(self):
        self.fridge = Fridge(self.fridge_path)
        self.fridge.datetime_provider = self.datetime_provider

    def reopen_fridge(self):
        self.fridge.close()
        self.open_fridge()


class TestFridgeInitApi(object):
    @raises(FridgeError)
    def test_raises_exception_when_already_initialized(self):
        fridge_path = tempfile.mkdtemp()
        Fridge.init_dir(fridge_path)
        Fridge.init_dir(fridge_path)


class TestFridgeExperimentApi(FrigdeFixture):
    def test_stores_created_experiment(self):
        experiment_name = 'somename'
        experiment_desc = 'somedesc'
        self.fridge.create_experiment(experiment_name, experiment_desc)
        self.reopen_fridge()
        assert_that(self.fridge.experiments, has_item(class_with(
            name=experiment_name, description=experiment_desc)))

    def test_creation_returns_experiment(self):
        experiment_name = 'somename'
        experiment_desc = 'somedesc'
        exp = self.fridge.create_experiment(experiment_name, experiment_desc)
        assert_that(exp, is_(class_with(
            name=experiment_name, description=experiment_desc)))

    def test_allows_to_access_experiments_by_name(self):
        experiment_name = 'somename'
        experiment_desc = 'somedesc'
        self.fridge.create_experiment(experiment_name, experiment_desc)
        assert_that(
            self.fridge.experiments.get(experiment_name), is_(class_with(
                name=experiment_name, description=experiment_desc)))

    def test_experiment_has_creation_date(self):
        timestamp = 90
        self.datetime_provider.timestamp = timestamp
        exp = self.fridge.create_experiment('unused', 'unused')
        assert_that(
            exp.created, is_(equal_to(datetime.fromtimestamp(timestamp))))


class TestFridgeTrialsApi(FrigdeFixture):
    def setUp(self):
        super().setUp()
        self.experiment = self.fridge.create_experiment('test', 'unused_desc')

    def reopen_fridge(self):
        super().reopen_fridge()
        self.experiment = self.fridge.experiments[0]

    def test_stores_trial_with_reason(self):
        reason = 'For testing.'
        trial = self.experiment.create_trial()
        trial.reason = reason
        trial.run(lambda: None)

        self.reopen_fridge()
        assert_that(self.fridge.trials, has_item(class_with(reason=reason)))

    def test_records_execution_time(self):
        timestamp_start = 90
        timestamp_end = 160
        trial = self.experiment.create_trial()

        def task():
            self.datetime_provider.timestamp = timestamp_end

        self.datetime_provider.timestamp = timestamp_start
        trial.run(task)

        assert_that(self.fridge.trials, has_item(class_with(
            start=datetime.fromtimestamp(timestamp_start),
            end=datetime.fromtimestamp(timestamp_end))))
