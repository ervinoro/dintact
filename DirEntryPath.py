import os
from pathlib import Path


class DirEntryPath(Path):
    entry: os.DirEntry

    def __init__(self, *args):
        entry = args[0]
        if isinstance(entry, os.DirEntry):
            super().__init__(entry.path)
            self.entry = entry
        else:
            super().__init__(*args)

    def is_symlink(self):
        if self.entry:
            return self.entry.is_symlink()
        else:
            return super().is_symlink()

    def is_dir(self):
        if self.entry:
            return self.entry.is_dir()
        else:
            return super().is_dir()

    def is_file(self):
        if self.entry:
            return self.entry.is_file()
        else:
            return super().is_file()

    def is_junction(self):
        if self.entry:
            return self.entry.is_junction()
        else:
            return super().is_junction()

    def stat(self, *, follow_symlinks=True):
        if self.entry:
            return self.entry.stat(follow_symlinks=follow_symlinks)
        else:
            return super().stat(follow_symlinks=follow_symlinks)
