from datetime import datetime
from sqlalchemy import \
    create_engine, Column, DateTime, ForeignKey, Integer, LargeBinary, \
    Sequence, String, Text
from sqlalchemy.orm import backref, relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from .vcs import GitRepo
import os
import os.path
import warnings

try:
    import cPickle as pickle
except:
    import pickle


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


class ParameterObject(Base):
    __tablename__ = 'parameterObjects'

    id = Column(Integer, Sequence('parameterObjects_id_seq'), primary_key=True)
    repr = Column(String(), nullable=False)
    _pickle = Column(LargeBinary())
    trial_id = Column(Integer, ForeignKey('trials.id'))

    trial = relationship('Trial', backref=backref('arguments'))
    # FIXME many to many?
    # FIXME sorting

    def __init__(self, obj):
        self.repr = repr(obj)
        try:
            self.obj = obj
        except pickle.PicklingError:
            warnings.warn(RuntimeWarning(
                'Cannot pickle object. Only the string representation was ' +
                'stored.'))

    def get_obj(self):
        if self._pickle is None:
            return None
        return pickle.loads(self._pickle)

    def set_obj(self, obj):
        self._pickle = pickle.dumps(obj)

    obj = property(get_obj, set_obj)


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

    experiment = relationship(
        'Experiment', backref=backref('trials', order_by=id))

    def __init__(self, fridge, experiment):
        self.fridge = fridge
        self.experiment = experiment

    def run(self, fn, *args):
        self.check_run_preconditions()

        self._record_start_time()
        self._record_revisions()
        self._record_arguments(*args)
        self.fridge.commit()

        fn(*args)

        self._record_end_time()
        self.fridge.commit()

    def check_run_preconditions(self):
        for p in self._get_repo_rel_paths():
            if GitRepo(os.path.join(self.fridge.path, p)).isdirty():
                raise FridgeError('Repository %s is dirty.' % p)

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

    def __repr__(self):
        return '<trial %i in experiment %s, start %s, end %s, reason: %s>' % (
            self.id, self.experiment_name, str(self.start), str(self.end),
            self.reason)


class Fridge(object):
    DIRNAME = '.fridge'
    DBNAME = 'fridge.db'

    def __init__(self, path):
        self.path = path
        self.engine = create_engine(self.path_to_db_file(path))
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        self.experiments = self.session.query(Experiment)
        self.trials = self.session.query(Trial)
        self.datetime_provider = datetime

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


class FridgeError(Exception):
    pass
