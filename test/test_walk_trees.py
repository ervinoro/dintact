import os
import sys
import unittest
from pathlib import Path, PurePath
from unittest import mock

from changes import (Added, AddedAppeared, AddedCopied, Appeared, Corrupted,
                     Lost, Modified, ModifiedCopied, ModifiedCorrupted,
                     ModifiedLost, Removed, RemovedCorrupted, RemovedLost)
from dintact import walk_trees
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
            Removed(PurePath('Removed.txt')),
            RemovedCorrupted(PurePath('RemovedCorrupted.txt')),
            Appeared(PurePath('Appeared.txt')),
            RemovedLost(PurePath('RemovedLost.txt')),
            ModifiedLost(PurePath('ModifiedLost'), 0, [], Index()),
            Lost(PurePath('Lost'), 0, []),
            Added(PurePath('Added'), 0, [], Index()),
            RemovedCorrupted(PurePath('RemovedCorrupted')),
            Removed(PurePath('Removed')),
            Appeared(PurePath('Appeared')),
            RemovedLost(PurePath('RemovedLost'))
        ], key=repr), sorted(changes, key=repr))
