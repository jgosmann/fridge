from hamcrest import assert_that, equal_to, has_entries, is_
from nose.tools import raises
import fridge.lazyPickle as pickle


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
        pickled = pickle.dumps(obj)
        restored = pickle.loads(pickled)
        assert_that(restored, has_entries(obj))

    def test_roundtrip_nondict(self):
        obj = Pickleable(0)
        pickled = pickle.dumps(obj)
        restored = pickle.loads(pickled)
        assert_that(restored, is_(equal_to(obj)))

    def test_if_unpickling_fails_for_one_dict_value_others_are_still_available(
            self):
        obj = {'a': 42, 'obj': Pickleable(0)}
        pickled = pickle.dumps(obj)
        global Pickleable
        orig_class = Pickleable
        Pickleable = None
        try:
            restored = pickle.loads(pickled)
            assert_that(restored, has_entries({'a': 42}))
        finally:
            Pickleable = orig_class

    @raises(pickle.UnpicklingError)
    def test_access_to_unpickleable_raises_exception(self):
        obj = {'a': 42, 'obj': Pickleable(0)}
        pickled = pickle.dumps(obj)
        global Pickleable
        orig_class = Pickleable
        Pickleable = None
        try:
            restored = pickle.loads(pickled)
            restored['obj']
        finally:
            Pickleable = orig_class

    def test_if_unpickling_fails_for_one_dict_value_repr_can_still_be_accessed(
            self):
        obj = {'a': 42, 'b': {'obj': Pickleable(0)}}
        pickled = pickle.dumps(obj)
        global Pickleable
        orig_class = Pickleable
        Pickleable = None
        try:
            restored = pickle.loads(pickled)
            assert_that(
                restored.repr_of('b', 'obj'), is_(repr(obj['b']['obj'])))
        finally:
            Pickleable = orig_class
