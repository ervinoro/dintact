import collections
import itertools
from pathlib import Path, PurePath
from typing import Union, Iterator, Dict


class Index:
    pass  # PyCharm bug about using types internally


# noinspection PyRedeclaration
class Index(collections.abc.MutableMapping):
    """Dict-like structure mapping files to checksums

    Can either be used in-memory or as a file interface.

    :param cold_dir: directory containing index.txt, or None (in which case empty in-memory index is created)
    """

    def __init__(self, cold_dir: Union[Path, None] = None) -> None:
        super().__init__()
        self.dirs: Dict[PurePath, Index] = {}
        self.files: Dict[PurePath, str] = {}
        if cold_dir:
            self.path = cold_dir / "index.txt"
            if not self.path.exists():
                self.path.touch(exist_ok=False)
            with self.path.open('r', encoding='utf8') as file:
                for line in file:
                    if not line.strip():
                        continue
                    checksum, name = line.strip().split(" ", 1)
                    self[PurePath(name)] = checksum

    def store(self):
        """Store to cold backup index file"""
        with self.path.open('w', encoding='utf8') as file:
            for name in self.keys():
                v = self[name]
                assert isinstance(v, str), f"Internal Error ({v} returned by iter)"
                file.write(f"{v} {name.as_posix()}\n")

    def __len__(self) -> int:
        return sum([len(d) for d in self.dirs.values()]) + len(self.files)

    def __getitem__(self, k: PurePath) -> Union[str, Index]:
        assert not k.is_absolute(), "Index keys must be relative paths"
        if len(k.parts) == 0:
            return self
        elif len(k.parts) == 1:
            if k in self.files:
                return self.files[k]
            elif k in self.dirs:
                return self.dirs[k]
            else:
                raise KeyError(f"{k} not found")
        else:
            return self.dirs[PurePath(k.parts[0])][PurePath(*k.parts[1:])]

    def __setitem__(self, k: PurePath, v: Union[str, Index]) -> None:
        assert not k.is_absolute(), "Index keys must be relative paths"
        if len(k.parts) == 0:
            raise ValueError("can't set self (i think)")
        elif len(k.parts) == 1:
            if isinstance(v, str):
                assert k not in self.dirs
                self.files[k] = v
            elif isinstance(v, Index):
                assert k not in self.files
                self.dirs[k] = v
            else:
                raise TypeError(f"Unallowed value of type {type(v)}")
        else:
            assert PurePath(k.parts[0]) not in self.files, "file/directory name collision"
            if PurePath(k.parts[0]) not in self.dirs:
                self[PurePath(k.parts[0])] = Index()
            self.dirs[PurePath(k.parts[0])][PurePath(*k.parts[1:])] = v

    def __delitem__(self, k: PurePath) -> None:
        assert not k.is_absolute(), "Index keys must be relative paths"
        if len(k.parts) == 0:
            raise ValueError("can't del self (i think)")
        elif len(k.parts) == 1:
            if k in self.files:
                del self.files[k]
            elif k in self.dirs:
                del self.dirs[k]
            else:
                raise KeyError(f"{k} not found")
        else:
            del self.dirs[PurePath(k.parts[0])][PurePath(*k.parts[1:])]
            if not self.dirs[PurePath(k.parts[0])]:
                del self.dirs[PurePath(k.parts[0])]

    def __iter__(self) -> Iterator[PurePath]:
        return itertools.chain(*[list(map(lambda n: d[0] / n, iter(d[1]))) for d in self.dirs.items()],
                               iter(self.files))

    def iterdir(self) -> Iterator[PurePath]:
        """Non-recursive only iterate immediate children"""
        return itertools.chain(iter(self.dirs), iter(self.files))

    def __repr__(self) -> str:
        return f"Index(files: {repr(self.files)}, dirs: {repr(self.dirs)})"

    def __id_members(self):
        return self.dirs, self.files

    def __eq__(self, other):
        if type(other) is type(self):
            return self.__id_members() == other.__id_members()
        else:
            return False
