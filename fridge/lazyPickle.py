from collections import Mapping
try:
    import cPickle as pickle
except:
    import pickle


class _LazyPickle(object):
    def __init__(self, obj, onerror=None):
        self.repr = repr(obj)
        try:
            self.pickle = pickle.dumps(obj)
        except Exception as err:
            if not onerror is None:
                self.pickle = onerror(err)
            else:
                raise err

    def __repr__(self):
        return self.repr

    def retrieve(self):
        return pickle.loads(self.pickle)


class _LazyPickleMapping(Mapping):
    def __init__(self, mapping, onerror=None):
        self._proxy = {}
        for k, v in mapping.items():
            self._proxy[k] = lazify(v, onerror)

    def __getitem__(self, key):
        return self._proxy[key]

    def __len__(self):
        return len(self._proxy)

    def __iter__(self):
        return iter(self._proxy.keys())

    def keys(self):
        return self._proxy.keys()

    def retrieve(self):
        delazified = {}
        for k, v in self.items():
            delazified[k] = v.retrieve()
        return delazified

    def __repr__(self):
        return repr(self._proxy)


def lazify(obj, onerror=None):
    if isinstance(obj, Mapping):
        return _LazyPickleMapping(obj, onerror)
    else:
        return _LazyPickle(obj, onerror)
