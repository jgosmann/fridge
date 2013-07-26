from weakref import WeakKeyDictionary

from fridge.api import Trial
from sumatra.datastore.base import DataKey
from sumatra.projects import load_project
from sumatra.parameters import build_parameters


_projects = WeakKeyDictionary()
_records = WeakKeyDictionary()


def _update_dict(d, new_values):
    for k, v in new_values:
        d[k] = v


def before_run(trial):
    project = load_project(trial.fridge.path)
    parameters = {}
    for arg in trial.arguments:
        try:
            _update_dict(parameters, arg.value)
        except:
            try:
                _update_dict(parameters, build_parameters(arg.repr))
            except:
                pass
    input_data = [f.filename for f in trial.files if f.type == 'input']
    main_file = trial.arguments[0].repr
    script_args = [arg.repr for arg in trial.arguments[1:]]
    label = '%s-%i' % (trial.experiment_name, trial.id)

    record = project.new_record(
        main_file=main_file,
        parameters=parameters, input_data=input_data, script_args=script_args,
        reason=trial.reason, label=label)

    _records[trial] = record
    _projects[trial] = project


def after_run(trial):
    record = _records[trial]
    project = _projects[trial]

    if record is not None and project is not None:
        record.duration = trial.end - trial.start
        record.output_data = [
            DataKey(f.filename, f.get_hexhash())
            for f in trial.files if f.type == 'output']
        project.add_record(record)
        project.save()


Trial.before_run.append(before_run)
Trial.after_run.append(after_run)
