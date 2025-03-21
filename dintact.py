#!/usr/bin/env python3
import argparse
import os
import sys
from collections import defaultdict
from operator import attrgetter
from pathlib import Path, PurePath
from typing import List, Set

from tqdm import tqdm

from changes import (Added, AddedAppeared, AddedCopied, Appeared, Change,
                     Corrupted, Lost, Modified, ModifiedCopied,
                     ModifiedCorrupted, ModifiedLost, Moved, Removed,
                     RemovedCorrupted, RemovedLost)
from index import Index
from utils import (hash_compare_files, hash_file, hash_tree, is_relevant, walk,
                   yesno)

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
        # Firstly, check that the index is correct
        for p, h in index.items():
            if h != hash_file(cold_dir / p, pbar):
                print(f"Verification failed: '{p}'.", file=sys.stderr)
                fail_count += 1
        # Secondly, check that the index is complete
        for file in walk(cold_dir):
            rel_path: PurePath = file.relative_to(cold_dir)
            if rel_path not in index:
                print(f"File missing from index: '{rel_path}'.", file=sys.stderr)
                fail_count += 1

    if fail_count == 0:
        print("OK: Data is intact!")
    else:
        print(f"FAIL: There were {fail_count} failures!")


def _compare_files(path: PurePath, cold_index: Index, hot_dir: Path, cold_dir: Path, pbar: tqdm) -> List[Change]:
    hot_hash, cold_hash, eq = hash_compare_files(hot_dir / path, cold_dir / path, pbar)
    if eq:
        if path not in cold_index:
            return [AddedCopied(path, hot_hash)]
        elif cold_index[path] != cold_hash:
            return [ModifiedCopied(path, hot_hash)]
        else:
            return []
    else:
        if path not in cold_index:
            return [AddedAppeared(path, hot_hash, (hot_dir / path).stat().st_size)]
        elif cold_index[path] != cold_hash:
            if hot_hash == cold_index[path]:
                return [Corrupted(path, os.path.getsize(hot_dir / path))]
            else:
                return [ModifiedCorrupted(path, hot_hash, os.path.getsize(hot_dir / path))]
        else:
            return [Modified(path, hot_hash, (hot_dir / path).stat().st_size)]


def _compare_dirs(path: PurePath, cold_index: Index, hot_dir: Path, cold_dir: Path, sub_index: Index | None,
                  pbar: tqdm) -> List[Change]:
    changes: List[Change] = []

    hot_children: Set[PurePath] = set(map(lambda abs_path: abs_path.relative_to(hot_dir),
                                          filter(lambda p: is_relevant(p),
                                                 (hot_dir / path).iterdir())))
    cold_children: Set[PurePath] = set(map(lambda abs_path: abs_path.relative_to(cold_dir),
                                           filter(lambda p: is_relevant(p),
                                                  (cold_dir / path).iterdir())))
    index_children: Set[PurePath] = set(map(lambda p: path / p,
                                            sub_index.iterdir() if sub_index is not None else []))

    # H C I: 1 0 X
    for hot_child in hot_children.difference(cold_children):
        i, size = hash_tree(hot_dir / hot_child, pbar)
        if hot_child not in cold_index:
            changes.append(Added(hot_child, i, size))
        elif i == cold_index[hot_child]:
            changes.append(Lost(hot_child, size))
        else:
            changes.append(ModifiedLost(hot_child, i, size))

    # H C I: 0 1 X
    for cold_child in cold_children.difference(hot_children):
        if cold_child not in cold_index:
            changes.append(Appeared(cold_child))
            pbar.update(sum(file.stat().st_size for file in walk(cold_dir / cold_child)))
        elif hash_tree(cold_dir / cold_child, pbar)[0] == cold_index[cold_child]:
            changes.append(Removed(cold_child, cold_index[cold_child]))
        else:
            changes.append(RemovedCorrupted(cold_child, cold_index[cold_child]))

    # H C I: 0 0 1
    for index_child in index_children.difference(hot_children).difference(cold_children):
        changes.append(RemovedLost(index_child))

    # Recursive: (H C I: 1 1 X)
    for child in hot_children & cold_children:
        ch_changes = walk_trees(child, cold_index, hot_dir, cold_dir, pbar)
        changes.extend(ch_changes)

    return changes


def walk_trees(path: PurePath, cold_index: Index, hot_dir: Path, cold_dir: Path, pbar: tqdm) -> List[Change]:
    """Compare hot (sub)dir, cold (sub)dir, and cold index. Returns a list of changes required to get them synced.

    It only returns outermost directories/files for each change (except content changes, which it lists all)

    :param path: current relative path
    :param cold_index: the original unchanged cold index
    :param hot_dir: hot base path
    :param cold_dir: cold base path
    :param pbar: will be updated as files get hashed
    :return: All changes between cold and hot directories under current sub path
    """

    sub_index = cold_index[path] if path in cold_index else None
    if (hot_dir / path).is_file() and (cold_dir / path).is_file():
        return _compare_files(path, cold_index, hot_dir, cold_dir, pbar)
    elif not (hot_dir / path).is_dir() or not (cold_dir / path).is_dir() or isinstance(sub_index, str):
        raise NotImplementedError("File/Folder name collision")
    else:
        return _compare_dirs(path, cold_index, hot_dir, cold_dir, sub_index, pbar)


def find_moveds(changes: list[Change]):
    removeds = defaultdict(list)
    addeds = defaultdict(list)
    for change in changes:
        if isinstance(change, Removed) and type(change) is Removed:
            removeds[change.index].append(change)
        elif isinstance(change, Added) and type(change) is Added:
            addeds[change.index].append(change)

    for i in set(removeds).intersection(addeds):
        if len(removeds[i]) != 1 or len(addeds[i]) != 1:
            continue
        changes.append(Moved(addeds[i][0].name, addeds[i][0].index, removeds[i][0]))
        changes.remove(removeds[i][0])
        changes.remove(addeds[i][0])


def ignore_index(changes: list[Change]):
    index = PurePath(Index.FILENAME)
    for change in changes:
        if change.name == index and type(change) is Appeared:
            changes.remove(change)
            return


def find_deduplications(changes: list[Change], index: Index):
    for change in changes:
        if (isinstance(change, Removed) and type(change) is Removed and isinstance(change.index, str)
                and change.index in index.reverse):
            duplicates = [str(path) for path in index.reverse[change.index] if path != change.name]
            change.has_been += f" (cold index has duplicates: {duplicates})"


def sync(args: argparse.Namespace) -> None:
    """Prompt user for each change towards getting hot dir, cold dir and cold index synced

    :param args: must have attrs hot_dir:str and cold_dir: str
    """
    hot_dir, cold_dir = Path(args.hot_dir), Path(args.cold_dir)
    assert hot_dir.is_dir(), "hot_dir not found!"
    assert cold_dir.is_dir(), "cold_dir not found!"

    index = Index(cold_dir)

    # Set up progress bar
    file_count = 0
    for _, dirs, files in os.walk(hot_dir):
        file_count += len(dirs) + len(files)
    for _, dirs, files in os.walk(cold_dir):
        file_count += len(dirs) + len(files)
    total = 0
    with tqdm(total=file_count, unit_scale=True, desc="Calculating data size") as pbar:
        for file in walk(hot_dir, pbar):
            total += file.stat().st_size
        for file in walk(cold_dir, pbar):
            total += file.stat().st_size
    with tqdm(total=total, unit="B", unit_scale=True, desc="Detecting changes") as pbar:
        # Find all changes required
        changes = walk_trees(PurePath(), index, hot_dir, cold_dir, pbar)
    ignore_index(changes)
    find_moveds(changes)
    find_deduplications(changes, index)

    if len(changes):
        print(f"Found {len(changes)} changes.")

    # Confirm each change with the user
    changes.sort(key=attrgetter('name'))
    actions: List[Change] = []
    action_total = 0
    for change in changes:
        if change.name.suffix.lower() in ['.jpg']:
            continue
        if yesno(str(change), default=False):
            actions.append(change)
            action_total += change.size

    if not yesno(f"Commence {len(actions)} actions?", False):
        print("Aborted!")
        return

    # Carry out all confirmed changes
    with tqdm(total=action_total, unit="B", unit_scale=True, desc="Applying changes") as pbar:
        for change in actions:
            change.apply(args.hot_dir, args.cold_dir, index, pbar)

    index.store()
    print("OK: Done!")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='subparser_name', help='command')

    parser_check = subparsers.add_parser('check', help="Verify that all files and checksums match")
    parser_check.add_argument('cold_dir', help=f"Cold backup root dir, must contain {Index.FILENAME}")
    parser_check.set_defaults(func=check)

    parser_sync = subparsers.add_parser('sync', help="Sync hot and cold archive folders")
    parser_sync.add_argument('hot_dir', help="Working copy of the archive, assumed to be newer")
    parser_sync.add_argument('cold_dir', help=f"Cold backup root dir, must contain {Index.FILENAME}")
    parser_sync.set_defaults(func=sync)

    parsed_args = parser.parse_args()
    if parsed_args.subparser_name:
        parsed_args.func(parsed_args)
    else:
        parser.print_help()
