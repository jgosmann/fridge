from datetime import datetime
from sqlalchemy import \
    create_engine, BINARY, Column, DateTime, Enum, ForeignKey, Integer, \
    PickleType, Sequence, String, Text
from sqlalchemy.orm import backref, relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from .vcs import GitRepo
from .lazyPickle import lazify
import binascii
import hashlib
import os
import os.path
import shutil
import warnings
try:
    import cPickle as pickle
except:
    import pickle


# TODO test this function
def sha1sum(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        buf = b'\0'
        while buf != b'':
            buf = f.read(1024 * 1024)
            h.update(buf)
    return h.digest()


Base = declarative_base()


class Experiment(Base):
    __tablename__ = 'experiments'

    name = Column(String(128), primary_key=True)
    created = Column(DateTime(timezone=True), nullable=False)
    description = Column(Text, nullable=False)

    def __init__(self, fridge, name, description=''):
        self.fridge = fridge
        self.name = name
        self.created = fridge.datetime_provider.now()
        self.description = description

    def create_trial(self):
        trial = Trial(self.fridge, self)
        self.fridge.add(trial)
        return trial

    def __repr__(self):
        return '<experiment %s, created %s, desc: %s>' % (
            self.name, str(self.created), self.description)


class File(Base):
    __tablename__ = 'files'

    id = Column(Integer, Sequence('files_id_seq'), primary_key=True)
    type = Column(Enum('output'), nullable=False)
    filename = Column(String(), nullable=False)
    size = Column(Integer, nullable=False)
    sha1 = Column(BINARY(160 / 8), nullable=False)
    trial_id = Column(Integer, ForeignKey('trials.id'))

    trial = relationship('Trial', backref=backref('files', lazy='dynamic'))

    def __init__(self, type, filename, size, sha1):
        self.type = type
        self.filename = filename
        self.size = size
        self.sha1 = sha1


class ParameterObject(Base):
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
        except pickle.PicklingError:
            warnings.warn(RuntimeWarning(
                'Cannot pickle object. Only the string representation was ' +
                'stored.'))

    def get_value(self):
        if self._pickle is None:
            return None
        return self._pickle

    def set_value(self, value):
        self._pickle = lazify(value)

    value = property(get_value, set_value)


class Revision(Base):
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


class Trial(Base):
    __tablename__ = 'trials'

    id = Column(Integer, Sequence('trial_id_seq'), primary_key=True)
    reason = Column(Text, nullable=False, default='')
    start = Column(DateTime(timezone=True))
    end = Column(DateTime(timezone=True))
    experiment_name = Column(String(128), ForeignKey('experiments.name'))

    @hybrid_property
    def outputs(self):
        return self.files.filter(File.type == 'output')

    experiment = relationship(
        'Experiment', backref=backref('trials', order_by=id))

    def __init__(self, fridge, experiment):
        self.fridge = fridge
        self.experiment = experiment

    def run(self, fn, *args):
        self.check_run_preconditions()

        args = list(args) + [self.workpath]

        self._record_start_time()
        self._record_revisions()
        self._record_arguments(*args)
        self.fridge.commit()

        self._prepare_run()
        fn(*args)

        self._record_end_time()
        self._record_output_files()
        self.fridge.commit()
        self._move_data_to_final_location()

    def check_run_preconditions(self):
        for p in self._get_repo_rel_paths():
            if GitRepo(os.path.join(self.fridge.path, p)).isdirty():
                raise FridgeError('Repository %s is dirty.' % p)

    def _prepare_run(self):
        os.makedirs(self.workpath, exist_ok=True)

    def _get_repo_rel_paths(self):
        if GitRepo.isrepo(os.path.join(self.fridge.path, '.')):
            yield '.'
        else:
            for p in os.listdir(self.fridge.path):
                path = os.path.join(self.fridge.path, p)
                if os.path.isdir(path) and GitRepo.isrepo(path):
                    yield p

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
        for dirpath, dirnames, filenames in os.walk(self.workpath):
            filepath = dirpath[len(self.workpath):]
            for filename in filenames:
                self._add_file('output', os.path.join(filepath, filename))

    def _add_file(self, type, filename):
        path = os.path.join(self.workpath, filename)
        size = os.path.getsize(path)
        sha1 = sha1sum(path)
        self.files.append(File(type, filename, size, sha1))

        sha1hex = binascii.hexlify(sha1).decode()
        destdir = os.path.join(
            self.fridge.blobpath, sha1hex[0:3], sha1hex[3:6])
        destfilepath = os.path.join(destdir, sha1hex)
        if not os.path.exists(destfilepath):
            os.makedirs(destdir, exist_ok=True)
            shutil.copy2(path, destfilepath)

    def _move_data_to_final_location(self):
        os.makedirs(self.datapath, exist_ok=True)
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

    def __init__(self, path):
        self.path = path
        self.engine = create_engine(self.path_to_db_file(path))
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
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
        experiment = Experiment(self, name, description)
        self.add(experiment)
        return experiment

    @classmethod
    def init_dir(cls, path):
        fridge_path = os.path.join(path, cls.DIRNAME)
        if os.path.exists(fridge_path):
            raise FridgeError('Already initialized.')
        os.mkdir(fridge_path)
        engine = create_engine(cls.path_to_db_file(path))
        Base.metadata.create_all(engine)

    @classmethod
    def path_to_db_file(cls, basepath):
        return 'sqlite:///' + os.path.join(basepath, cls.DIRNAME, cls.DBNAME)

    def get_blobpath(self):
        return os.path.join(self.path, self.DIRNAME, 'blobs')

    def get_datapath(self):
        return os.path.join(self.path, self.config.data_path)

    blobpath = property(get_blobpath)
    datapath = property(get_datapath)


class FridgeError(Exception):
    pass
