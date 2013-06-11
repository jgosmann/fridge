from hamcrest import assert_that, equal_to, has_entries, is_
from nose.tools import raises
from fridge.lazyPickle import lazify
try:
    import cPickle as pickle
except:
    import pickle


class Pickleable(object):
    def __init__(self, id):
        self.id = id

    def __eq__(self, item):
        return self.id == item.id

    def __repr__(self):
        return 'Pickable(%i)' % self.id


class TestLazyPickles(object):
    def test_roundtrip_dict(self):
        obj = {'a': 42, 'obj': Pickleable(0)}
        pickled = pickle.dumps(lazify(obj))
        restored = pickle.loads(pickled).retrieve()
        assert_that(restored, has_entries(obj))

    def test_roundtrip_nondict(self):
        obj = Pickleable(0)
        pickled = pickle.dumps(lazify(obj))
        restored = pickle.loads(pickled).retrieve()
        assert_that(restored, is_(equal_to(obj)))

    def test_if_unpickling_fails_for_one_dict_value_others_are_still_available(
            self):
        obj = {'a': 42, 'obj': Pickleable(0)}
        pickled = pickle.dumps(lazify(obj))
        global Pickleable
        orig_class = Pickleable
        Pickleable = None
        try:
            restored = pickle.loads(pickled)
            assert_that(restored['a'].retrieve(), is_(42))
        finally:
            Pickleable = orig_class

    @raises(pickle.UnpicklingError)
    def test_raises_exception_if_unpickling_fails(self):
        obj = {'a': 42, 'obj': Pickleable(0)}
        pickled = pickle.dumps(lazify(obj))
        global Pickleable
        orig_class = Pickleable
        Pickleable = None
        try:
            restored = pickle.loads(pickled)
            restored['obj'].retrieve()
        finally:
            Pickleable = orig_class

    @raises(pickle.UnpicklingError)
    def test_raises_exception_if_unpickling_fails2(self):
        obj = {'a': 42, 'obj': Pickleable(0)}
        pickled = pickle.dumps(lazify(obj))
        global Pickleable
        orig_class = Pickleable
        Pickleable = None
        try:
            pickle.loads(pickled).retrieve()
        finally:
            Pickleable = orig_class

    def test_if_unpickling_fails_for_one_dict_value_repr_can_still_be_accessed(
            self):
        obj = {'a': 42, 'b': {'obj': Pickleable(0)}}
        pickled = pickle.dumps(lazify(obj))
        global Pickleable
        orig_class = Pickleable
        Pickleable = None
        try:
            restored = pickle.loads(pickled)
            assert_that(repr(restored), is_(repr(obj)))
        finally:
            Pickleable = orig_class
