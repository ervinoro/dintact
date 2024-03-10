import itertools
import os
import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import Generator, List, Optional, Tuple, Union

import pathspec
import xxhash
from tqdm import tqdm

from DirEntryPath import DirEntryPath
from index import Index

# noinspection PyShadowingBuiltins
print = tqdm.write

GITIGNORE = '.gitignore'
CHUNK_SIZE: int = 4096


class PathAwareGitMatchPattern(pathspec.patterns.GitWildMatchPattern):
    def __init__(self, pattern, root: Path, include=None):
        super().__init__(pattern, include)
        self.root = root


def root_rules(path: Path) -> List[PathAwareGitMatchPattern]:
    return [PathAwareGitMatchPattern(Index.FILENAME, path)]


def add_path_rules(path: Path, rules: List[PathAwareGitMatchPattern]) -> None:
    if (path / GITIGNORE).exists():
        with open(path / GITIGNORE, 'r') as f:
            rules.extend(map(lambda r: PathAwareGitMatchPattern(r, path), f.read().splitlines()))


def add_scandir_rules(path: Path, children:  list[os.DirEntry[str]], rules: List[PathAwareGitMatchPattern]):
    gitignore = next((x for x in children if x.name == GITIGNORE), None)
    if gitignore:
        with open(gitignore.path, 'r') as f:
            rules.extend(map(lambda r: PathAwareGitMatchPattern(r, path), f.read().splitlines()))


def is_relevant(path: Path, rules: List[PathAwareGitMatchPattern], skip_first_check: bool = False) -> bool:
    if not skip_first_check and not (path.is_file() or any(path.iterdir())):
        return False
    ignored = False
    for rule in rules:
        if rule.include is not None:
            rel_path = str(PurePosixPath(path.relative_to(rule.root)))
            if path.is_dir():
                rel_path += '/'  # https://bugs.python.org/issue21039
            if rule.match_file(rel_path):
                ignored = rule.include
    return not ignored


def walk(path: Path, rules: List[PathAwareGitMatchPattern], pbar: Optional[tqdm] = None) -> Generator[Path, None, None]:
    if pbar:
        pbar.update()
    if not is_relevant(path, rules, True):
        if pbar and path.is_dir():
            pbar.update(sum([len(dirs) + len(files) for _, dirs, files in os.walk(path)]))
        return
    if path.is_file():
        yield path
    elif path.is_dir():
        children = list(os.scandir(path))
        if not children:
            return
        add_scandir_rules(path, children, rules)
        for child in children:
            for grandchild_path in walk(DirEntryPath(child), rules[:], pbar):
                yield grandchild_path
    else:  # pragma: no cover
        raise ValueError(f"Unknown thing {dir}")


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
    """Return checksums of two files, and a boolean indicating if these files have identical content.

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
    if path.is_dir():
        i = Index()
        size = 0
        for f in path.rglob("*"):
            if f.is_file():
                i[f.relative_to(path)] = hash_file(f, pbar)
                size += f.stat().st_size
        return i, size
    elif path.is_file():
        return hash_file(path, pbar), path.stat().st_size
    else:
        raise NotImplementedError(f"Unknown {path}")


def cp(source: Path, target: Path, rules: List[PathAwareGitMatchPattern], pbar: tqdm):
    assert os.path.exists(source), "can't copy, doesn't exist (internal error)"
    assert not os.path.exists(target), "remove explicitly first (internal error)"
    for src_f in walk(source, rules):
        dst_f = target / src_f.relative_to(source)
        dst_f.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src_f, dst_f)
        pbar.update(src_f.stat().st_size)


def rm(target: os.PathLike):
    assert os.path.exists(target), "can't remove, doesn't exist (internal error)"
    if os.path.isdir(target):
        shutil.rmtree(target)
    elif os.path.isfile(target):
        os.remove(target)
    else:  # pragma: no cover
        raise ValueError(f"Unknown thing {target}")


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
