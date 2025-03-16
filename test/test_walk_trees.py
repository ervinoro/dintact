import os
import sys
import unittest
from pathlib import Path, PurePath
from unittest import mock

from changes import (Added, AddedAppeared, AddedCopied, Appeared, Corrupted,
                     Lost, Modified, ModifiedCopied, ModifiedCorrupted,
                     ModifiedLost, Moved, Removed, RemovedCorrupted,
                     RemovedLost)
from dintact import find_moveds, walk_trees
from index import Index
from utils import root_rules


class TestWalkTrees(unittest.TestCase):
    def test_bundled_folder(self):
        os.chdir(sys.path[0])
        pbar = mock.MagicMock()
        changes = walk_trees(
            PurePath(),
            Index(Path('cold')),
            Path('hot'),
            Path('cold'),
            root_rules(Path('hot')),
            root_rules(Path('cold')),
            pbar
        )
        find_moveds(changes)
        self.assertEqual(sorted([
            ModifiedCopied(PurePath('ModifiedCopied.txt'), Index()),
            Modified(PurePath('Modified.txt'), 0, [], Index()),
            Corrupted(PurePath('Corrupted.txt'), 0, []),
            ModifiedCorrupted(PurePath('ModifiedCorrupted.txt'), 0, [], Index()),
            AddedCopied(PurePath('AddedCopied.txt'), Index()),
            AddedAppeared(PurePath('AddedAppeared.txt'), 0, [], Index()),
            Lost(PurePath('Lost.txt'), 0, []),
            ModifiedLost(PurePath('ModifiedLost.txt'), 0, [], Index()),
            Added(PurePath('Added.txt'), 0, [], Index()),
            Removed(PurePath('Removed.txt'), '3c15f2cb2622b0c2d450322224329613'),
            RemovedCorrupted(PurePath('RemovedCorrupted.txt'), '3c15f2cb2622b0c2d450322224329613'),
            Appeared(PurePath('Appeared.txt')),
            RemovedLost(PurePath('RemovedLost.txt')),
            ModifiedLost(PurePath('ModifiedLost'), 0, [], Index()),
            Lost(PurePath('Lost'), 0, []),
            Added(PurePath('Added'), 0, [], Index()),
            RemovedCorrupted(PurePath('RemovedCorrupted'), Index()),
            Removed(PurePath('Removed'), Index()),
            Appeared(PurePath('Appeared')),
            RemovedLost(PurePath('RemovedLost')),
            Moved(PurePath('Moved2.txt'), 0, [], 'f5c0e7635de66b6379b7945d4c474ecd',
                  Removed(PurePath('Moved1.txt'), 'f5c0e7635de66b6379b7945d4c474ecd')),
            Moved(PurePath('Moved2'), 0, [], Index(),
                  Removed(PurePath('Moved1'), Index())),
        ], key=repr), sorted(changes, key=repr))
