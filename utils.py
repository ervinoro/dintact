import itertools
import os
import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import Generator, Tuple, Union, List

import pathspec
import xxhash
from tqdm import tqdm

from index import Index

# noinspection PyShadowingBuiltins
print = tqdm.write

CHUNK_SIZE: int = 4096


class PathAwareGitWildMatchPattern(pathspec.patterns.GitWildMatchPattern):
    def __init__(self, pattern, root: Path, include=None):
        super().__init__(pattern, include)
        self.root = root


def is_relevant(p: Path, rules: List[PathAwareGitWildMatchPattern]) -> bool:
    if not (p.is_file() or any(p.iterdir())):
        return False
    ignored = False
    for rule in rules:
        if rule.include is not None:
            relpath = str(PurePosixPath(p.relative_to(rule.root)))
            if relpath in rule.match((relpath,)):
                ignored = rule.include
    return not ignored


def walk(p: Path, rules: List[PathAwareGitWildMatchPattern]) -> Generator[Path, None, None]:
    if is_relevant(p, rules):
        if p.is_file():
            yield p
        elif p.is_dir():
            if (p / '.gitignore').exists():
                with open(p / '.gitignore', 'r') as f:
                    for line in f:
                        rules.append(PathAwareGitWildMatchPattern(line, p))
            for c in p.iterdir():
                for cc in walk(c, rules[:]):
                    yield cc
        else:  # pragma: no cover
            raise Exception(f"Unknown thing {p}")


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
    x = xxhash.xxh3_128()
    for chunk in slurp(path, pbar):
        x.update(chunk)
    return x.hexdigest()


def hash_compare_files(a_path: Path, b_path: Path, pbar: tqdm) -> Tuple[str, str, bool]:
    """Return checksums of two files, and a boolean whether or not these files have identical content.

    Can return 'not equal' even when hashes collide.
    """
    a_x = xxhash.xxh3_128()
    b_x = xxhash.xxh3_128()
    eq = True
    for chunk in itertools.zip_longest(slurp(a_path, pbar), slurp(b_path, pbar)):
        a_x.update(chunk[0] or b'')
        b_x.update(chunk[1] or b'')
        if chunk[0] != chunk[1]:
            eq = False
    return a_x.hexdigest(), b_x.hexdigest(), eq


def hash_tree(path: Path, pbar: tqdm) -> Tuple[Union[Index, str], int]:
    """Calculate index of a path recursively"""
    i = Index()
    size = 0
    if path.is_dir():
        for f in path.rglob("*"):
            if f.is_file():
                i[f.relative_to(path)] = hash_file(f, pbar)
                size += f.stat().st_size
    elif path.is_file():
        i = hash_file(path, pbar)
        size += path.stat().st_size
    else:
        raise NotImplementedError(f"Unknown {path}")
    return i, size


def cp(source: os.PathLike, target: os.PathLike):
    assert os.path.exists(source), "can't copy, doesn't exist (internal error)"
    assert not os.path.exists(target), "remove explicitly first (internal error)"
    if os.path.isdir(source):
        shutil.copytree(source, target)
    elif os.path.isfile(source):
        shutil.copyfile(source, target)
    else:  # pragma: no cover
        raise Exception(f"Unknown thing {source}")


def rm(target: os.PathLike):
    assert os.path.exists(target), "can't remove, doesn't exist (internal error)"
    if os.path.isdir(target):
        shutil.rmtree(target)
    elif os.path.isfile(target):
        os.remove(target)
    else:  # pragma: no cover
        raise Exception(f"Unknown thing {target}")


def yesno(prompt: str, default: bool = True) -> bool:
    """Presents user with the prompt until it gets an answer"""
    while True:
        answer = input(prompt + (" [Y/n] " if default else " [y/N] "))
        if answer.strip() == "":
            return default
        if answer.strip().lower() in ["y", "yes"]:
            return True
        if answer.strip().lower() in ["n", "no"]:
            return False
