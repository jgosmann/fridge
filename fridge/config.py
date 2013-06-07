

class Specification(object):
    def __init__(self, version, config_options):
        self.version = version
        self.config_options = config_options


class Option(object):
    def __init__(
            self, type=None, default=None, desc=None, scope=None,
            required=True):
        self.type = type
        self.default = default
        self.desc = None
        self.scope = scope
        self.required = required

    def validate(self, path, value):
        if not self.scope is None:
            assert value in self.scope


class FloatRangeScope(object):
    def __init__(self, min=None, max=None):
        self.min = min
        self.max = max

    def __contains__(self, value):
        return self.min <= value and value <= self.max


class ConfigTree(object):
    def __getattr__(self, name):
        if not name in self.__dict__:
            self.__dict__[name] = ConfigTree()
        return self.__dict__[name]

    # TODO use an exception better describing the problem and do not split the
    # validation like at the moment
    def validate(self, path, config_options):
        for name, option_spec in config_options.items():
            if name in self.__dict__:
                if isinstance(option_spec, Option):
                    if not option_spec.type is None:
                        self.__dict__[name] = option_spec.type(self.__dict__[name])
                    option_spec.validate(path + [name], self.__dict__[name])
                else:
                    self.__dict__[name].validate(path + [name], option_spec)
            else:
                assert not option_spec.required
                self.__dict__[name] = option_spec.default


class Config(object):
    def __init__(self):
        self.version = None
        self.root = ConfigTree()

    def validate(self, specification):
        self.root.validate(['root'], specification.config_options)
        self.version = specification.version
