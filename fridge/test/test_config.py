#!/usr/bin/env python

from fridge.config import Config, FloatRangeScope, Option, Specification
import unittest


class TestConfig(unittest.TestCase):
    def test_allows_storage_and_retrieval_of_values(self):
        config = Config()
        config.root.root_level_value = 42
        config.root.nesting.a.value = 'nested'
        self.assertEqual(config.root.root_level_value, 42)
        self.assertEqual(config.root.nesting.a.value, 'nested')

    def test_validates_against_matching_specfication(self):
        spec = Specification(0, {
            'int_opt': Option(int),
            'every_type': Option(),
            'not_required': Option(required=False),
            'not_required_with_default': Option(default='def', required=False),
            'scope_check': {
                'float': Option(float, scope=FloatRangeScope(-2, 5.3)),
                'list': Option(int, scope=[3, 5, 8])
            }
        })

        config = Config()
        config.root.int_opt = 2
        config.root.every_type = True
        config.root.scope_check.float = 3
        config.root.scope_check.list = 5

        config.validate(spec)
        self.assertEqual(config.version, 0)
        self.assertEqual(config.root.not_required_with_default, 'def')

    # TODO test failing verifications


if __name__ == '__main__':
    unittest.main()
