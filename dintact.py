#!/usr/bin/env python3
import argparse
import os
import sys
from typing import Generator, Callable, TypeVar

import xxhash
from tqdm import tqdm

# noinspection PyShadowingBuiltins
print = tqdm.write

CHUNK_SIZE: int = 4096


def slurp(filename: str, pbar: tqdm, chunk_size: int = CHUNK_SIZE) -> Generator[bytes, None, None]:
    try:
        with open(filename, 'rb') as f:
            for chunk in iter(lambda: f.read(chunk_size), b''):
                yield chunk
                pbar.update(len(chunk))
    except IOError:
        print(f"Unable to open '{filename}'.", file=sys.stderr)


def hash_file(path: str, pbar: tqdm) -> str:
    x = xxhash.xxh64()
    for chunk in slurp(path, pbar):
        x.update(chunk)
    return x.hexdigest()


A = TypeVar("A")
def walk_path(path: str, generator: Callable[[str], A]) -> Generator[A, None, None]:
    if os.path.isfile(path):
        yield generator(path)
    elif os.path.isdir(path):
        for root, _, files in os.walk(path):
            for file in files:
                yield generator(os.path.join(root, file))
    else:
        print(f"Dafuq is this: '{path}'?", file=sys.stderr)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--add", action="append", default=[], help="Add new folder to index")
    parser.add_argument("index", help="File where archive index is stored")
    args = parser.parse_args()

    # Read in index
    index = {}
    if not os.path.exists(args.index):
        open(args.index, 'w').close()
    with open(args.index, 'r') as index_file:
        for line in index_file:
            if not line:
                continue
            h, p = line.strip().split(" ", 1)
            index[p] = h

    # Set up progress bar
    total = (
            sum([sum(walk_path(added, lambda p: os.path.getsize(p))) for added in args.add]) +
            sum([os.path.getsize(p) for p in index.keys()])
    )
    with tqdm(total=total, unit="B", unit_scale=True) as pbar:

        # Add new files to index
        with open(args.index, 'a') as index_file:
            for added in args.add:
                for h, p in walk_path(added, lambda p: (hash_file(p, pbar), p)):
                    if p in index:
                        print(f"File {p} already added!", file=sys.stderr)
                    else:
                        index_file.write(f"{h} {p}\n")

        # Check existing files in index
        for p, h in index.items():
            if h != hash_file(p, pbar):
                print(f"Verification failed: '{p}'.", file=sys.stderr)
