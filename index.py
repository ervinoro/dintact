from __future__ import annotations

import datetime
import itertools
import json
from collections.abc import MutableMapping
from pathlib import Path, PurePath
from typing import Dict, Iterator


class Index(MutableMapping):
    """Dict-like structure mapping files to checksums

    Can either be used in-memory or as a file interface.

    :param cold_dir: directory containing STD_NAME, or None (in which case empty in-memory index is created)
    :param coding: file encoding to use when reading STD_NAME
    """
    FILENAME = 'index.txt'
    meta: dict | None = None

    def __init__(self, cold_dir: Path | None = None, coding: str = 'utf8') -> None:
        super().__init__()
        self.dirs: Dict[PurePath, Index] = {}
        self.files: Dict[PurePath, str] = {}
        if cold_dir is None:
            return
        self.path = cold_dir / self.FILENAME
        if not self.path.exists():
            self.path.touch(exist_ok=False)
            self.meta = {
                'version': 1,
                'algorithm': 'XXH128',
                'coding': 'utf8',
            }
            return
        with self.path.open('r', encoding=coding) as file:
            header_line = file.readline()
            if header_line.startswith('# dintact index '):
                meta = json.loads(header_line[16:])
                if meta['version'] != 1 or meta['algorithm'] != 'XXH128' or meta['coding'] != coding:
                    raise ValueError("Can't load this index file!")
                self.meta = meta
            else:
                raise ValueError("Index file header missing!")

            for line in file:
                if not line.strip() or line[0] == "#":
                    continue
                checksum, name = line.strip().split("  ", 1)
                self[PurePath(name)] = checksum

    def store(self):
        """Store to cold backup index file"""
        self.meta['created_at'] = datetime.datetime.now().replace(microsecond=0).astimezone().isoformat()
        with self.path.open('w', encoding=self.meta['coding']) as file:
            file.write(f"# dintact index {json.dumps(self.meta)}\n")
            for name in self.keys():
                v = self[name]
                assert isinstance(v, str), f"Internal Error ({v} returned by iter)"
                file.write(f"{v}  {name.as_posix()}\n")

    def __len__(self) -> int:
        return sum([len(d) for d in self.dirs.values()]) + len(self.files)

    @staticmethod
    def _validate_key(k: PurePath):
        assert not k.is_absolute(), "Index keys must be relative paths"

    def __contains__(self, k: object) -> bool:
        if isinstance(k, PurePath):
            self._validate_key(k)
            if len(k.parts) == 0:
                return True
            elif len(k.parts) == 1:
                return k in self.files or k in self.dirs
            else:
                head = PurePath(k.parts[0])
                tail = PurePath(*k.parts[1:])
                return head in self.dirs and tail in self.dirs[head]
        else:
            return False

    def __getitem__(self, k: PurePath) -> str | Index:
        self._validate_key(k)
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

    def __setitem__(self, k: PurePath, v: str | Index) -> None:
        self._validate_key(k)
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
                raise TypeError(f"Disallowed value of type {type(v)}")
        else:
            assert PurePath(k.parts[0]) not in self.files, "file/directory name collision"
            if PurePath(k.parts[0]) not in self.dirs:
                self[PurePath(k.parts[0])] = Index()
            self.dirs[PurePath(k.parts[0])][PurePath(*k.parts[1:])] = v

    def __delitem__(self, k: PurePath) -> None:
        self._validate_key(k)
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
        return itertools.chain(
            (directory / file for directory in self.dirs for file in self.dirs[directory]),
            self.files
        )

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
