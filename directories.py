"""Shared library between client and server."""
from __future__ import annotations
from pathlib import Path
from hashlib import sha1
import json

BUFSIZE = 1024 ** 2


class File:
    """Represents a file in a directory hierarchy."""

    def __init__(self, name: str, hash: str):
        """Create file parameterized by name and its hash."""
        self.name = name
        self.hash = hash

    @classmethod
    def from_path(cls, path: Path) -> File:
        """Create a file from a file location on system, calculating hash."""
        name = path.name
        filehash = sha1()
        with path.open() as f:
            while data := f.read(BUFSIZE):
                filehash.update(data)
        hash = filehash.hexdigest()
        return cls(name, hash)

    def to_dict(self) -> dict:
        """Represent the file as a dict for JSON processing."""
        return {
            'type': 'file',
            'name': self.name,
            'hash': self.hash
        }

    def to_json(self) -> str:
        """Represent the file as a JSON string."""
        return json.dumps(self.to_dict())

    def copy(self) -> File:
        """Create a copy of the file."""
        return File(self.name, self.hash)

    def __eq__(self, other: File) -> bool:
        """Allow comparing files."""
        return self.name == other.name and self.hash == other.hash

    def __repr__(self):
        """Represent a file as string."""
        return f'{self.name}[{self.hash}]'


class Directory:
    """Represents a recursive directory holding files and subdirectories."""

    def __init__(self, name: str, contents: list[Directory | File]):
        """Initialize a directory with a name and a list of contents."""
        self.name = name
        self.contents = contents

    @classmethod
<<<<<<< HEAD
    def from_path(cls, path: Path | str) -> Directory:
=======
    def from_path(cls, path: Path | str) -> FileTree:
>>>>>>> 3625d12 (Added missing documentation and refactoring.)
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
<<<<<<< HEAD

    def copy(self) -> Directory:
        """Create a copy of the directory."""
        return Directory(self.name, [x.copy() for x in self.contents])
=======
>>>>>>> 3625d12 (Added missing documentation and refactoring.)

    def to_json(self) -> str:
        """Represent directory as JSON str."""
        return json.dumps(self.to_dict())

    def __eq__(self, other: Directory) -> bool:
        """Compare two directories recursively."""
        return self.name == other.name and self.contents == other.contents

    def __repr__(self):
        """Represent a directory as string."""
<<<<<<< HEAD
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
=======
        out = self.name + "{\n"
        for x in self.contents:
            match x:
                case File():
                    out += '    ' + repr(x) + "\n"
                case Directory():
                    out += '    ' + repr(x).replace("\n", "\n    ") + '\n'
        return out + '\n}'
>>>>>>> 3625d12 (Added missing documentation and refactoring.)


def decode(encoded: str) -> File | Directory:
    """Decode a json directory structure to class."""
    # TODO: process `loads` using curio in background
    # TODO: validate the json
    decode = json.loads(encoded)

    def parse(obj: dict) -> File | Directory:
        if obj['type'] == 'file':
            return File(obj['name'], obj['hash'])
        elif obj['type'] == 'directory':
            return Directory(obj['name'], [parse(c) for c in obj['contents']])

    return parse(decode)
