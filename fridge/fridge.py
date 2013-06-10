from datetime import datetime
from sqlalchemy import \
    create_engine, Column, DateTime, ForeignKey, Integer, Sequence, String, Text
from sqlalchemy.orm import backref, relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os
import os.path


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
        self.start = self.fridge.datetime_provider.now()
        self.fridge.commit()
        fn(*args)
        self.end = self.fridge.datetime_provider.now()
        self.fridge.commit()

    def __repr__(self):
        return '<trial %i in experiment %s, start %s, end %s, reason: %s>' % (
            self.id, self.experiment_name, str(self.start), str(self.end),
            self.reason)


class Fridge(object):
    DIRNAME = '.fridge'
    DBNAME = 'fridge.db'

    def __init__(self, path):
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
