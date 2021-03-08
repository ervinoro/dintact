#!/usr/bin/env python3
import argparse
import itertools
import os
import sys
from operator import attrgetter
from pathlib import Path, PurePath
from typing import List, Set

from tqdm import tqdm

from changes import (Added, AddedAppeared, AddedCopied, Appeared, Change,
                     Corrupted, Lost, Modified, ModifiedCopied,
                     ModifiedCorrupted, ModifiedLost, Removed,
                     RemovedCorrupted, RemovedLost)
from index import Index
from utils import (PathAwareGitWildMatchPattern, hash_compare_files, hash_file,
                   hash_tree, is_relevant, walk, yesno)

# noinspection PyShadowingBuiltins
print = tqdm.write


def check(args: argparse.Namespace) -> None:
    """Verify that index matches files, print out any mismatches

    :param args: must have attr cold_dir: str
    """
    cold_dir = Path(args.cold_dir)
    assert cold_dir.is_dir(), "cold_dir not found!"
    index = Index(cold_dir)
    fail_count = 0

    # Set up progress bar
    total = sum([(cold_dir / p).stat().st_size if (cold_dir / p).exists() else 0 for p in index.keys()])
    with tqdm(total=total, unit="B", unit_scale=True) as pbar:
        # Check that index is correct
        for p, h in index.items():
            if h != hash_file(cold_dir / p, pbar):
                print(f"Verification failed: '{p}'.", file=sys.stderr)
                fail_count += 1
        # Additionally check that index is complete
        for file in walk(cold_dir, [PathAwareGitWildMatchPattern('index.txt', cold_dir)]):
            rel_path: PurePath = file.relative_to(cold_dir)
            if rel_path not in index:
                print(f"File missing from index: '{rel_path}'.", file=sys.stderr)
                fail_count += 1

    if fail_count == 0:
        print("OK: Data is intact!")
    else:
        print(f"FAIL: There were {fail_count} failures!")


def walk_trees(path: PurePath, cold_index: Index, hot_dir: Path, cold_dir: Path,
               hot_rules: List[PathAwareGitWildMatchPattern], cold_rules: List[PathAwareGitWildMatchPattern],
               pbar: tqdm) -> List[Change]:
    """Compare hot (sub)dir, cold (sub)dir, and cold index. Returns a list of changes required to get them synced.

    It only returns outermost directories/files for each change (except content changes, which it lists all)

    :param path: current relative path
    :param cold_index: the original unchanged cold index
    :param hot_dir: hot base path
    :param cold_dir: cold base path
    :param hot_rules: files to ignore in hot dir
    :param cold_rules: files to ignore in cold dir
    :param pbar: will be updated as files get hashed
    :return: All changes between cold and hot directories under current sub path
    """
    sub_index = cold_index[path] if path in cold_index else None

    if (hot_dir / path).is_file() and (cold_dir / path).is_file():
        hot_hash, cold_hash, eq = hash_compare_files(hot_dir / path, cold_dir / path, pbar)
        if eq:
            if path not in cold_index:
                return [AddedCopied(path, 0, hot_hash)]
            elif cold_index[path] != cold_hash:
                return [ModifiedCopied(path, 0, hot_hash)]
            else:
                return []
        else:
            if path not in cold_index:
                return [AddedAppeared(path, (hot_dir / path).stat().st_size, hot_hash)]
            elif cold_index[path] != cold_hash:
                if hot_hash == cold_index[path]:
                    return [Corrupted(path, os.path.getsize(hot_dir / path), hot_hash)]
                else:
                    return [ModifiedCorrupted(path, os.path.getsize(hot_dir / path), hot_hash)]
            else:
                return [Modified(path, (hot_dir / path).stat().st_size, hot_hash)]

    elif not (hot_dir / path).is_dir() or not (cold_dir / path).is_dir() or isinstance(sub_index, str):
        raise NotImplementedError("File/Folder name collision")

    else:
        changes: List[Change] = []

        if (hot_dir / path / '.gitignore').exists():
            with open(hot_dir / path / '.gitignore', 'r') as f:
                hot_rules += map(lambda r: PathAwareGitWildMatchPattern(r, hot_dir / path), f.read().splitlines())
        if (cold_dir / path / '.gitignore').exists():
            with open(cold_dir / path / '.gitignore', 'r') as f:
                cold_rules += map(lambda r: PathAwareGitWildMatchPattern(r, cold_dir / path), f.read().splitlines())
        if path == PurePath():
            hot_rules += [PathAwareGitWildMatchPattern('index.txt', hot_dir / path)]
            cold_rules += [PathAwareGitWildMatchPattern('index.txt', cold_dir / path)]

        hot_children: Set[PurePath] = set(map(lambda abs_path: abs_path.relative_to(hot_dir),
                                              filter(lambda p: is_relevant(p, hot_rules),
                                                     (hot_dir / path).iterdir())))
        cold_children: Set[PurePath] = set(map(lambda abs_path: abs_path.relative_to(cold_dir),
                                               filter(lambda p: is_relevant(p, cold_rules),
                                                      (cold_dir / path).iterdir())))
        index_children: Set[PurePath] = set(map(lambda p: path / p,
                                                sub_index.iterdir() if sub_index is not None else []))

        # H C I: 1 0 X
        for hot_child in hot_children.difference(cold_children):
            i, size = hash_tree(hot_dir / hot_child, pbar)
            if hot_child not in cold_index:
                changes.append(Added(hot_child, size, i))
            elif i == cold_index[hot_child]:
                changes.append(Lost(hot_child, size))
            else:
                changes.append(ModifiedLost(hot_child, size, i))

        # H C I: 0 1 X
        for cold_child in cold_children.difference(hot_children):
            if cold_child not in cold_index:
                changes.append(Appeared(cold_child, 0))
                for file in walk(cold_dir / cold_child, cold_rules):
                    pbar.update(file.stat().st_size)
            else:
                i, size = hash_tree(cold_dir / cold_child, pbar)
                if i == cold_index[cold_child]:
                    changes.append(Removed(cold_child, 0))
                else:
                    changes.append(RemovedCorrupted(cold_child, 0))

        # H C I: 0 0 1
        for index_child in index_children.difference(hot_children).difference(cold_children):
            changes.append(RemovedLost(index_child, 0))

        # Recursive: (H C I: 1 1 X)
        for child in hot_children & cold_children:
            ch_changes = walk_trees(child, cold_index, hot_dir, cold_dir, hot_rules[:], cold_rules[:], pbar)
            changes.extend(ch_changes)

        return changes


def sync(args: argparse.Namespace) -> None:
    """Prompt user for each change towards getting hot dir, cold dir and cold index synced

    :param args: must have attrs hot_dir:str and cold_dir: str
    """
    hot_dir, cold_dir = Path(args.hot_dir), Path(args.cold_dir)
    assert hot_dir.is_dir(), "hot_dir not found!"
    assert cold_dir.is_dir(), "cold_dir not found!"

    index = Index(cold_dir)
    # inv_index = defaultdict(list)
    # for k, v in index.items():
    #     inv_index[v].append(k)

    # Set up progress bar
    total = 0
    for file in itertools.chain(walk(hot_dir, []), walk(cold_dir, [])):
        total += file.stat().st_size
    with tqdm(total=total, unit="B", unit_scale=True) as pbar:
        # Find all changes required
        changes = walk_trees(PurePath(), index, hot_dir, cold_dir, [], [], pbar)

        # TODO: calculate reverse indices recursively for added and removed
        # TODO: find all moved. Can be also moved into added or out from removed
        # for file in hot_only:
        #     h = hash_file(os.path.join(args.hot_dir, file), pbar)
        #     if h in inv_index and set(cold_only) & set(inv_index[h]):
        #         print(set(cold_only) & set(inv_index[h]), "moved to", file)

    # Confirm each change with the user
    changes.sort(key=attrgetter('name'))
    actions = []
    action_total = 0
    for change in changes:
        if yesno(str(change), default=False):
            actions.append(change)
            action_total += change.size

    # Carry out all confirmed changes
    with tqdm(total=action_total, unit="B", unit_scale=True) as pbar:
        for change in actions:
            change.apply(args.hot_dir, args.cold_dir, index)
            pbar.update(change.size)

    index.store()
    print("OK: Done!")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='subparser_name', help='command')

    parser_check = subparsers.add_parser('check', help="Verify that all files and checksums match")
    parser_check.add_argument('cold_dir', help="Cold backup root dir, must contain index.txt")
    parser_check.set_defaults(func=check)

    parser_sync = subparsers.add_parser('sync', help="Sync hot and cold archive folders")
    parser_sync.add_argument('hot_dir', help="Working copy of the archive, assumed to be newer")
    parser_sync.add_argument('cold_dir', help="Cold backup root dir, must contain index.txt")
    parser_sync.set_defaults(func=sync)

    parsed_args = parser.parse_args()
    if parsed_args.subparser_name:
        parsed_args.func(parsed_args)
    else:
        parser.print_help()
