"""Defines all possible changes that can happen between hot and cold copies.

Combinations of Hot, Cold and Index (0 = not in, same number = same file, different number = different file)

H C I
1 1 1 OK
1 1 2 ModifiedCopied
2 1 1 Modified
1 2 1 Corrupted
1 2 3 ModifiedCorrupted
1 1 0 AddedCopied
1 2 0 AddedAppeared
1 0 1 Lost
1 0 2 ModifiedLost
1 0 0 Added
0 1 1 Removed
0 1 2 RemovedCorrupted
0 1 0 Appeared
0 0 1 RemovedLost
0 0 0 NULL

"""
from os import renames
from pathlib import Path, PurePath

from tqdm import tqdm

from index import Index
from utils import cp, rm


class Change:
    """Abstract base class for changes

    :param name: relative path to the changed entity
    :param size: of data to be moved to cold backup in bytes (for progressbar)
    """
    has_been: str  # description of what has happened in hot copy
    action: str  # description of what could be done to mimic it in cold backup

    def __init__(
        self,
        name: PurePath,
        size: int = 0,
    ):
        self.name = name
        self.size = size

    def apply(self, hot_dir: Path, cold_dir: Path, index: Index, pbar: tqdm) -> None:
        """Apply the change from hot_dir to cold_dir

        :param hot_dir: hot copy base path
        :param cold_dir: cold copy base path
        :param index: cold copy index, will be modified accordingly
        :param pbar
        """

    def __repr__(self):
        return f"{self.name} has been {self.has_been}, do you want to {self.action}?"

    def __id_members(self):
        return type(self), self.name

    def __eq__(self, other):
        if isinstance(other, Change):
            return self.__id_members() == other.__id_members()
        else:
            return False

    def __hash__(self):
        return hash(self.__id_members())


class ChangeWithIndex(Change):
    """
    :param name: relative path to the changed entity
    :param size: of data to be moved to cold backup in bytes (for progressbar)
    :param index: sub-index with checksums of all new files
    """

    def __init__(
        self,
        name: PurePath,
        index: Index | str,
        size: int = 0,
    ):
        super().__init__(name, size)
        self.index = index


class AddedCopied(ChangeWithIndex):
    has_been = "added and manually copied (without updating the index)"
    action = "add it to cold index"

    def apply(self, hot_dir: Path, cold_dir: Path, index: Index, pbar: tqdm):
        index[self.name] = self.index


class ModifiedCopied(AddedCopied):
    has_been = "modified and manually copied (without updating the index)"


class Added(ChangeWithIndex):
    has_been = "added"
    action = "copy it to cold backup"

    def apply(self, hot_dir: Path, cold_dir: Path, index: Index, pbar: tqdm):
        cp(hot_dir / self.name, cold_dir / self.name, pbar)
        index[self.name] = self.index


class ModifiedLost(Added):
    has_been = "modified in hot and lost from cold backup"


class Lost(Change):
    has_been = "lost from cold backup"
    action = "copy it to cold backup"

    def apply(self, hot_dir: Path, cold_dir: Path, index: Index, pbar: tqdm):
        cp(hot_dir / self.name, cold_dir / self.name, pbar)


class Removed(ChangeWithIndex):
    has_been = "removed"
    action = "remove it from cold backup"

    def apply(self, hot_dir: Path, cold_dir: Path, index: Index, pbar: tqdm):
        rm(cold_dir / self.name)
        del index[self.name]


class Moved(ChangeWithIndex):
    """
    :param name: relative path to the changed entity
    :param index: sub-index with checksums of all new files
    """

    def __init__(
        self,
        name: PurePath,
        index: Index | str,
        original: Removed,
    ):
        super().__init__(name, index)
        self.original = original
        self.has_been = f"moved from {original.name}"

    action = "rename it in cold backup"

    def apply(self, hot_dir: Path, cold_dir: Path, index: Index, pbar: tqdm):
        renames(cold_dir / self.original.name, cold_dir / self.name)
        index[self.name] = self.index
        del index[self.original.name]


class RemovedCorrupted(Removed):
    has_been = "removed (from hot storage) and corrupted (in cold backup)"


class Modified(ChangeWithIndex):
    has_been = "modified"
    action = "overwrite from hot to cold"

    def apply(self, hot_dir: Path, cold_dir: Path, index: Index, pbar: tqdm):
        rm(cold_dir / self.name)
        cp(hot_dir / self.name, cold_dir / self.name, pbar)
        index[self.name] = self.index


class Corrupted(Change):
    has_been = "corrupted (in cold backup)"
    action = "overwrite from hot to cold"

    def apply(self, hot_dir: Path, cold_dir: Path, index: Index, pbar: tqdm):
        rm(cold_dir / self.name)
        cp(hot_dir / self.name, cold_dir / self.name, pbar)


class ModifiedCorrupted(Modified):
    has_been = "modified (in hot storage) and corrupted (in cold backup)"


class AddedAppeared(Modified):
    has_been = "added to both (different files)"


class Appeared(Change):
    has_been = "manually added to cold backup (but not index)"
    action = "delete if from cold backup"

    def apply(self, hot_dir: Path, cold_dir: Path, index: Index, pbar: tqdm):
        rm(cold_dir / self.name)


class RemovedLost(Change):
    has_been = "removed from hot and lost from cold backup"
    action = "remove it from index"

    def apply(self, hot_dir: Path, cold_dir: Path, index: Index, pbar: tqdm):
        del index[self.name]
