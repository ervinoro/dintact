import os
import sys
import tempfile
import unittest.mock as mock
from io import StringIO
from pathlib import Path
from unittest import TestCase, main

from utils import (PathAwareGitWildMatchPattern, cp, hash_compare_files,
                   hash_file, hash_tree, rm, slurp, walk, yesno)


class TestSlurp(TestCase):
    # """Returns generator for accessing file content chunk-by-chunk"""
    def assert_slurp_correct(self, data: bytes, kwargs: dict, pbar_update_calls: list):
        with mock.patch('builtins.open', mock.mock_open(read_data=data)) as mock_open:
            pbar = mock.MagicMock()
            self.assertEqual(data, b''.join(slurp(Path('foo_filename'), pbar, **kwargs)))
            mock_open.assert_called_once_with(Path('foo_filename'), 'rb')
            self.assertEqual(pbar_update_calls, pbar.update.mock_calls)

    def test_slurp_empty(self):
        data = b''
        pbar_update_calls = []
        self.assert_slurp_correct(data, {}, pbar_update_calls)

    def test_slurp_ioerror(self):
        with mock.patch('builtins.open', mock.mock_open()) as mock_open:
            with mock.patch('sys.stderr', new=StringIO()) as mock_err:
                mock_open.side_effect = IOError()
                pbar = mock.MagicMock()
                list(slurp(Path('foo_filename'), pbar))
                pbar.update.assert_not_called()
                self.assertIn('foo_filename', mock_err.getvalue())

    def test_slurp_byte(self):
        data = b'\x42'
        pbar_update_calls = [mock.call(1)]
        self.assert_slurp_correct(data, {}, pbar_update_calls)

    def test_slurp_chunk(self):
        chunk_size = 100
        data = bytes(range(chunk_size))
        pbar_update_calls = [mock.call(chunk_size)]
        self.assert_slurp_correct(data, {'chunk_size': chunk_size}, pbar_update_calls)

    def test_slurp_divisible(self):
        chunk_size = 100
        data = bytes(range(chunk_size * 2))
        pbar_update_calls = [mock.call(chunk_size)] * 2
        self.assert_slurp_correct(data, {'chunk_size': chunk_size}, pbar_update_calls)

    def test_slurp_not_divisible(self):
        chunk_size = 100
        data = bytes(range(int(chunk_size * 1.5)))
        pbar_update_calls = [mock.call(chunk_size), mock.call(int(chunk_size * 0.5))]
        self.assert_slurp_correct(data, {'chunk_size': chunk_size}, pbar_update_calls)


class TestHashFile(TestCase):
    # """Returns checksum of file content"""
    # """Return checksums of two files, and a boolean whether or not these files have identical content.
    #
    # Can return 'not equal' even when hashes collide.
    # """
    xxhash_examples = [
        {"data": b'', "hexdigest": '99aa06d3014798d86001c324468d497f'},
        {"data": b'Test', "hexdigest": '391c8305c491690bc2da658a2d6348d5'},
        {"data": b'A bit longer test case...', "hexdigest": '5a4d96cb56d55d8d76aa74750d7e72a5'},
        {"data": b'x' * 4097, "hexdigest": 'df9a7a18b1942ff8531b09228bdbf2ef'},
        {"data": b'\x00' * 8, "hexdigest": '2c0a8a99dc147d5445c3b49d035665b2'}
    ]

    def test_hash_file(self):
        for example in TestHashFile.xxhash_examples:
            with mock.patch('builtins.open', mock.mock_open(read_data=example['data'])) as mock_open:
                pbar = mock.MagicMock()
                self.assertEqual(example['hexdigest'], hash_file(Path('foo_filename'), pbar))
                mock_open.assert_called_once_with(Path('foo_filename'), 'rb')

    def test_hash_compare_files(self):
        for e1 in TestHashFile.xxhash_examples:
            for e2 in TestHashFile.xxhash_examples:
                mock_files = [mock.mock_open(read_data=e1['data']).return_value,
                              mock.mock_open(read_data=e2['data']).return_value]
                mock_opener = mock.mock_open()
                mock_opener.side_effect = mock_files
                with mock.patch('builtins.open', mock_opener) as mock_open:
                    pbar = mock.MagicMock()
                    a, b, equal = hash_compare_files(Path('a'), Path('b'), pbar)
                    self.assertEqual(e1['hexdigest'], a)
                    self.assertEqual(e2['hexdigest'], b)
                    self.assertEqual(e1['data'] == e2['data'], equal)
                    self.assertEqual([mock.call(Path('a'), 'rb'), mock.call(Path('b'), 'rb')], mock_open.mock_calls)


class TestHashTree(TestCase):
    def test_unknown(self):
        with self.assertRaises(Exception):
            hash_tree(Path('asdf_path'), mock.MagicMock())


class TestCp(TestCase):
    def test_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            (tmpdir / 'a.txt').write_text("asdf_content")
            pbar = mock.MagicMock()
            cp(tmpdir / 'a.txt', tmpdir / 'b.txt', [], pbar)
            self.assertTrue((tmpdir / 'a.txt').exists())
            self.assertEqual("asdf_content", (tmpdir / 'a.txt').read_text())
            self.assertTrue((tmpdir / 'b.txt').exists())
            self.assertEqual("asdf_content", (tmpdir / 'b.txt').read_text())

    def test_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            (tmpdir / 'c').mkdir()
            (tmpdir / 'c' / 'a.txt').write_text("asdf_content")
            (tmpdir / 'c' / 'b.txt').write_text("bsdf_content")
            (tmpdir / 'c' / 'c.txt').write_text("csdf_content")
            (tmpdir / 'c' / '.gitignore').write_text("c.txt")
            pbar = mock.MagicMock()
            cp(tmpdir / 'c', tmpdir / 'd', [PathAwareGitWildMatchPattern('a.txt', tmpdir)], pbar)
            self.assertTrue((tmpdir / 'c').exists())
            self.assertEqual("asdf_content", (tmpdir / 'c' / 'a.txt').read_text())
            self.assertEqual("bsdf_content", (tmpdir / 'c' / 'b.txt').read_text())
            self.assertEqual("csdf_content", (tmpdir / 'c' / 'c.txt').read_text())
            self.assertEqual("c.txt", (tmpdir / 'c' / '.gitignore').read_text())
            self.assertTrue((tmpdir / 'd').exists())
            self.assertEqual("bsdf_content", (tmpdir / 'd' / 'b.txt').read_text())
            self.assertEqual("c.txt", (tmpdir / 'c' / '.gitignore').read_text())
            self.assertFalse((tmpdir / 'd' / 'a.txt').exists())
            self.assertFalse((tmpdir / 'd' / 'c.txt').exists())

    def test_non_existing(self):
        pbar = mock.MagicMock()
        with self.assertRaises(AssertionError):
            cp(Path('asdf_path'), Path('asdf_path'), [], pbar)


class TestRm(TestCase):
    def test_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            (tmpdir / 'a.txt').write_text("asdf_content")
            rm(tmpdir / 'a.txt')
            self.assertFalse((tmpdir / 'a.txt').exists())

    def test_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            (tmpdir / 'c').mkdir()
            (tmpdir / 'c' / 'a.txt').write_text("asdf_content")
            (tmpdir / 'c' / 'b.txt').write_text("bsdf_content")
            rm(tmpdir / 'c')
            self.assertFalse((tmpdir / 'c').exists())

    def test_non_existing(self):
        with self.assertRaises(AssertionError):
            rm(Path('asdf_path'))


class TestYesNo(TestCase):
    """Presents user with the prompt until it gets an answer"""

    def assert_yesno(self, user_input, expected, default=None):
        with mock.patch('sys.stdout', new_callable=StringIO) as mock_out:
            with mock.patch('sys.stdin', new=StringIO(user_input)):
                if default is None:
                    self.assertEqual(expected, yesno('asdf_prompt'))
                else:
                    self.assertEqual(expected, yesno('asdf_prompt', default))
                self.assertIn('asdf_prompt', mock_out.getvalue())
                self.assertIn('[y/n]', mock_out.getvalue().lower())
                if default is not None:
                    self.assertIn('[Y/n]' if default else '[y/N]', mock_out.getvalue())

    def test_yesno(self):
        self.assert_yesno('y\n', True)
        self.assert_yesno('Y\n', True)
        self.assert_yesno('yes\n', True)
        self.assert_yesno('YES\n', True)
        self.assert_yesno('Yes\n', True)

        self.assert_yesno('n\n', False)
        self.assert_yesno('N\n', False)
        self.assert_yesno('no\n', False)
        self.assert_yesno('NO\n', False)
        self.assert_yesno('NO\n', False)

        self.assert_yesno('asdf\nn\n', False)
        self.assert_yesno('asdf\ny\n', True)

        self.assert_yesno('\n', True, True)
        self.assert_yesno('\n', False, False)


class TestWalk(TestCase):
    def test_walk_ignorable(self):
        os.chdir(sys.path[0])
        self.assertEqual(sorted([
            Path('ignorable/b.txt'),
            Path('ignorable/c/e.txt'),
            Path('ignorable/f/g.txt')
        ]), sorted(list(walk(Path('ignorable'), []))))


if __name__ == "__main__":
    main()
