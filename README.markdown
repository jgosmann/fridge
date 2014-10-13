[![Build Status](https://travis-ci.org/jgosmann/fridge.svg?branch=master)](https://travis-ci.org/jgosmann/fridge)
[![Coverage Status](https://img.shields.io/coveralls/jgosmann/fridge.svg)](https://coveralls.io/r/jgosmann/fridge?branch=master)

Thinking, playing around and researching I came to the conclusion that I first
of all need a content addressable file system (CAFS) tool like
[boar](http://www.boarvcs.com/) for scientific data. Then I might build on that
to add more logbook like functions like provided by
[Sumatra](http://neuralensemble.org/sumatra/). Or, maybe, it turns out that
Sumatra in addition with my CAFS fulfills my needs.

The main feature I am missing in boar is having distributed archives (like in
git with push and pull). Also, I think, the CLI can be simplified (to many
commands in boar need the ```--repo``` option.

Wishlist of Features
--------------------

* Distributed
* Atomic operations
* Integrity verification
* Fast
* Not limited by file size
* Some kind of branching or tagging
* Tracking of file locations?
* Ignore mechanism
* Python API
* Pruning
* checkout multiple snapshots at the same time
* Easy restore of data even without fridge.
* Get specific files?

Questions
---------

* What hash function can be used?
  - Should be fast.
  - Are accidental collisions a problem?
  - Are attacker provoking collisions a problem?
* Symlinking to files or creating copies?
  - Symlinking is faster, but might be harmful to data.
* What concept of branches/tags or the like make sense?
  - Tags should definitely be ok? But how to merge name clashes? 
    - Let user resolve by deciding for either one or renaming either one?
    - Store by origin?
  - Branches store by origin like git and possibility to checkout.
    - How to handle checkout on dirty working dir?

Commands
--------

    fridge init <name?>
    fridge commit
    fridge checkout <id> <target>
    fridge log
    fridge whence <file>  # find out how/which commit created file
    fridge verify

Objects
-------

* Blobs
* Trees? Snapshot?
  - Snapshot with complete list
* Commits?
  - Should not point back to a parent commit with original versions of changed
    files. We are not storing any diffs! But might be helpful anyways?
  - Should point back to commits providing unchanged files in some way ...
  - Should contain author and computer info
  - Pointing to one snapshot and one changeset listing add/remove/modified?
