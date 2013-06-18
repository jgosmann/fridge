from hamcrest import any_of, assert_that, contains, equal_to, has_entries, \
    instance_of, is_
from nose.tools import raises
from fridge.lazyPickle import lazify
try:
    from unittest.mock import MagicMock
except:
    from mock import MagicMock
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

    @raises(pickle.UnpicklingError, TypeError)
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

    @raises(pickle.UnpicklingError, TypeError)
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

    @raises(pickle.PicklingError, TypeError)
    def test_raises_exception_on_failed_pickling(self):
        obj = {'a': 42, 'b': lambda: None, 'c': 23}
        lazify(obj)

    def test_if_own_error_handler_provided_it_is_used_instead_of_exception(
            self):
        onerror = MagicMock()
        obj = {'a': 42, 'b': lambda: None, 'c': 23}
        lazify(obj, onerror)
        assert_that(len(onerror.call_args_list), is_(1))
        assert_that(
            onerror.call_args_list[0][0], contains(any_of(
                instance_of(pickle.PicklingError), instance_of(TypeError))))

    def test_if_own_error_handler_its_return_value_is_used(self):
        onerror = MagicMock()
        onerror.return_value = 'pickling failed'
        obj = {'a': 42, 'b': lambda: None, 'c': 23}
        lazified = lazify(obj, onerror)
        assert_that(lazified['a'].retrieve(), is_(42))
        assert_that(lazified['b'].pickle, is_(equal_to(onerror.return_value)))
        assert_that(lazified['c'].retrieve(), is_(23))
