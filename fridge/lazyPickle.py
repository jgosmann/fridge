from collections.abc import Mapping
try:
    import cPickle as pickle
except:
    import pickle


class _LazyPickle(object):
    def __init__(self, obj):
        self.repr = repr(obj)
        self.pickle = pickle.dumps(obj)

    def __repr__(self):
        return self.repr

    def unpickle(self):
        return pickle.loads(self.pickle)


class _LazyPickleMapping(Mapping):
    def __init__(self, mapping):
        self._proxy = {}
        for k, v in mapping.items():
            self._proxy[k] = _lazify(v)

    def __getitem__(self, key):
        obj = self._proxy[key]
        if isinstance(obj, _LazyPickle):
            obj = obj.unpickle()
        return obj

    def __len__(self):
        return len(self._proxy)

    def __iter__(self):
        return iter(self._proxy.keys())

    def keys(self):
        return self._proxy.keys()

    def repr_of(self, *key_path):
        if len(key_path) == 1:
            return repr(self._proxy[key_path[0]])
        else:
            return self._proxy[key_path[0]].repr_of(*key_path[1:])


def _lazify(obj):
    if isinstance(obj, Mapping):
        return _LazyPickleMapping(obj)
    else:
        return _LazyPickle(obj)


def dumps(obj):
    return pickle.dumps(_lazify(obj))


def loads(bytes_object):
    unpickled = pickle.loads(bytes_object)
    if isinstance(unpickled, _LazyPickle):
        unpickled = unpickled.unpickle()
    return unpickled


PicklingError = pickle.PicklingError
UnpicklingError = pickle.UnpicklingError
