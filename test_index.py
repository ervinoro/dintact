import os
from unittest import TestCase, mock
from pathlib import PurePath, Path

from index import Index


class Test(TestCase):
    def test_index_in_memory(self):
        index = Index()
        self.assertEqual(0, len(index))
        self.assertFalse(index.keys())

        index[PurePath('a')] = '1'
        self.assertEqual(1, len(index))
        self.assertIn(PurePath('a'), index)
        self.assertEqual('1', index[PurePath('a')])

        del index[PurePath('a')]
        self.assertEqual(0, len(index))
        self.assertFalse(index.keys())

        index[PurePath('a/b')] = '2'
        self.assertEqual(1, len(index))
        self.assertIn(PurePath('a/b'), index)
        self.assertEqual([PurePath('a/b')], list(index))
        self.assertEqual('2', index[PurePath('a/b')])
        self.assertEqual(1, len(index[PurePath('a')]))
        self.assertIn(PurePath('b'), index[PurePath('a')])
        self.assertEqual('2', index[PurePath('a')][PurePath('b')])

        del index[PurePath('a/b')]
        self.assertEqual(0, len(index))
        self.assertFalse(index.keys())

        index[PurePath('a')] = '3'
        self.assertEqual(1, len(index))
        self.assertIn(PurePath('a'), index)
        self.assertEqual('3', index[PurePath('a')])

        del index[PurePath('a')]
        self.assertEqual(0, len(index))
        self.assertFalse(index.keys())

        subindex = Index()
        subindex[PurePath('c')] = '4'
        index[PurePath('d')] = subindex
        self.assertEqual(1, len(index))
        self.assertIn(PurePath('d/c'), index)
        self.assertEqual('4', index[PurePath('d/c')])
        self.assertEqual(1, len(index[PurePath('d')]))
        self.assertIn(PurePath('c'), index[PurePath('d')])
        self.assertEqual('4', index[PurePath('d')][PurePath('c')])

        del index[PurePath('d')]
        self.assertEqual(0, len(index))
        self.assertFalse(index.keys())

        index[PurePath('x')] = '5'
        index[PurePath('y/x')] = '6'
        self.assertEqual({PurePath('x'), PurePath('y/x')}, set(index))

    @staticmethod
    def index_del(i, p):
        del i[PurePath(p)]

    def test_index_in_memory_exceiptions(self):
        index = Index()
        self.assertRaises(KeyError, lambda: Test.index_del(index, 'a'))
        self.assertRaises(KeyError, lambda: index[PurePath('a')])
        self.assertRaises(TypeError, lambda: index.update([(PurePath('a'), 1)]))

    def assert_index_file(self, file: str, index: Index):
        self._assert_index_file(file, index, exists=True)
        self._assert_index_file(file, index, exists=False)

    def _assert_index_file(self, file: str, index: Index, exists: bool = True):
        p: Path = Path('foo_filename')
        i: Index
        with mock.patch.object(Path, 'touch') as mock_touch:
            with mock.patch.object(Path, 'exists') as mock_exists:
                mock_exists.return_value = exists
                with mock.patch('io.open', mock.mock_open(read_data=file)) as mock_open:
                    i = Index(p)
                    self.assertEqual(index, i)
                    mock_open.assert_called_once()
                    self.assertEqual(p / "index.txt", mock_open.call_args[0][0])
            if not exists:
                mock_touch.assert_called_once()

        with mock.patch('io.open', mock.mock_open()) as mock_open:
            i.store()
            mock_open.assert_called_once()
            self.assertEqual(p / "index.txt", mock_open.call_args[0][0])
            self.assertEqual(set(file.split('\n')),
                             set(''.join(c.args[0] for c in mock_open().write.mock_calls).split('\n')))

    def test_empty_file(self):
        self.assert_index_file("", Index())

    def test_single_file(self):
        i = Index()
        i[PurePath('a')] = '1'
        self.assert_index_file("1 a\n", i)

    def test_subdir_file(self):
        i = Index()
        i[PurePath('a')] = '1'
        i[PurePath('c/d')] = '2'
        self.assert_index_file("1 a\n2 c/d\n", i)
