"""Shared library between client and server."""
from __future__ import annotations
from pathlib import Path
from hashlib import sha1
import json
from typing import Any, Sequence

BUFSIZE = 1024 ** 2


class File:
    """Represents a file in a directory hierarchy."""

    def __init__(self, name: str, hash: str, filesize: int):
        """Create file parameterized by name and its hash."""
        self.name = name
        self.hash = hash
        self.size = filesize

    @classmethod
    def from_path(cls, path: Path) -> File:
        """Create a file from a file location on system, calculating hash."""
        name = path.name
        filesize = path.stat().st_size
        filehash = sha1()
        with path.open("rb") as f:
            while data := f.read(BUFSIZE):
                filehash.update(data)
        hash = filehash.hexdigest()
        return cls(name, hash, filesize)

    def to_dict(self) -> dict:
        """Represent the file as a dict for JSON processing."""
        return {
            'type': 'file',
            'name': self.name,
            'hash': self.hash,
            'size': self.size,
        }

    def to_json(self) -> str:
        """Represent the file as a JSON string."""
        return json.dumps(self.to_dict())

    def copy(self) -> File:
        """Create a copy of the file."""
        return File(self.name, self.hash, self.size)

    def __eq__(self, other: File) -> bool:
        """Allow comparing files."""
        return self.name == other.name and self.hash == other.hash

    def __repr__(self):
        """Represent a file as string."""
        return f'{self.name}[{self.hash}][{self.size}]'


class Directory:
    """Represents a recursive directory holding files and subdirectories."""

    def __init__(self, name: str, contents: Sequence[Directory | File]):
        """Initialize a directory with a name and a list of contents."""
        self.name = name
        self.contents = contents

    @classmethod
    def from_path(cls, path: Path | str) -> Directory:
        """Create a directory from a directory path in file system."""
        path = Path(path)
        contents = []
        for x in path.iterdir():
            if x.is_file():
                contents.append(File.from_path(x))
            elif x.is_dir():
                contents.append(cls.from_path(x))
        return Directory(path.name, contents)

    def to_dict(self) -> dict:
        """Represent dictionary as dict."""
        return {
            'type': 'directory',
            'name': self.name,
            'contents': [c.to_dict() for c in self.contents]
        }

    def copy(self) -> Directory:
        """Create a copy of the directory."""
        return Directory(self.name, [x.copy() for x in self.contents])

    def to_json(self) -> str:
        """Represent directory as JSON str."""
        return json.dumps(self.to_dict())

    def __eq__(self, other: Directory) -> bool:
        """Compare two directories recursively."""
        return self.name == other.name and self.contents == other.contents

    def __iter__(self):
        """Iterate the directory tree."""
        yield self
        for x in self.contents:
            if isinstance(x, Directory):
                yield from x
            elif isinstance(x, File):
                yield x

    def __repr__(self):
        """Represent a directory as string."""
        out = self.name
        if not self.contents:
            out += '/{}'
        elif len(self.contents) == 1:
            out += '/' + repr(self.contents[0])
        else:
            out += "{"
            for x in self.contents:
                match x:
                    case File():
                        out += '\n    ' + repr(x)
                    case Directory():
                        out += '\n    ' + repr(x).replace("\n", "\n    ")
            out += '\n}'
        return out


def decode(encoded: bytes | str) -> File | Directory:
    """Decode a json directory structure to class.

    Raise an exception if it doesn't match the pattern expected by either.
    """
    # TODO: process `loads` using curio in background
    loaded: dict = json.loads(encoded)
    return parse(loaded)


def parse(json_decode: dict) -> File | Directory:
    """Parse dict back to File | Directory."""
    match json_decode:
        case {'type': 'file', 'name': str(name), 'hash': str(hash), 'size': int(size)}:
            return File(name, hash, size)
        case {'type': 'directory', 'name': str(name), 'contents': list(contents)}:  #
            return Directory(name, [parse(element) for element in contents])
        case _:
            raise ValueError("Bad JSON")
