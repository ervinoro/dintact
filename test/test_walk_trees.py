import os
import sys
import unittest
from pathlib import Path
from unittest import mock

from changes import *
from dintact import walk_trees


class TestWalkTrees(unittest.TestCase):
    def test_bundled_folder(self):
        os.chdir(sys.path[0])
        pbar = mock.MagicMock()
        changes = walk_trees(PurePath(), Index(Path('cold')), Path('hot'), Path('cold'), [], [], pbar)
        self.assertEqual(sorted([
            ModifiedCopied(PurePath('ModifiedCopied.txt'), 0),
            Modified(PurePath('Modified.txt'), 0),
            Corrupted(PurePath('Corrupted.txt'), 0),
            ModifiedCorrupted(PurePath('ModifiedCorrupted.txt'), 0),
            AddedCopied(PurePath('AddedCopied.txt'), 0),
            AddedAppeared(PurePath('AddedAppeared.txt'), 0),
            Lost(PurePath('Lost.txt'), 0),
            ModifiedLost(PurePath('ModifiedLost.txt'), 0),
            Added(PurePath('Added.txt'), 0),
            Removed(PurePath('Removed.txt'), 0),
            RemovedCorrupted(PurePath('RemovedCorrupted.txt'), 0),
            Appeared(PurePath('Appeared.txt'), 0),
            RemovedLost(PurePath('RemovedLost.txt'), 0),
            ModifiedLost(PurePath('ModifiedLost'), 0),
            Lost(PurePath('Lost'), 0),
            Added(PurePath('Added'), 0),
            RemovedCorrupted(PurePath('RemovedCorrupted'), 0),
            Removed(PurePath('Removed'), 0),
            Appeared(PurePath('Appeared'), 0),
            RemovedLost(PurePath('RemovedLost'), 0)
        ], key=repr), sorted(changes, key=repr))
