from unittest import TestCase
import unittest.mock as mock
from utils import *


class TestSlurp(TestCase):
    # """Returns generator for accessing file content chunk-by-chunk"""
    def assert_slurp_correct(self, data: bytes, kwargs: dict, pbar_update_calls: list):
        with mock.patch('builtins.open', mock.mock_open(read_data=data)) as mock_open:
            pbar = mock.MagicMock()
            self.assertEqual(data, b''.join(slurp('foo_filename', pbar, **kwargs)))
            mock_open.assert_called_once_with('foo_filename', 'rb')
            self.assertEqual(pbar_update_calls, pbar.update.mock_calls)

    def test_slurp_empty(self):
        data = b''
        pbar_update_calls = []
        self.assert_slurp_correct(data, {}, pbar_update_calls)

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
        data = bytes(range(chunk_size*2))
        pbar_update_calls = [mock.call(chunk_size)]*2
        self.assert_slurp_correct(data, {'chunk_size': chunk_size}, pbar_update_calls)

    def test_slurp_not_divisible(self):
        chunk_size = 100
        data = bytes(range(int(chunk_size*1.5)))
        pbar_update_calls = [mock.call(chunk_size), mock.call(int(chunk_size * 0.5))]
        self.assert_slurp_correct(data, {'chunk_size': chunk_size}, pbar_update_calls)


class TestHashFile(TestCase):
    # """Returns checksum of file content"""
    # """Return checksums of two files, and a boolean whether or not these files have identical content.
    #
    # Can return 'not equal' even when hashes collide.
    # """
    xxhash_examples = [
        {"data": b'', "hexdigest": 'ef46db3751d8e999'},
        {"data": b'Test', "hexdigest": 'da83efc38a8922b4'},
        {"data": b'A bit longer test case...', "hexdigest": 'ddd42c49611733ca'},
        {"data": b'x'*4097, "hexdigest": 'a4233fac2072729d'},
        {"data": b'\x00'*8, "hexdigest": '34c96acdcadb1bbb'}
    ]

    def test_hash_file(self):
        for example in TestHashFile.xxhash_examples:
            with mock.patch('builtins.open', mock.mock_open(read_data=example['data'])) as mock_open:
                pbar = mock.MagicMock()
                self.assertEqual(example['hexdigest'], hash_file('foo_filename', pbar))
                mock_open.assert_called_once_with('foo_filename', 'rb')

    def test_hash_compare_files(self):
        for e1 in TestHashFile.xxhash_examples:
            for e2 in TestHashFile.xxhash_examples:
                mock_files = [mock.mock_open(read_data=e1['data']).return_value,
                              mock.mock_open(read_data=e2['data']).return_value]
                mock_opener = mock.mock_open()
                mock_opener.side_effect = mock_files
                with mock.patch('builtins.open', mock_opener) as mock_open:
                    pbar = mock.MagicMock()
                    a, b, equal = hash_compare_files('a', 'b', pbar)
                    self.assertEqual(e1['hexdigest'], a)
                    self.assertEqual(e2['hexdigest'], b)
                    self.assertEqual(e1['data'] == e2['data'], equal)
                    self.assertEqual([mock.call('a', 'rb'), mock.call('b', 'rb')], mock_open.mock_calls)
