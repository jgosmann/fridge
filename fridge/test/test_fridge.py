from datetime import datetime
from fridge import Fridge, FridgeError
from fridge.vcs import GitRepo
from hamcrest import all_of, anything, assert_that, contains, \
    contains_inanyorder, contains_string, equal_to, has_entry, has_item, \
    has_string, instance_of, is_
from matchers import class_with
from nose.tools import raises
import os.path
import shutil
import tempfile
import warnings

import pickle


class DateTimeProviderMock(datetime):
    timestamp = 0

    @classmethod
    def now(cls, tz=None):
        assert tz is None, 'Timezone handling not mocked'
        return datetime.fromtimestamp(cls.timestamp)


class Pickleable(object):
    def __init__(self, id):
        self.id = id

    def __eq__(self, item):
        return self.id == item.id

    def __repr__(self):
        return 'Pickable(%i)' % self.id


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
        trial.run(lambda outpath: None)

        self.reopen_fridge()
        assert_that(self.fridge.trials, has_item(class_with(reason=reason)))

    def test_records_execution_time(self):
        timestamp_start = 90
        timestamp_end = 160
        trial = self.experiment.create_trial()

        def task(outpath):
            self.datetime_provider.timestamp = timestamp_end

        self.datetime_provider.timestamp = timestamp_start
        trial.run(task)

        assert_that(self.fridge.trials, has_item(class_with(
            start=datetime.fromtimestamp(timestamp_start),
            end=datetime.fromtimestamp(timestamp_end))))

    def test_calls_function_with_args(self):
        args = [4, 'xyz']
        outpath = os.path.join(
            self.fridge.config.data_path, self.experiment.name)
        expected_args = args + [outpath]
        called = False

        def task(*args):
            nonlocal called
            called = True
            assert_that(args, contains(*expected_args))

        trial = self.experiment.create_trial()
        trial.run(task, *args)
        assert_that(called, is_(True))

    def test_stores_git_sourcecode_revisions(self):
        repos = [(p, self.create_git_repo_with_dummy_commit(
            os.path.join(self.fridge_path, p))) for p in ['repoA', 'repoB']]
        trial = self.experiment.create_trial()
        trial.run(lambda outpath: None)
        trial_id = trial.id
        self.reopen_fridge()

        expected_revisions = [(p, repo.current_revision()) for p, repo in repos]
        trial = self.fridge.trials.get(trial_id)
        actual_revisions = [(rev.path, rev.revision) for rev in trial.revisions]
        assert_that(actual_revisions, contains_inanyorder(*expected_revisions))

    def test_stores_git_sourcecode_revision_for_single_root_repo(self):
        repo = self.create_git_repo_with_dummy_commit(self.fridge_path)
        trial = self.experiment.create_trial()
        trial.run(lambda outpath: None)
        trial_id = trial.id
        self.reopen_fridge()

        trial = self.fridge.trials.get(trial_id)
        assert_that(trial.revisions, contains(class_with(
            revision=repo.current_revision())))

    @raises(FridgeError)
    def test_raises_exception_for_dirty_repo(self):
        repo = self.create_git_repo_with_dummy_commit(self.fridge_path)
        with open(os.path.join(self.fridge_path, 'dirty.txt'), 'w') as file:
            file.write('dirty')

        trial = self.experiment.create_trial()
        trial.run(lambda: None)

    @staticmethod
    def create_git_repo_with_dummy_commit(path):
        repo = GitRepo.init(path)
        filename = os.path.join(path, 'file.txt')
        with open(filename, 'w') as file:
            file.write('content')
        gitignore_path = os.path.join(path, '.gitignore')
        with open(gitignore_path, 'w') as file:
            file.write('.fridge')
        repo.add([filename, gitignore_path])
        repo.commit('Initial commit.')
        return repo

    def run_new_trial_and_reopen_fridge(self, fn, *args):
        trial = self.experiment.create_trial()
        trial.run(fn, *args)
        trial_id = trial.id
        self.reopen_fridge()
        return self.fridge.trials.get(trial_id)


    def test_records_run_arguments_representation(self):
        args = (42, 'some text', Pickleable(0))
        trial = self.run_new_trial_and_reopen_fridge(
            lambda x, y, z, outpath: None, *args)
        assert_that(self.fridge.trials, has_item(class_with(arguments=contains(
                *[class_with(repr=repr(a)) for a in args] + [anything()]))))

    def test_records_run_arguments_objects(self):
        args = [42, 'some text', Pickleable(0)]
        trial = self.run_new_trial_and_reopen_fridge(
            lambda x, y, z, outpath: None, *args)
        stored_args = (a.value.retrieve() for a in trial.arguments)
        assert_that(stored_args, contains(*args + [anything()]))

    def test_records_run_argument_without_object_if_pickling_fails(self):
        unpickleable = lambda: None
        args = (unpickleable,)
        trial = self.run_new_trial_and_reopen_fridge(
            lambda x, outpath: None, *args)
        assert_that(self.fridge.trials, has_item(class_with(arguments=contains(
            *[class_with(repr=repr(a), value=None) for a in args] +
            [anything()]))))

    def test_issues_warning_if_pickling_of_argument_fails(self):
        unpickleable = lambda: None
        args = (unpickleable,)
        trial = self.experiment.create_trial()
        with warnings.catch_warnings(record=True) as w:
            trial.run(lambda x, outpath: None, *args)
            assert_that(w, has_item(class_with(message=all_of(
                instance_of(RuntimeWarning),
                has_string(contains_string('pickle'))))))

    def test_parameter_repr_accessible_even_if_unpickling_not_possible(self):
        args = (Pickleable(0),)
        trial = self.run_new_trial_and_reopen_fridge(
            lambda x, outpath: None, *args)

        global Pickleable
        orig_class = Pickleable
        Pickleable = None
        try:
            assert_that(self.fridge.trials, has_item(class_with(
                arguments=contains(
                    *[class_with(repr=repr(a)) for a in args] +
                    [anything()]))))
        finally:
            Pickleable = orig_class

    @raises(pickle.UnpicklingError)
    def test_raises_exception_on_parameter_access_if_unpickling_fails(self):
        args = (Pickleable(0),)
        trial = self.run_new_trial_and_reopen_fridge(
            lambda x, outpath: None, *args)

        global Pickleable
        orig_class = Pickleable
        Pickleable = None
        try:
            trial.arguments[0].value.retrieve()
        finally:
            Pickleable = orig_class

    def test_can_access_parameters_in_dict_if_it_contains_unpickleable_values(
            self):
        args = ({'accessible': 42, 'not accessible': Pickleable(0)},)
        trial = self.run_new_trial_and_reopen_fridge(
            lambda x, outpath: None, *args)

        global Pickleable
        orig_class = Pickleable
        Pickleable = None
        try:
            assert_that(
                trial.arguments[0].value['accessible'].retrieve(), is_(42))
        finally:
            Pickleable = orig_class

    def test_outpath_exists_while_running_trial(self):
        def check_path(outpath):
            assert_that(os.path.isdir(outpath), is_(True))

        trial = self.experiment.create_trial()
        trial.run(check_path)

    # TODO store function name
