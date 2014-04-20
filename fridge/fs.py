"""Provides the default Python implementation of file system access functions.
"""
from os import makedirs, mkdir, rename, symlink
try:
    from builtins import open
except ImportError:
    from __builtin__ import open
