from datetime import datetime
from sqlalchemy import \
    create_engine, BINARY, Column, DateTime, Enum, ForeignKey, Integer,\
    PickleType, Sequence, String, Text
from sqlalchemy.orm import backref, relationship, sessionmaker
from sqlalchemy.orm.session import object_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from types import ModuleType
from weakref import WeakKeyDictionary
from .iocapture import CaptureStdout, CaptureStderr
from .lazyPickle import lazify
from .vcs import GitRepo
import binascii
import errno
import hashlib
import os
import os.path
import shutil
import subprocess
import warnings
try:
    import cPickle as pickle
except:
    import pickle


# FIXME this exception should include further information about the problematic
# object
class OnlyStringReprStoredWarning(UserWarning):
    def __init__(self, pickling_exception):
        self.pickling_exception = pickling_exception
        super(OnlyStringReprStoredWarning, self).__init__(
            'Cannot pickle object. '
            'Only the string representation was stored. '
            'Reason: ' + str(pickling_exception))

warnings.simplefilter('always', OnlyStringReprStoredWarning)


# TODO test this function
def sha1sum(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        buf = b'\0'
        while buf != b'':
            buf = f.read(1024 * 1024)
            h.update(buf)
    return h.digest()


def _makedirs(path, mode=0o777, exist_ok=False):
    try:
        os.makedirs(path, mode)
    except OSError as err:
        if exist_ok and err.errno == errno.EEXIST:
            return
        raise err


class CallbackList(list):
    def __call__(self, *args, **kwargs):
        for cb in self:
            cb(*args, **kwargs)


class InFridge(object):
    def get_fridge(self):
        return Fridge.session_to_fridge[object_session(self)]

    fridge = property(get_fridge)


InFridgeBase = declarative_base(cls=InFridge)


class Experiment(InFridgeBase):
    __tablename__ = 'experiments'

    name = Column(String(128), primary_key=True)
    created = Column(DateTime(timezone=True), nullable=False)
    description = Column(Text, nullable=False)

    def __init__(self, name, description='', datetime_provider=datetime):
        self.name = name
        self.created = datetime_provider.now()
        self.description = description

    def create_trial(self):
        trial = Trial(self)
        self.fridge.add(trial)
        return trial

    def __repr__(self):
        return '<experiment %s, created %s, desc: %s>' % (
            self.name, str(self.created), self.description)


class File(InFridgeBase):
    __tablename__ = 'files'

    id = Column(Integer, Sequence('files_id_seq'), primary_key=True)
    type = Column(Enum('input', 'output'), nullable=False)
    filename = Column(String(), nullable=False)
    size = Column(Integer, nullable=False)
    hash = Column(BINARY(160 / 8), nullable=False)
    parsed = Column(PickleType, nullable=True)
    trial_id = Column(Integer, ForeignKey('trials.id'))

    trial = relationship('Trial', backref=backref('files', lazy='dynamic'))

    def __init__(self, type, filename, size, hash):
        self.type = type
        self.filename = filename
        self.size = size
        self.hash = hash

    def open(self, mode='rb'):
        if not mode in ['r', 'rb']:
            raise ValueError('Only read access is allowed.')
        return open(self._filepath, mode)

    def get_hexhash(self):
        return binascii.hexlify(self.hash).decode()

    def _get_dir(self):
        hexhash = self.hexhash
        return os.path.join(self.fridge.blobpath, hexhash[0:3], hexhash[3:6])

    def _get_filepath(self):
        return os.path.join(self._dir, self.hexhash)

    hexhash = property(get_hexhash)
    _dir = property(_get_dir)
    _filepath = property(_get_filepath)


class ParameterObject(InFridgeBase):
    __tablename__ = 'parameterObjects'

    id = Column(Integer, Sequence('parameterObjects_id_seq'), primary_key=True)
    repr = Column(String(), nullable=False)
    _pickle = Column(PickleType())
    trial_id = Column(Integer, ForeignKey('trials.id'))

    trial = relationship('Trial', backref=backref('arguments'))
    # FIXME many to many?
    # FIXME sorting

    def __init__(self, value):
        self.repr = repr(value)
        try:
            self.value = value
        except (pickle.PicklingError, TypeError) as err:
            warnings.warn(OnlyStringReprStoredWarning(err))

    @staticmethod
    def _handle_lazify_error(err):
        if isinstance(err, pickle.PicklingError) or isinstance(err, TypeError):
            warnings.warn(OnlyStringReprStoredWarning(err))
            return None
        else:
            raise err

    def get_value(self):
        if self._pickle is None:
            return None
        return self._pickle

    def set_value(self, value):
        self._pickle = lazify(value, self._handle_lazify_error)

    value = property(get_value, set_value)


class Revision(InFridgeBase):
    __tablename__ = 'revisions'

    id = Column(Integer, Sequence('repository_id_seq'), primary_key=True)
    path = Column(String(), nullable=False)
    revision = Column(String(), nullable=False)
    trial_id = Column(Integer, ForeignKey('trials.id'))

    trial = relationship('Trial', backref=backref('revisions'))

    def __init__(self, path, revision):
        self.path = path
        self.revision = revision

    def __repr__(self):
        return '<revision %s of %s>' % (self.revision, self.path)


class Trial(InFridgeBase):
    __tablename__ = 'trials'

    id = Column(Integer, Sequence('trial_id_seq'), primary_key=True)
    reason = Column(Text, nullable=False, default='')
    outcome = Column(Text, nullable=False, default='')
    start = Column(DateTime(timezone=True))
    end = Column(DateTime(timezone=True))
    return_value = Column(PickleType)
    exception = Column(PickleType)
    type = Column(
        Enum('notrun', 'python-function', 'external'), default='notrun',
        nullable=False)
    experiment_name = Column(String(128), ForeignKey('experiments.name'))

    before_run = CallbackList()
    after_run = CallbackList()

    @hybrid_property
    def outputs(self):
        return self.files.filter(File.type == 'output')

    @hybrid_property
    def inputs(self):
        return self.files.filter(File.type == 'input')

    experiment = relationship(
        'Experiment', backref=backref('trials', order_by=id))

    def __init__(self, experiment):
        self.experiment = experiment

    # TODO test and refactor (code duplication with run)
    def run_external(self, *args):
        self.type = 'external'
        self.check_run_preconditions()

        self._record_start_time()
        self._record_revisions()
        self._record_input_files(*args[1:])
        args = list(args) + [self.workpath]
        self._record_arguments(*args)
        self.fridge.commit()

        self._prepare_run()
        self.before_run(self)
        stdout_filename = os.path.join(self.workpath, 'stdout.txt')
        stderr_filename = os.path.join(self.workpath, 'stderr.txt')
        with open(stdout_filename, 'w') as stdout_file, \
                open(stderr_filename, 'w') as stderr_file, \
                CaptureStdout(stdout_file), CaptureStderr(stderr_file):
            self.return_value = lazify(subprocess.call(args))

        self.after_run(self)
        self._record_end_time()
        self._record_output_files()
        self.fridge.commit()
        self._move_data_to_final_location()

    def run(self, fn, *args):
        self.type = 'python-function'
        self.check_run_preconditions()

        self._record_start_time()
        self._record_revisions()
        self._record_input_files(*args)
        args = list(args) + [self.workpath]
        self._record_arguments(*[fn.__name__ + '()'] + args)
        self.fridge.commit()

        self._prepare_run()
        self.before_run(self)
        stdout_filename = os.path.join(self.workpath, 'stdout.txt')
        stderr_filename = os.path.join(self.workpath, 'stderr.txt')
        with open(stdout_filename, 'w') as stdout_file, \
                open(stderr_filename, 'w') as stderr_file, \
                CaptureStdout(stdout_file), CaptureStderr(stderr_file):
            try:
                self.return_value = lazify(fn(*args))
            except Exception as ex:
                self.exception = lazify(ex)

        self.after_run(self)
        self._record_end_time()
        self._record_output_files()
        self.fridge.commit()
        self._move_data_to_final_location()

    def check_run_preconditions(self):
        for p in self._get_repo_rel_paths():
            if GitRepo(os.path.join(self.fridge.path, p)).isdirty():
                raise FridgeError('Repository %s is dirty.' % p)

    def _prepare_run(self):
        _makedirs(self.workpath, exist_ok=True)

    def _get_repo_rel_paths(self):
        if GitRepo.isrepo(os.path.join(self.fridge.path, '.')):
            yield '.'
        else:
            for p in os.listdir(self.fridge.path):
                path = os.path.join(self.fridge.path, p)
                if os.path.isdir(path) and GitRepo.isrepo(path):
                    yield p

    def _record_input_files(self, *args):
        for arg in args:
            if os.path.exists(str(arg)):
                self._record_files('input', arg)

    def _record_files(self, type, path):
        if os.path.isfile(path):
            self.add_file(type, path)
        else:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    self.add_file('output', os.path.join(dirpath, filename))

    def _record_arguments(self, *args):
        for arg in args:
            paramObj = ParameterObject(arg)
            self.arguments.append(paramObj)

    def _record_revisions(self):
        for p in self._get_repo_rel_paths():
            path = os.path.join(self.fridge.path, p)
            rev = Revision(p, GitRepo(path).current_revision())
            rev.trial = self
            self.fridge.add(rev)

    def _record_start_time(self):
        self.start = self.fridge.datetime_provider.now()

    def _record_end_time(self):
        self.end = self.fridge.datetime_provider.now()

    def _record_output_files(self):
        self._record_files('output', self.workpath)

    # FIXME some refactoring is needed:
    # - we have two identical _handle_lazify_error functions
    # - some parts of add_file might be better included in the File class
    # - parse functionality should be extracted from this class
    @staticmethod
    def _handle_lazify_error(err):
        if isinstance(err, pickle.PicklingError) or isinstance(err, TypeError):
            warnings.warn(OnlyStringReprStoredWarning(err))
            return None
        else:
            raise err

    def add_file(self, type, path):
        if path.startswith(self.workpath):
            filename = os.path.relpath(path, self.workpath)
        else:
            filename = path
        size = os.path.getsize(path)
        sha1 = sha1sum(path)
        file = File(type, filename, size, sha1)
        parsed = self._parse(path)
        if parsed is not None:
            file.parsed = lazify(parsed, self._handle_lazify_error)
        self.files.append(file)

        if not os.path.exists(file._dir):
            _makedirs(file._dir, exist_ok=True)
            shutil.copy2(path, file._filepath)

    def _parse(self, path):
        if path.endswith('.py'):
            entries = {}
            with open(path, 'r') as source:
                import_fix = '''
import sys
sys.path.insert(0, %s)
''' % repr(os.path.dirname(path))
                compiled = compile(import_fix + source.read(), path, 'exec')
                exec(compiled, entries)
            del entries['__builtins__']
            to_delete = [k for k in entries
                         if isinstance(entries[k], ModuleType)]
            for k in to_delete:
                del entries[k]
            return entries
        return None

    def _move_data_to_final_location(self):
        # FIXME this function will need some kind of locking when it should
        # be possible to run multiple trials in parallel.
        _makedirs(self.datapath, exist_ok=True)
        for item in os.listdir(self.workpath):
            os.rename(
                os.path.join(self.workpath, item),
                os.path.join(self.datapath, item))
        os.rmdir(self.workpath)

    def __repr__(self):
        return '<trial %i in experiment %s, start %s, end %s, reason: %s>' % (
            self.id, self.experiment_name, str(self.start), str(self.end),
            self.reason)

    def get_workpath(self):
        if self.id is None:
            self.fridge.commit()
        return os.path.join(
            self.fridge.path, self.fridge.DIRNAME, self.fridge.WORKDIR,
            self.experiment.name, str(self.id))

    def get_outpath(self):
        return os.path.join(self.fridge.datapath, self.experiment.name)

    workpath = property(get_workpath)
    datapath = property(get_outpath)


class StaticConfig(object):
    def __init__(self):
        self.data_path = 'Data'


class Fridge(object):
    DIRNAME = '.fridge'
    DBNAME = 'fridge.db'
    WORKDIR = 'work'

    session_to_fridge = WeakKeyDictionary()

    def __init__(self, path):
        self.path = path
        if not os.path.exists(self.path_to_db_file(path)):
            raise FridgeError('Not an initialized fridge directory.')
        self.engine = create_engine('sqlite:///' + self.path_to_db_file(path))
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        self.session_to_fridge[self.session] = self
        self.experiments = self.session.query(Experiment)
        self.trials = self.session.query(Trial)
        self.datetime_provider = datetime
        self.config = StaticConfig()

    def add(self, obj):
        self.session.add(obj)

    def close(self):
        self.commit()
        self.session.close()

    def commit(self):
        self.session.commit()

    def create_experiment(self, name, description):
        experiment = Experiment(name, description, self.datetime_provider)
        self.add(experiment)
        return experiment

    @classmethod
    def init_dir(cls, path):
        fridge_path = os.path.join(path, cls.DIRNAME)
        if os.path.exists(fridge_path):
            raise FridgeError('Already initialized.')
        os.mkdir(fridge_path)
        engine = create_engine('sqlite:///' + cls.path_to_db_file(path))
        InFridgeBase.metadata.create_all(engine)

    # FIXME refactor to property
    @classmethod
    def path_to_db_file(cls, basepath):
        return os.path.join(basepath, cls.DIRNAME, cls.DBNAME)

    def get_blobpath(self):
        return os.path.join(self.path, self.DIRNAME, 'blobs')

    def get_datapath(self):
        return os.path.join(self.path, self.config.data_path)

    blobpath = property(get_blobpath)
    datapath = property(get_datapath)


class FridgeError(Exception):
    pass
