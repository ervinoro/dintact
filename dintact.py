#!/usr/bin/env python3
import argparse
from collections import defaultdict
from typing import List

from changes import *
from index import Index
from utils import *

# noinspection PyShadowingBuiltins
print = tqdm.write


def check(args: argparse.Namespace):
    cold_dir = Path(args.cold_dir)
    assert cold_dir.is_dir(), "cold_dir not found!"
    index = Index(cold_dir)

    # Set up progress bar
    total = sum([(cold_dir / p).stat().st_size if (cold_dir / p).exists() else 0 for p in index.keys()])
    with tqdm(total=total, unit="B", unit_scale=True) as pbar:
        # Check that index is correct
        for p, h in index.items():
            if h != hash_file(cold_dir / p, pbar):
                print(f"Verification failed: '{p}'.", file=sys.stderr)
        # Additionally check that index is complete
        for root, _, files in os.walk(cold_dir):
            root = Path(root)
            for file in files:
                relpath = (root / file).relative_to(cold_dir)
                if relpath not in index and relpath != PurePath("index.txt"):
                    print(f"File missing from index: '{relpath}'.", file=sys.stderr)


def walk_tree(path: Path, pbar: tqdm) -> Tuple[Union[Index, str], int]:
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


def walk_trees(path: PurePath, cold_index: Index, hot_dir: Path, cold_dir: Path, pbar: tqdm) -> List[Change]:
    """Calculate hashes for all files in both trees recursively (creates index for hot, validates index for cold)

    It only returns outermost directories/files for each list (except content changes, which it lists all)

    :param path: current relative path
    :param cold_index:
    :param hot_dir: hot base path
    :param cold_dir: cold base path
    :param pbar: will be updated as files get hashed
    :return: All changes between cold and hot directories
    """

    if (hot_dir/path).is_file() and (cold_dir/path).is_file():
        hot_hash, cold_hash, eq = hash_compare_files(hot_dir/path, cold_dir/path, pbar)
        hot_index = Index()
        hot_index[path] = hot_hash
        if eq:
            if path not in cold_index:
                return [AddedCopied(path, 0, hot_index)]
            elif cold_index[path] != cold_hash:
                return [ModifiedCopied(path, os.path.getsize(hot_dir / path), hot_index)]
            else:
                return []
        else:
            if path not in cold_index:
                return [AddedAppeared(path, (hot_dir/path).stat().st_size, hot_index)]
            elif cold_index[path] != cold_hash:
                if hot_hash == cold_index[path]:
                    return [Corrupted(path, os.path.getsize(hot_dir / path), hot_index)]
                else:
                    return [ModifiedCorrupted(path, os.path.getsize(hot_dir / path), hot_index)]
            else:
                return [Modified(path, (hot_dir / path).stat().st_size, hot_index)]

    elif not (hot_dir/path).is_dir() or not (cold_dir/path).is_dir():
        raise NotImplementedError("File/Folder name collision")

    changes = []

    hot_children: List[PurePath] = list(map(lambda abs_path: abs_path.relative_to(hot_dir), (hot_dir/path).iterdir()))
    cold_children: List[PurePath] = list(map(lambda abs_path: abs_path.relative_to(cold_dir), (cold_dir/path).iterdir()))
    if path == PurePath():
        cold_children.remove(PurePath("index.txt"))

    only_hot_children = set(hot_children).difference(cold_children)
    for hot_child in only_hot_children:
        i, size = walk_tree(hot_dir/hot_child, pbar)
        if hot_child not in cold_index:
            changes.append(Added(hot_child, size, i))
        elif i == cold_index[hot_child]:
            changes.append(Lost(hot_child, 0))
        else:
            changes.append(ModifiedLost(hot_child, size, i))

    removed = set(cold_children).difference(hot_children)
    for cold_child in removed:
        if cold_child not in cold_index:
            changes.append(Appeared(cold_child, 0))
        else:
            i, size = walk_tree(cold_dir/cold_child, pbar)
            if i == cold_index[cold_child]:
                changes.append(Removed(cold_child, 0))
            else:
                changes.append(RemovedCorrupted(cold_child, 0))

    removedlost = set(cold_index.keys()).difference(hot_children).difference(cold_children)
    for removedlost_child in removedlost:
        changes.append(RemovedLost(removedlost_child, 0))

    for child in set(hot_children) & set(cold_children):
        ch_changes = walk_trees(child, cold_index, hot_dir, cold_dir, pbar)
        changes.extend(ch_changes)

    return changes


def sync(args: argparse.Namespace):
    hot_dir, cold_dir = Path(args.hot_dir), Path(args.cold_dir)
    assert hot_dir.is_dir(), "hot_dir not found!"
    assert cold_dir.is_dir(), "cold_dir not found!"

    index = Index(cold_dir)
    inv_index = defaultdict(list)
    for k, v in index.items():
        inv_index[v].append(k)

    # Set up progress bar
    total = sum([(cold_dir / p).stat().st_size if (cold_dir / p).exists() else 0 for p in index.keys()])
    for root, _, files in os.walk(args.hot_dir):
        for file in files:
            total += os.path.getsize(os.path.join(root, file))
    with tqdm(total=total, unit="B", unit_scale=True) as pbar:
        changes = walk_trees(PurePath(), index, hot_dir, cold_dir, pbar)

        # TODO: calculate reverse indices recursively for added and removed
        # TODO: find all moved. Can be also moved into added or out from removed
        # for file in hot_only:
        #     h = hash_file(os.path.join(args.hot_dir, file), pbar)
        #     if h in inv_index and set(cold_only) & set(inv_index[h]):
        #         print(set(cold_only) & set(inv_index[h]), "moved to", file)

    actions = []
    action_total = 0

    for change in changes:
        # TODO: for context provide if contains moved'es
        if yesno(str(change), default=False):
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
