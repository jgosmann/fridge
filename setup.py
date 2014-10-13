#!/usr/bin/env python

from setuptools import setup
import os
import os.path
import shutil
import stat

# The test output of the system tests may contain symlinks to non-existing
# files which make distutils throw an exception (even though they are pruned).
test_output_dir = os.path.join(os.curdir, 'systemtests', 'test-output')
if os.path.exists(test_output_dir):
    for dirpath, dirnames, filenames in os.walk(test_output_dir):
        for filename in filenames:
            os.chmod(
                os.path.join(dirpath, filename), stat.S_IREAD | stat.S_IWRITE)
    shutil.rmtree(test_output_dir)

setup(
    name='fridge',
    version='0.1',
    author='Jan Gosmann',
    author_email='jan@hyper-world.de',
    packages=['fridge'],
    scripts=['bin/fridge'],
    provides=['fridge'],
)
