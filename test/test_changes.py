from pathlib import Path, PurePath
from unittest import TestCase
from unittest.mock import MagicMock, patch

from changes import (Added, AddedAppeared, AddedCopied, Appeared, Change,
                     Corrupted, Lost, Modified, ModifiedCopied,
                     ModifiedCorrupted, ModifiedLost, Removed,
                     RemovedCorrupted, RemovedLost)
from index import Index


class TestCommon(TestCase):
    def test_str(self):
        change = Change(PurePath('asdf_name'), 0)
        change.has_been = 'asdf_has_been'
        change.action = 'asfd_action'
        self.assertIn('asdf_name', str(change))
        self.assertIn('asdf_has_been', str(change))
        self.assertIn('asfd_action', str(change))

    def test_eq(self):
        a = Change(PurePath('asdf_name'), 0)
        b = Change(PurePath('asdf_name'), 0)
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))

        a = Change(PurePath('asdf_name'), 0)
        b = Change(PurePath('asdf_name'), 1)
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))

        a = Change(PurePath('asdf_name'), 0)
        b = Change(PurePath('asdf_name2'), 0)
        self.assertNotEqual(a, b)
        self.assertNotEqual(hash(a), hash(b))

        a = Removed(PurePath('asdf_name'), 0)
        b = RemovedCorrupted(PurePath('asdf_name'), 0)
        self.assertNotEqual(a, b)
        self.assertNotEqual(hash(a), hash(b))

        self.assertNotEqual(a, 10)
        self.assertNotEqual(hash(a), hash(10))


@patch('changes.rm')
@patch('changes.cp')
class TestApplies(TestCase):
    def test_added_copied(self, cp, rm):  # HCI: 1 1 0, action: add it to cold index
        h, c, n = Path('hot'), Path('cold'), Path('name')
        change = AddedCopied(n, 'x')
        i = Index()
        pbar = MagicMock()
        change.apply(h, c, i, pbar)
        cp.assert_not_called()
        rm.assert_not_called()
        self.assertEqual('x', i[n])

    def test_modified_copied(self, cp, rm):  # HCI: 1 1 2, action: add it to cold index
        h, c, n = Path('hot'), Path('cold'), Path('name')
        change = ModifiedCopied(n, 'x')
        i = Index()
        i[n] = 'y'
        pbar = MagicMock()
        change.apply(h, c, i, pbar)
        cp.assert_not_called()
        rm.assert_not_called()
        self.assertEqual('x', i[n])

    def test_added(self, cp, rm):  # HCI: 1 0 0, action: copy it to cold backup
        h, c, n = Path('hot'), Path('cold'), Path('name')
        change = Added(n, 0, [], 'x')
        i = Index()
        pbar = MagicMock()
        change.apply(h, c, i, pbar)
        cp.assert_called_once_with(h / n, c / n, [], pbar)
        rm.assert_not_called()
        self.assertEqual('x', i[n])

    def test_modified_lost(self, cp, rm):  # HCI: 1 0 2, action: copy it to cold backup
        h, c, n = Path('hot'), Path('cold'), Path('name')
        change = ModifiedLost(n, 0, [], 'x')
        i = Index()
        i[n] = 'y'
        pbar = MagicMock()
        change.apply(h, c, i, pbar)
        cp.assert_called_once_with(h / n, c / n, [], pbar)
        rm.assert_not_called()
        self.assertEqual('x', i[n])

    def test_lost(self, cp, rm):  # HCI: 1 0 1, action: copy it to cold backup
        h, c, n = Path('hot'), Path('cold'), Path('name')
        change = Lost(n, 0, [])
        i = Index()
        pbar = MagicMock()
        change.apply(h, c, i, pbar)
        cp.assert_called_once_with(h / n, c / n, [], pbar)
        rm.assert_not_called()
        self.assertNotIn(n, i)

    def test_removed(self, cp, rm):  # HCI: 0 1 1, action: remove it from cold backup
        h, c, n = Path('hot'), Path('cold'), Path('name')
        change = Removed(n)
        i = Index()
        i[n] = 'x'
        pbar = MagicMock()
        change.apply(h, c, i, pbar)
        cp.assert_not_called()
        rm.assert_called_once_with(c / n)
        self.assertNotIn(n, i)

    def test_removed_corrupted(self, cp, rm):  # HCI: 0 1 2, action: remove it from cold backup
        h, c, n = Path('hot'), Path('cold'), Path('name')
        change = RemovedCorrupted(n)
        i = Index()
        i[n] = 'y'
        pbar = MagicMock()
        change.apply(h, c, i, pbar)
        cp.assert_not_called()
        rm.assert_called_once_with(c / n)
        self.assertNotIn(n, i)

    def test_modified(self, cp, rm):  # HCI: 2 1 1, action: copy it to cold backup
        h, c, n = Path('hot'), Path('cold'), Path('name')
        change = Modified(n, 0, [], 'x')
        i = Index()
        i[n] = 'y'
        pbar = MagicMock()
        change.apply(h, c, i, pbar)
        cp.assert_called_once_with(h / n, c / n, [], pbar)
        rm.assert_called_once_with(c / n)
        self.assertEqual('x', i[n])

    def test_corrupted(self, cp, rm):  # HCI: 1 2 1, action: copy it to cold backup
        h, c, n = Path('hot'), Path('cold'), Path('name')
        change = Corrupted(n, 0, [])
        i = Index()
        pbar = MagicMock()
        change.apply(h, c, i, pbar)
        cp.assert_called_once_with(h / n, c / n, [], pbar)
        rm.assert_called_once_with(c / n)
        self.assertNotIn(n, i)

    def test_modified_corrupted(self, cp, rm):  # HCI: 1 2 3, action: copy it to cold backup
        h, c, n = Path('hot'), Path('cold'), Path('name')
        change = ModifiedCorrupted(n, 0, [], 'x')
        i = Index()
        i[n] = 'y'
        pbar = MagicMock()
        change.apply(h, c, i, pbar)
        cp.assert_called_once_with(h / n, c / n, [], pbar)
        rm.assert_called_once_with(c / n)
        self.assertEqual('x', i[n])

    def test_added_appeared(self, cp, rm):  # HCI: 1 2 0, action: overwrite from hot to cold
        h, c, n = Path('hot'), Path('cold'), Path('name')
        change = AddedAppeared(n, 0, [], 'x')
        i = Index()
        pbar = MagicMock()
        change.apply(h, c, i, pbar)
        cp.assert_called_once_with(h / n, c / n, [], pbar)
        rm.assert_called_once_with(c / n)
        self.assertEqual('x', i[n])

    def test_appeared(self, cp, rm):  # HCI: 0 1 0, action: delete if from cold backup
        h, c, n = Path('hot'), Path('cold'), Path('name')
        change = Appeared(n)
        i = Index()
        pbar = MagicMock()
        change.apply(h, c, i, pbar)
        cp.assert_not_called()
        rm.assert_called_once_with(c / n)
        self.assertNotIn(n, i)

    def test_removed_lost(self, cp, rm):  # HCI: 0 0 1, action: remove it from index
        h, c, n = Path('hot'), Path('cold'), Path('name')
        change = RemovedLost(n)
        i = Index()
        i[n] = 'x'
        pbar = MagicMock()
        change.apply(h, c, i, pbar)
        cp.assert_not_called()
        rm.assert_not_called()
        self.assertNotIn(n, i)
