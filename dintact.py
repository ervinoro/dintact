#!/usr/bin/env python3
import argparse
from collections import defaultdict
from pathlib import Path, PurePath
from typing import List, Union

from index import Index
from utils import *

# noinspection PyShadowingBuiltins
print = tqdm.write


def check(args: argparse.Namespace):
    cold_dir = Path(args.cold_dir)
    assert cold_dir.is_dir(), "cold_dir not found!"
    index = Index(cold_dir)

    # Set up progress bar
    total = sum([(cold_dir / p).stat().st_size for p in index.keys()])
    with tqdm(total=total, unit="B", unit_scale=True) as pbar:
        # Check that index is correct
        for p, h in index.items():
            if h != hash_file(cold_dir / p, pbar):
                print(f"Verification failed: '{p}'.", file=sys.stderr)
        # Additionally check that index is complete
        for root, _, files in os.walk(cold_dir):
            for file in files:
                relpath = (root / file).relative_to(cold_dir)
                if relpath not in index and relpath != PurePath("index.txt"):
                    print(f"File missing from index: '{relpath}'.", file=sys.stderr)

# TODO: below not rewritten
class Change:
    def __init__(self, name: str, size: int, index: Union[Index, None] = None):
        self.name = name
        self.size = size
        self.index = index

    def __str__(self):
        return f"{self.name} has been {self.has_been}, do you want to {self.action}?"

    def _apply(self, hot_path: str, cold_path: str, index: Index):
        pass

    def apply(self, hot_dir: str, cold_dir: str, index: Index):
        hot_path = os.path.join(hot_dir, self.name)
        cold_path = os.path.join(cold_dir, self.name)
        self._apply(hot_path, cold_path, index)


class Added(Change):
    has_been = "added"
    action = "copy it to cold backup"

    def _apply(self, hot_path, cold_path, index: Index):
        cp(hot_path, cold_path)
        index[self.name] = self.index[self.name]


class Removed(Change):
    has_been = "removed"
    action = "remove it from cold backup"

    def _apply(self, hot_path, cold_path, index: Index):
        rm(cold_path)
        del index[self.name]


class Modified(Change):
    has_been = "modified"
    action = "copy it to cold backup"

    def _apply(self, hot_path: str, cold_path: str, index: Index):
        rm(cold_path)
        cp(hot_path, cold_path)
        index[self.name] = self.index


def walk_trees(hot_dir: str, cold_dir: str, cold_index: Index, args: argparse.Namespace, pbar: tqdm) -> List[Change]:
    """

    This function calculates hashes for all files in both trees recursively
    (creates index for hot, validates index for cold)

    It only returns outermost directories/files for each list (except content changes, which it lists all)
    """
    if not os.path.isdir(hot_dir) or not os.path.isdir(cold_dir):
        hot_hash, cold_hash, eq = hash_compare_files(hot_dir, cold_dir, pbar)
        assert cold_index[os.path.relpath(cold_dir, args.cold_dir)] == cold_hash, "Cold index invalid, won't sync..."
        if eq:
            return []
        else:
            hot_index = Index()
            hot_index[os.path.relpath(hot_dir, args.hot_dir)] = hot_hash
            return [Modified(os.path.relpath(hot_dir, args.hot_dir), os.path.getsize(hot_dir), hot_index)]

    changes = []

    hot_children = list(map(
        lambda abs_path: str(os.path.relpath(os.path.join(hot_dir, abs_path), args.hot_dir)),
        os.listdir(hot_dir)))
    cold_children = list(filter(lambda p: p != "index.txt", map(
        lambda abs_path: str(os.path.relpath(os.path.join(cold_dir, abs_path), args.cold_dir)),
        os.listdir(cold_dir))))

    added = set(hot_children).difference(cold_children)
    for hot_child in added:
        size = 0
        hot_index = Index()
        if os.path.isdir(os.path.join(args.hot_dir, hot_child)):
            for root, _, files in os.walk(os.path.join(args.hot_dir, hot_child)):
                for file in files:
                    path = os.path.join(root, file)
                    checksum = hash_file(path, pbar)
                    hot_index[os.path.relpath(path, args.hot_dir)] = checksum
                    size += os.path.getsize(path)
        elif os.path.isfile(os.path.join(args.hot_dir, hot_child)):
            path = os.path.join(args.hot_dir, hot_child)
            checksum = hash_file(path, pbar)
            hot_index[os.path.relpath(path, args.hot_dir)] = checksum
            size += os.path.getsize(path)
        changes.append(Added(hot_child, size, hot_index))

    removed = set(cold_children).difference(hot_children)
    for cold_child in removed:
        changes.append(Removed(cold_child, 0))
        if os.path.isdir(os.path.join(args.cold_dir, cold_child)):
            for root, _, files in os.walk(os.path.join(args.cold_dir, cold_child)):
                for file in files:
                    path = os.path.join(root, file)
                    checksum = hash_file(path, pbar)
                    assert cold_index[os.path.relpath(path, args.cold_dir)] == checksum, "Cold index invalid, won't sync..."
        elif os.path.isfile(os.path.join(args.cold_dir, cold_child)):
            path = os.path.join(args.cold_dir, cold_child)
            checksum = hash_file(path, pbar)
            assert cold_index[os.path.relpath(path, args.cold_dir)] == checksum, "Cold index invalid, won't sync..."

    for child in set(hot_children) & set(cold_children):
        ch_changes = walk_trees(
            os.path.join(args.hot_dir, child),
            os.path.join(args.cold_dir, child),
            cold_index, args, pbar
        )
        changes.extend(ch_changes)

    return changes


def sync(args: argparse.Namespace):
    assert os.path.isdir(args.hot_dir), "hot_dir not found!"
    assert os.path.isdir(args.cold_dir), "cold_dir not found!"

    index = Index(args.cold_dir)
    inv_index = defaultdict(list)
    for k, v in index.items():
        inv_index[v].append(k)

    # Assert that cold index represents the same set of files as cold directory (content checked later
    for root, _, files in os.walk(args.cold_dir):
        for file in files:
            relpath = os.path.relpath(os.path.join(root, file), args.cold_dir)
            assert relpath in index or relpath == "index.txt", "Cold index invalid, won't sync..."
    for file in index.keys():
        assert os.path.isfile(os.path.join(args.cold_dir, file)), "Cold index invalid, won't sync..."

    # Set up progress bar
    total = sum([os.path.getsize(os.path.join(args.cold_dir, p)) for p in index.keys()])
    for root, _, files in os.walk(args.hot_dir):
        for file in files:
            total += os.path.getsize(os.path.join(root, file))
    with tqdm(total=total, unit="B", unit_scale=True) as pbar:

        changes = walk_trees(args.hot_dir, args.cold_dir, index, args, pbar)

        # TODO: calculate reverse indices recursively for added and removed
        # TODO: find all moved. Can be also moved into added or out from removed
        # for file in hot_only:
        #     h = hash_file(os.path.join(args.hot_dir, file), pbar)
        #     if h in inv_index and set(cold_only) & set(inv_index[h]):
        #         print(set(cold_only) & set(inv_index[h]), "moved to", file)

    actions = []
    action_total = 0

    for change in changes:
        # TODO: for context provide if contains moved'es and if was invalid
        if yesno(str(change)):
            actions.append(change)
            action_total += change.size

    with tqdm(total=total, unit="B", unit_scale=True) as pbar:
        for change in actions:
            change.apply(args.hot_dir, args.cold_dir, index)
            pbar.update(change.size)

    index.store()


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
