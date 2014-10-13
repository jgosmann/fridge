"""Provides the default Python implementation of file system access functions.
"""
from os import chmod, makedirs, mkdir, rename, stat, unlink, utime, walk
from os.path import exists
from shutil import copy
try:
    from builtins import open
except ImportError:
    from __builtin__ import open
