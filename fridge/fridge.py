from datetime import datetime
from sqlalchemy import \
    create_engine, Column, DateTime, ForeignKey, Integer, Sequence, String, Text
from sqlalchemy.orm import backref, relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class Experiment(Base):
    __tablename__ = 'experiments'

    name = Column(String(128), primary_key=True)
    created = Column(DateTime(timezone=True), nullable=False)
    description = Column(Text, nullable=False)

    def __init__(self, fridge, name, description=''):
        self.fridge = fridge
        self.name = name
        self.created = datetime.now()
        self.description = description

    def create_trial(self, config):
        trial = Trial(self.fridge, self, config)
        self.fridge.add(trial)
        return trial


class Trial(Base):
    __tablename__ = 'trials'

    id = Column(Integer, Sequence('trial_id_seq'), primary_key=True)
    reason = Column(Text, nullable=False)
    start = Column(DateTime(timezone=True))
    end = Column(DateTime(timezone=False))
    experiment_name = Column(String(128), ForeignKey('experiments.name'))

    experiment = relationship(
        'Experiment', backref=backref('trials', order_by=id))

    def __init__(self, fridge, experiment, config):
        self.fridge = fridge
        self.experiment = experiment

    def start(self):
        self.start = datetime.now()
        self.fridge.commit()

    def finished(self):
        self.end = datetime.now()
        self.fridge.commit()

    def __repr__(self):
        return '<trial %i in experiment %s, start %s, end %s, reason: %s>' % (
            self.id, self.experiment_name, str(self.start), str(self.end),
            self.reason)


class Fridge(object):
    def __init__(self, db_path, spec):
        self.engine = create_engine('sqlite:///' + db_path)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        self.spec = spec
        self.trials = self.session.query(Trial)

    def add(self, obj):
        self.session.add(obj)

    def commit(self):
        self.session.commit()

    def create_experiment(self, name, description):
        experiment = Experiment(self, name, description)
        self.add(experiment)
        return experiment

    def init(self):
        Base.metadata.create_all(self.engine)
