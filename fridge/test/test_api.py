from datetime import datetime
from fridge.api import CallbackList, Fridge, Trial, FridgeError
from fridge.vcs import GitRepo
from hamcrest import all_of, anything, assert_that, contains, \
    contains_inanyorder, contains_string, equal_to, has_item, has_string, \
    instance_of, is_
from hamcrest.library.text.stringcontainsinorder import \
    string_contains_in_order
from matchers import class_with, empty, file_with_content
from nose.tools import raises
try:
    from unittest.mock import MagicMock, patch
except:
    from mock import MagicMock, patch
import hashlib
import os.path
import shutil
import sys
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


class FridgeFixture(object):
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


class TestCallbackList(object):
    def test_is_initially_empty(self):
        cb_list = CallbackList()
        assert_that(cb_list, is_(empty()))

    def test_can_be_initialized_with_seq(self):
        seq = [lambda x: 0, lambda x: 1, lambda x: 2]
        cb_list = CallbackList(seq)
        assert_that(cb_list, contains(*seq))

    def test_can_append(self):
        cb = lambda x: 0
        cb_list = CallbackList()
        cb_list.append(cb)
        assert_that(cb_list, contains(cb))


class TestFridgeInitApi(object):
    @raises(FridgeError)
    def test_raises_exception_when_already_initialized(self):
        fridge_path = tempfile.mkdtemp()
        try:
            Fridge.init_dir(fridge_path)
            Fridge.init_dir(fridge_path)
        finally:
            shutil.rmtree(fridge_path)

    @raises(FridgeError)
    def test_raises_exception_when_opening_uninitialized_dir(self):
        fridge_path = tempfile.mkdtemp()
        try:
            Fridge(fridge_path)
        finally:
            shutil.rmtree(fridge_path)


class TestFridgeExperimentApi(FridgeFixture):
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


class TestFridgeTrialsApi(FridgeFixture):
    def setUp(self):
        FridgeFixture.setUp(self)
        self.experiment = self.fridge.create_experiment('test', 'unused_desc')

    def reopen_fridge(self):
        FridgeFixture.reopen_fridge(self)
        self.experiment = self.fridge.experiments[0]

    def test_stores_trial_with_reason(self):
        reason = 'For testing.'
        trial = self.experiment.create_trial()
        trial.reason = reason
        trial.run(lambda workpath: None)

        self.reopen_fridge()
        assert_that(self.fridge.trials, has_item(class_with(reason=reason)))

    def test_records_trial_type(self):
        trial = self.experiment.create_trial()
        trial.run(lambda workpath: None)

        self.reopen_fridge()
        # FIXME cast to list in all test as this gives better output.
        assert_that(list(self.fridge.trials), has_item(class_with(
            type='python-function')))

    def test_records_trial_return_value(self):
        trial = self.run_new_trial_and_reopen_fridge(lambda *args: 42)
        assert_that(
            trial.return_value.retrieve(), is_(equal_to(42)))

    def test_records_trial_exception(self):
        def raise_exception(*args):
            raise Exception(42)

        trial = self.run_new_trial_and_reopen_fridge(raise_exception)
        assert_that(trial.exception.retrieve(), is_(all_of(
            instance_of(Exception), class_with(args=(42,)))))

    def test_records_execution_time(self):
        timestamp_start = 90
        timestamp_end = 160
        trial = self.experiment.create_trial()

        def task(workpath):
            self.datetime_provider.timestamp = timestamp_end

        self.datetime_provider.timestamp = timestamp_start
        trial.run(task)

        assert_that(self.fridge.trials, has_item(class_with(
            start=datetime.fromtimestamp(timestamp_start),
            end=datetime.fromtimestamp(timestamp_end))))

    def test_calls_function_with_args(self):
        args = [4, 'xyz']
        trial = self.experiment.create_trial()
        self.fridge.commit()
        workpath = string_contains_in_order(
            os.path.join(self.fridge.path, self.fridge.DIRNAME),
            str(trial.id))
        expected_args = args + [workpath]
        # Using dictionary as workaround for missing nonlocal keyword in
        # Python < 3, see http://technotroph.wordpress.com/2012/10/01/python-closures-and-the-python-2-7-nonlocal-solution/
        called = {0: False}

        def task(*args):
            #nonlocal called
            called[0] = True
            assert_that(args, contains(*expected_args))

        trial.run(task, *args)
        assert_that(called[0], is_(True))

    def test_stores_git_sourcecode_revisions(self):
        repos = [(p, self.create_git_repo_with_dummy_commit(
            os.path.join(self.fridge_path, p))) for p in ['repoA', 'repoB']]
        trial = self.experiment.create_trial()
        trial.run(lambda workpath: None)
        trial_id = trial.id
        self.reopen_fridge()

        expected_revisions = [(p, repo.current_revision())
                              for p, repo in repos]
        trial = self.fridge.trials.get(trial_id)
        actual_revisions = [(rev.path, rev.revision)
                            for rev in trial.revisions]
        assert_that(actual_revisions, contains_inanyorder(*expected_revisions))

    def test_stores_git_sourcecode_revision_for_single_root_repo(self):
        repo = self.create_git_repo_with_dummy_commit(self.fridge_path)
        trial = self.experiment.create_trial()
        trial.run(lambda workpath: None)
        trial_id = trial.id
        self.reopen_fridge()

        trial = self.fridge.trials.get(trial_id)
        assert_that(trial.revisions, contains(class_with(
            revision=repo.current_revision())))

    @raises(FridgeError)
    def test_raises_exception_for_dirty_repo(self):
        self.create_git_repo_with_dummy_commit(self.fridge_path)
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

    def test_records_called_function_name(self):
        def task_fn(*args):
            pass

        trial = self.run_new_trial_and_reopen_fridge(task_fn)
        assert_that(
            trial.arguments[0].value.retrieve(), is_(equal_to('task_fn()')))

    def test_records_run_arguments_representation(self):
        args = (42, 'some text', Pickleable(0))
        self.run_new_trial_and_reopen_fridge(
            lambda x, y, z, workpath: None, *args)
        assert_that(self.fridge.trials, has_item(class_with(arguments=contains(
            *[anything()] + [class_with(repr=repr(a)) for a in args] +
            [anything()]))))

    def test_records_run_arguments_objects(self):
        args = [42, 'some text', Pickleable(0)]
        trial = self.run_new_trial_and_reopen_fridge(
            lambda x, y, z, workpath: None, *args)
        stored_args = (a.value.retrieve() for a in trial.arguments)
        assert_that(stored_args, contains(*[anything()] + args + [anything()]))

    def test_records_run_argument_without_object_if_pickling_fails(self):
        unpickleable = lambda: None
        args = (unpickleable,)
        self.run_new_trial_and_reopen_fridge(lambda x, workpath: None, *args)
        assert_that(self.fridge.trials, has_item(class_with(arguments=contains(
            *[anything()] + [class_with(
                repr=repr(a), value=class_with(pickle=None)) for a in args] +
            [anything()]))))

    def test_issues_warning_if_pickling_of_argument_fails(self):
        unpickleable = lambda: None
        args = (unpickleable,)
        trial = self.experiment.create_trial()
        with warnings.catch_warnings(record=True) as w:
            trial.run(lambda x, workpath: None, *args)
            assert_that(w, has_item(class_with(message=all_of(
                instance_of(RuntimeWarning),
                has_string(contains_string('pickle'))))))

    def test_parameter_repr_accessible_even_if_unpickling_not_possible(self):
        args = (Pickleable(0),)
        self.run_new_trial_and_reopen_fridge(lambda x, workpath: None, *args)

        global Pickleable
        orig_class = Pickleable
        Pickleable = None
        try:
            assert_that(self.fridge.trials, has_item(class_with(
                arguments=contains(
                    *[anything()] + [class_with(repr=repr(a)) for a in args] +
                    [anything()]))))
        finally:
            Pickleable = orig_class

    @raises(pickle.UnpicklingError, TypeError)
    def test_raises_exception_on_parameter_access_if_unpickling_fails(self):
        args = (Pickleable(0),)
        trial = self.run_new_trial_and_reopen_fridge(
            lambda x, workpath: None, *args)

        global Pickleable
        orig_class = Pickleable
        Pickleable = None
        try:
            trial.arguments[1].value.retrieve()
        finally:
            Pickleable = orig_class

    def test_can_access_parameters_in_dict_if_it_contains_unpickleable_values(
            self):
        args = ({'accessible': 42, 'not accessible': Pickleable(0)},)
        trial = self.run_new_trial_and_reopen_fridge(
            lambda x, workpath: None, *args)

        global Pickleable
        orig_class = Pickleable
        Pickleable = None
        try:
            assert_that(
                trial.arguments[1].value['accessible'].retrieve(), is_(42))
        finally:
            Pickleable = orig_class

    def test_workpath_exists_while_running_trial(self):
        def check_path(workpath):
            assert_that(os.path.isdir(workpath), is_(True))

        trial = self.experiment.create_trial()
        trial.run(check_path)

    def test_records_information_about_written_files(self):
        def gen_output(workpath):
            with open(os.path.join(workpath, 'file.txt'), 'wb') as file:
                file.write(b'somecontent')

        trial = self.run_new_trial_and_reopen_fridge(gen_output)
        assert_that(trial.outputs, has_item(class_with(
            filename='file.txt', size=11,
            hash=hashlib.sha1(b'somecontent').digest())))

    def test_moves_output_files_to_final_location(self):
        def gen_output(workpath):
            with open(os.path.join(workpath, 'file.txt'), 'wb') as file:
                file.write(b'somecontent')

        self.run_new_trial_and_reopen_fridge(gen_output)
        outfile = os.path.join(
            self.fridge.path, self.fridge.config.data_path,
            self.experiment.name, 'file.txt')
        assert_that(outfile, is_(file_with_content(equal_to(b'somecontent'))))

    def test_can_add_additional_file(self):
        fd, filename = tempfile.mkstemp()
        try:
            os.write(fd, b'somecontent')
            trial = self.experiment.create_trial()
            trial.add_file('output', filename)
        finally:
            os.close(fd)
            os.unlink(filename)

        trial.run(lambda workpath: None)
        trial_id = trial.id
        self.reopen_fridge()
        trial = self.fridge.trials.get(trial_id)
        assert_that(trial.outputs, has_item(class_with(
            filename=filename, size=11,
            hash=hashlib.sha1(b'somecontent').digest())))

    def test_archives_contents_of_referenced_files(self):
        def gen_output(workpath):
            with open(os.path.join(workpath, 'file.txt'), 'wb') as file:
                file.write(b'somecontent')

        trial = self.run_new_trial_and_reopen_fridge(gen_output)
        outfile = os.path.join(
            self.fridge.path, self.fridge.config.data_path,
            self.experiment.name, 'file.txt')
        os.unlink(outfile)
        with trial.outputs[0].open('rb') as file:
            assert_that(file, is_(file_with_content(equal_to(b'somecontent'))))

    def test_records_information_about_input_files(self):
        fd, filename = tempfile.mkstemp()
        try:
            os.write(fd, b'somecontent')
            trial = self.experiment.create_trial()
            trial.run(lambda *args: None, filename)
        finally:
            os.close(fd)
            os.unlink(filename)

        trial_id = trial.id
        self.reopen_fridge()
        trial = self.fridge.trials.get(trial_id)

        assert_that(trial.inputs, has_item(class_with(
            filename=filename, size=11,
            hash=hashlib.sha1(b'somecontent').digest())))

    def test_captures_stdout(self):
        def write_to_stdout(*args):
            sys.stdout.write('somecontent')

        with patch('sys.stdout'):
            trial = self.run_new_trial_and_reopen_fridge(write_to_stdout)
        assert_that(trial.outputs, has_item(class_with(
            filename='stdout.txt', size=11,
            hash=hashlib.sha1('somecontent'.encode('utf-8')).digest())))

    def test_captures_stderr(self):
        def write_to_stderr(*args):
            sys.stderr.write('somecontent')

        with patch('sys.stderr'):
            trial = self.run_new_trial_and_reopen_fridge(write_to_stderr)
        assert_that(trial.outputs, has_item(class_with(
            filename='stderr.txt', size=11,
            hash=hashlib.sha1('somecontent'.encode('utf-8')).digest())))

    def test_stores_outcome_information(self):
        trial = self.run_new_trial_and_reopen_fridge(lambda *args: None)
        outcome = 'This is some text describing the outcome.'
        trial.outcome = outcome

        trial_id = trial.id
        self.reopen_fridge()
        trial = self.fridge.trials.get(trial_id)

        assert_that(trial.outcome, is_(equal_to(outcome)))

    def test_stores_parsed_input_files(self):
        fd, filename = tempfile.mkstemp('.py')
        try:
            os.write(fd, b'somevar = 42')
            trial = self.experiment.create_trial()
            trial.run(lambda *args: None, filename)
        finally:
            os.close(fd)
            os.unlink(filename)

        trial_id = trial.id
        self.reopen_fridge()
        trial = self.fridge.trials.get(trial_id)

        assert_that(trial.inputs[0].parsed['somevar'].retrieve(), is_(42))

    # TODO parsing file with unpickleable
    def test_issues_warning_if_pickling_of_parsed_config_item_fails(self):
        fd, filename = tempfile.mkstemp('.py')
        try:
            os.write(fd, b'unpickleable = lambda: None')
            trial = self.experiment.create_trial()
            with warnings.catch_warnings(record=True) as w:
                trial.run(lambda *args: None, filename)
                assert_that(w, has_item(class_with(message=all_of(
                    instance_of(RuntimeWarning),
                    has_string(contains_string('pickle'))))))
        finally:
            os.close(fd)
            os.unlink(filename)

    # FIXME raise exception when trying to run an already run trial


class TestFridgeTrialsPluginApi(FridgeFixture):
    def setUp(self):
        FridgeFixture.setUp(self)
        self.experiment = self.fridge.create_experiment('test', 'unused_desc')

    def test_calls_before_and_after_run_hooks(self):
        before_mock = MagicMock()
        after_mock = MagicMock()
        Trial.before_run += before_mock
        Trial.after_run += after_mock

        reason = 'Unit test.'
        trial = self.experiment.create_trial()
        trial.reason = reason
        trial.run(lambda workpath: None)

        before_mock.assert_called_once_with(trial)
        after_mock.assert_called_once_with(trial)
