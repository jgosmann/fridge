#!/bin/sh

set -e

VAGRANT_TOX='/cygdrive/c/Python27/Scripts/tox'
VAGRANT_PYPATH='/cygdrive/c/Python27/:/cygdrive/c/Python33/:/cygdrive/c/Python34'

vagrant up
vagrant rsync
vagrant ssh -c "cd /vagrant && PATH=$VAGRANT_PYPATH $VAGRANT_TOX"
