import itertools
import os
import shutil
import sys
from pathlib import Path
from typing import Generator, Tuple

from tqdm import tqdm
import xxhash

CHUNK_SIZE: int = 4096


def slurp(filename: Path, pbar: tqdm, chunk_size: int = CHUNK_SIZE) -> Generator[bytes, None, None]:
    """Returns generator for accessing file content chunk-by-chunk"""
    try:
        with open(filename, 'rb') as f:
            for chunk in iter(lambda: f.read(chunk_size), b''):
                yield chunk
                pbar.update(len(chunk))
    except IOError:
        print(f"Unable to open '{filename}'.", file=sys.stderr)


def hash_file(path: Path, pbar: tqdm) -> str:
    """Returns checksum of file content"""
    x = xxhash.xxh64()
    for chunk in slurp(path, pbar):
        x.update(chunk)
    return x.hexdigest()


def hash_compare_files(a_path: Path, b_path: Path, pbar: tqdm) -> Tuple[str, str, bool]:
    """Return checksums of two files, and a boolean whether or not these files have identical content.

    Can return 'not equal' even when hashes collide.
    """
    a_x = xxhash.xxh64()
    b_x = xxhash.xxh64()
    eq = True
    for chunk in itertools.zip_longest(slurp(a_path, pbar), slurp(b_path, pbar)):
        a_x.update(chunk[0] or b'')
        b_x.update(chunk[1] or b'')
        if chunk[0] != chunk[1]:
            eq = False
    return a_x.hexdigest(), b_x.hexdigest(), eq


def cp(source: os.PathLike, target: os.PathLike):
    assert not os.path.exists(target), "remove explicitly first (internal error)"
    if os.path.isdir(source):
        shutil.copytree(source, target)
    elif os.path.isfile(source):
        shutil.copyfile(source, target)
    else:
        raise Exception(f"Unknown thing {source}")


def rm(target: os.PathLike):
    assert os.path.exists(target), "can't remove, doesn't exist (internal error)"
    if os.path.isdir(target):
        shutil.rmtree(target)
    elif os.path.isfile(target):
        os.remove(target)
    else:
        raise Exception(f"Unknown thing {target}")


def yesno(prompt: str, default: bool = True) -> bool:
    while True:
        answer = input(prompt + (" [Y/n] " if default else " [y/N] "))
        if answer.strip() == "":
            return default
        if answer.strip().lower() in ["y", "yes"]:
            return True
        if answer.strip().lower() in ["n", "no"]:
            return False
