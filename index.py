import collections
import itertools
from pathlib import Path, PurePath
from typing import Union, List, Iterator, Dict


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
                    if not line:
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
        if len(k.parts) > 1:
            return self.dirs[PurePath(k.parts[0])][PurePath(*k.parts[1:])]
        else:
            if k in self.files:
                return self.files[k]
            elif k in self.dirs:
                return self.dirs[k]
            else:
                raise KeyError(f"{k} not found")

    def __setitem__(self, k: PurePath, v: Union[str, Index]) -> None:
        assert not k.is_absolute(), "Index keys must be relative paths"
        if len(k.parts) > 1:
            assert PurePath(k.parts[0]) not in self.files, "file/directory name collision"
            if PurePath(k.parts[0]) not in self.dirs:
                self[PurePath(k.parts[0])] = Index()
            self.dirs[PurePath(k.parts[0])][PurePath(*k.parts[1:])] = v
        else:
            if isinstance(v, str):
                assert k not in self.dirs
                self.files[k] = v
            elif isinstance(v, Index):
                assert k not in self.files
                self.dirs[k] = v
            else:
                raise TypeError(f"Unallowed value of type {type(v)}")

    def __delitem__(self, k: PurePath) -> None:
        assert not k.is_absolute(), "Index keys must be relative paths"
        if len(k.parts) > 1:
            del self.dirs[PurePath(k.parts[0])][PurePath(*k.parts[1:])]
            if not self.dirs[PurePath(k.parts[0])]:
                del self.dirs[PurePath(k.parts[0])]
        else:
            if k in self.files:
                del self.files[k]
            elif k in self.dirs:
                del self.dirs[k]
            else:
                raise KeyError(f"{k} not found")

    def iters(self) -> List[Iterator[PurePath]]:
        return [map(lambda n: d/n, i) for d in self.dirs.keys() for i in self.dirs[d].iters()] + [iter(self.files)]

    def __iter__(self) -> Iterator[str]:
        return itertools.chain(*self.iters())

    def __str__(self) -> str:
        return f"Index(files: {str(self.files)}, dirs: {str(self.dirs)})"
