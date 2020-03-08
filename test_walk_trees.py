import unittest
from pathlib import PurePath, Path
from unittest import mock

from dintact import walk_trees
from index import Index
from changes import *


class TestWalkTrees(unittest.TestCase):
    def test_something(self):
        pbar = mock.MagicMock()
        changes = walk_trees(PurePath(), Index(Path('test/cold')), Path('test/hot'), Path('test/cold'), pbar)
        self.assertEqual({
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
            RemovedLost(PurePath('RemovedLost.txt'), 0)
        }, set(changes))
