from hamcrest.core.base_matcher import BaseMatcher


class ClassWith(BaseMatcher):
    def __init__(self, **attributes_to_match):
        self.attributes_to_match = attributes_to_match

    def _matches(self, item):
        for attr_name, attr_value in self.attributes_to_match.items():
            api_satisfied = hasattr(item, attr_name)
            if not api_satisfied:
                return False
            value_matches = getattr(item, attr_name) == attr_value
            if not value_matches:
                return False
        return True

    def describe_to(self, description):
        description.append_text(
            'class with attributes matching %s' % str(self.attributes_to_match))


class Empty(BaseMatcher):
    def _matches(self, item):
        if hasattr(item, '__len__'):
            return len(item) == 0
        elif hasattr(item, 'count'):
            return item.count() == 0
        raise TypeError('%s cannot be tested for emptiness.' % (
            type(item).__name__))

    def describe_to(self, description):
        description.append_text('empty')


def class_with(**attributes_to_match):
    return ClassWith(**attributes_to_match)


def empty():
    return Empty()
