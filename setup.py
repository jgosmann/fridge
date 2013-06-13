#!/usr/bin/env python

from setuptools import setup, find_packages


# FIXME add dependencies (sqlalchemy, nose)
setup(
    name='fridge',
    version='0.1',
    description='Fridge stores your scientific simulation results ' +
    'and keeps them fresh.',
    author='Jan Gosmann',
    author_email='jan@hyper-world.de',
    # url= ... TODO
    packages=find_packages(),
    scripts=['bin/fridge'])
