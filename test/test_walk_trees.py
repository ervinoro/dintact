import os
import sys
import unittest
from pathlib import Path, PurePath
from unittest import mock

from changes import (Added, AddedAppeared, AddedCopied, Appeared, Corrupted,
                     Lost, Modified, ModifiedCopied, ModifiedCorrupted,
                     ModifiedLost, Moved, Removed, RemovedCorrupted,
                     RemovedLost)
from dintact import find_moveds, ignore_index, walk_trees
from index import Index


class TestWalkTrees(unittest.TestCase):
    def test_bundled_folder(self):
        os.chdir(sys.path[0])
        pbar = mock.MagicMock()
        changes = walk_trees(
            PurePath(),
            Index(Path('cold')),
            Path('hot'),
            Path('cold'),
            pbar
        )
        ignore_index(changes)
        find_moveds(changes)
        self.assertEqual(sorted([
            ModifiedCopied(PurePath('ModifiedCopied.txt'), Index()),
            Modified(PurePath('Modified.txt'), Index()),
            Corrupted(PurePath('Corrupted.txt')),
            ModifiedCorrupted(PurePath('ModifiedCorrupted.txt'), Index()),
            AddedCopied(PurePath('AddedCopied.txt'), Index()),
            AddedAppeared(PurePath('AddedAppeared.txt'), Index()),
            Lost(PurePath('Lost.txt')),
            ModifiedLost(PurePath('ModifiedLost.txt'), Index()),
            Added(PurePath('Added.txt'), Index()),
            Removed(PurePath('Removed.txt'), '3c15f2cb2622b0c2d450322224329613'),
            RemovedCorrupted(PurePath('RemovedCorrupted.txt'), '3c15f2cb2622b0c2d450322224329613'),
            Appeared(PurePath('Appeared.txt')),
            RemovedLost(PurePath('RemovedLost.txt')),
            ModifiedLost(PurePath('ModifiedLost'), Index()),
            Lost(PurePath('Lost')),
            Added(PurePath('Added'), Index()),
            RemovedCorrupted(PurePath('RemovedCorrupted'), Index()),
            Removed(PurePath('Removed'), Index()),
            Appeared(PurePath('Appeared')),
            RemovedLost(PurePath('RemovedLost')),
            Moved(PurePath('Moved2.txt'), 'f5c0e7635de66b6379b7945d4c474ecd',
                  Removed(PurePath('Moved1.txt'), 'f5c0e7635de66b6379b7945d4c474ecd')),
            Moved(PurePath('Moved2'), Index(),
                  Removed(PurePath('Moved1'), Index())),
        ], key=repr), sorted(changes, key=repr))
