from __future__ import absolute_import

from weakref import WeakKeyDictionary

from fridge.api import Trial
from sumatra.datastore.base import DataKey
from sumatra.programs import get_executable
from sumatra.projects import load_project
from sumatra.parameters import build_parameters


_projects = WeakKeyDictionary()
_records = WeakKeyDictionary()


def _update_dict(d, new_values):
    for k, v in new_values.items():
        try:
            if not k in d:
                d[k] = {}
            _update_dict(d[k], v)
        except:
            d[k] = v


def before_run(trial):
    project = load_project(trial.fridge.path)

    executable = get_executable(trial.arguments[0].value.retrieve())
    # FIXME this could be improved.
    # What is if we do state the interpreter explicitly and there is just a
    # main file?
    # What is if there are additional arguments to the interpreter? The main
    # file might occur at a different position within the arguments.
    # Is it save to use value? But repr will add quotes.
    main_file = trial.arguments[1].value.retrieve()
    input_files = [f for f in trial.files
                   if f.type == 'input' and f.filename != main_file]

    parameters = {}
    for infile in input_files:
        try:
            _update_dict(parameters, build_parameters(infile.filename))
        except:
            try:
                _update_dict(parameters, infile.parsed)
            except:  # FIXME be more specific about what exceptions are ok
                pass

    input_data = [DataKey(f.filename, f.get_hexhash()) for f in input_files]
    script_args = [str(arg.value.retrieve()) for arg in trial.arguments[2:]]
    label = '%s-%i' % (trial.experiment_name, trial.id)

    record = project.new_record(
        executable=executable, main_file=main_file,
        parameters=parameters, input_data=input_data, script_args=script_args,
        reason=trial.reason, label=label)

    _records[trial] = record
    _projects[trial] = project


def after_run(trial):
    record = _records[trial]
    project = _projects[trial]

    if record is not None and project is not None:
        record.duration = (trial.end - trial.start).total_seconds()
        record.output_data = [
            DataKey(f.filename, f.get_hexhash())
            for f in trial.files if f.type == 'output']
        project.add_record(record)
        project.save()


Trial.before_run.append(before_run)
Trial.after_run.append(after_run)
