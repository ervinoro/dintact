from pathlib import PurePath, Path
from unittest import TestCase, mock

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

    def test_multipart(self):
        index = Index()
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

    def test_multipart_single_del(self):
        index = Index()
        index[PurePath('a/b')] = '2'
        index[PurePath('a/c')] = '3'

        del index[PurePath('a/b')]
        self.assertEqual(1, len(index))
        self.assertNotIn(PurePath('a/b'), index)
        self.assertEqual('3', index[PurePath('a/c')])

    def test_self(self):
        i = Index()
        i[PurePath('a')] = '1'
        self.assertEqual(i, i[PurePath()])
        with self.assertRaises(ValueError):
            i[PurePath()] = '2'
        with self.assertRaises(ValueError):
            del i[PurePath()]

    def test_asdf(self):
        index = Index()
        index[PurePath('a')] = '3'
        self.assertEqual(1, len(index))
        self.assertIn(PurePath('a'), index)
        self.assertEqual('3', index[PurePath('a')])

        del index[PurePath('a')]
        self.assertEqual(0, len(index))
        self.assertFalse(index.keys())

    def test_subindex(self):
        index = Index()
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

    def test_keyset(self):
        index = Index()
        index[PurePath('x')] = '5'
        index[PurePath('y/x')] = '6'
        self.assertEqual({PurePath('x'), PurePath('y/x')}, set(index))

    def test_update(self):
        i = Index()
        i[PurePath('a')] = '1'
        i[PurePath('b')] = '2'
        i[PurePath('c/d')] = '3'
        i[PurePath('c/e')] = '4'

        j = Index()
        j[PurePath('b')] = 'x'
        j[PurePath('c/e')] = 'y'

        i.update(j)

        self.assertEqual('1', i[PurePath('a')])
        self.assertEqual('x', i[PurePath('b')])
        self.assertEqual('3', i[PurePath('c/d')])
        self.assertEqual('y', i[PurePath('c/e')])

    def test_repr(self):
        i = Index()
        i[PurePath('b')] = 'x'
        i[PurePath('c/e')] = 'y'

        self.assertEqual("Index(files: {PureWindowsPath('b'): 'x'}, "
                         "dirs: {PureWindowsPath('c'): Index(files: {PureWindowsPath('e'): 'y'}, dirs: {})})",
                         repr(i))

    def test_eq(self):
        i = Index()
        i[PurePath('b')] = 'x'
        i[PurePath('c/e')] = 'y'

        j = Index()
        j[PurePath('b')] = 'x'
        j[PurePath('c/e')] = 'y'
        self.assertEqual(i, j)

        j = Index()
        j[PurePath('b')] = 'z'
        j[PurePath('c/e')] = 'y'
        self.assertNotEqual(i, j)

        j = Index()
        j[PurePath('b')] = 'x'
        j[PurePath('c/e')] = 'z'
        self.assertNotEqual(i, j)

        j = Index()
        j[PurePath('z')] = 'x'
        j[PurePath('c/e')] = 'y'
        self.assertNotEqual(i, j)

        j = Index()
        j[PurePath('b')] = 'x'
        j[PurePath('z/e')] = 'y'
        self.assertNotEqual(i, j)

        j = Index()
        j[PurePath('b')] = 'x'
        j[PurePath('c/z')] = 'y'
        self.assertNotEqual(i, j)

        self.assertNotEqual(i, 10)

    def test_iterdir(self):
        index = Index()
        index[PurePath('a/b')] = '1'
        index[PurePath('c')] = '2'
        self.assertEqual({PurePath('a'), PurePath('c')}, set(index.iterdir()))

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

    def test_multiple_folders(self):
        i = Index()
        i[PurePath('a/b')] = '1'
        i[PurePath('c/d')] = '2'
        self.assert_index_file("1 a/b\n2 c/d\n", i)
