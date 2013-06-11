from hamcrest import equal_to
from hamcrest.core.base_matcher import BaseMatcher


class ClassWith(BaseMatcher):
    def __init__(self, **attributes_to_match):
        self.attributes_to_match = {}
        for attr_name, attr_value in attributes_to_match.items():
            if hasattr(attr_value, 'matches'):
                self.attributes_to_match[attr_name] = attr_value
            else:
                self.attributes_to_match[attr_name] = equal_to(attr_value)

    def _matches(self, item):
        for attr_name, attr_value in self.attributes_to_match.items():
            api_satisfied = hasattr(item, attr_name)
            if not api_satisfied:
                return False
            value_matches = attr_value.matches(getattr(item, attr_name))
            if not value_matches:
                return False
        return True

    def describe_to(self, description):
        description.append_text('class with attributes matching {')
        first = True
        for name, matcher in self.attributes_to_match.items():
            if not first:
                description.append_text(', ')
            first = False
            description.append_text(repr(name))
            description.append_text(': (')
            matcher.describe_to(description)
            description.append_text(')')
        description.append_text('}')


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
