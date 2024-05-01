"""The virtual filesystem that users can share.

The filesystem does not contain any file data by itself. Users need to request
data from each other to copy a filesystem.

Files and Directories can be encoded to JSON using the to_json methods and then
decoded using the decode method.

Classes:
    File: A file on the filesystem.
    Directory: A collection of files and directories.

Functions:
    decode: Decode a JSON string to a File or Directory.
    parse: Convert a dict to a File or Directory.
"""
from __future__ import annotations
from typing import Any, Iterator, Literal, Optional, Self, Sequence, TypeGuard, TypedDict, overload
from dataclasses import dataclass
import hashlib
import pathlib

import aiofiles
from aiofiles import os


_BUFSIZE = 1024 ** 2  # chunk size to read from disk


class FileDict(TypedDict):
    type: Literal['file']
    name: str
    hash: str
    size: int


def is_filedict(val: dict[Any, Any]) -> TypeGuard[FileDict]:
    try:
        return all((
                val['type'] == 'file',
                isinstance(val['name'], str),
                isinstance(val['hash'], str),
                isinstance(val['size'], int),
            ))
    except KeyError:
        return False


class DirectoryDict(TypedDict):
    type: Literal['directory']
    name: str
    contents: list[DirectoryDict | FileDict]


def is_directorydict(val: dict[Any, Any]) -> TypeGuard[DirectoryDict]:
    try:
        return all((
                val['type'] == 'directory',
                isinstance(val['name'], str),
                isinstance(val['contents'], list),
                all(is_directorydict(x) or is_filedict(x) for x in val['contents']),
            ))
    except KeyError:
        return False


@dataclass(eq=True)
class File:
    """Represents a file in a directory hierarchy.
    
    Attributes:
        name: The file's name.
        hash: The file's SHA1 hash.
        size: The size of the file in bytes.
    
    Methods:
        copy: Create a clone of the file.
        to_dict: Create a dictionary representation of the file..
        to_json: Create a JSON representation of the file.
        search: Check whether a file matches a search term or not.

    Class Methods:
        from_path: Create a File object representing of a file in the OS filesystem.
    """
    name: str
    hash: str
    size: int

    @classmethod
    async def from_path(cls, path: pathlib.Path) -> Self:
        """Create a file from a file location on system, calculating hash."""
        path = pathlib.Path(path)
        name = path.name
        filesize = (await os.stat(path)).st_size
        filehash = hashlib.sha1()
        async with aiofiles.open(path, "rb") as f:
            while data := await f.read(_BUFSIZE):
                filehash.update(data)
        hash = filehash.hexdigest()
        return cls(name, hash, filesize)

    @classmethod
    def from_dict(cls, data: FileDict) -> Self:
        return cls(data['name'], data['hash'], data['size'])

    def copy(self) -> Self:
        """Create a copy of the file."""
        return type(self)(self.name, self.hash, self.size)

    def to_dict(self) -> FileDict:
        """Represent the file as a dict for JSON processing."""
        return {
            'type': 'file',
            'name': self.name,
            'hash': self.hash,
            'size': self.size,
        }

    def __contains__(self, term: str) -> bool:
        """Checks whether the term matches the file's name.

        Parameters:
            term: The term to match against.
        """
        return term in self.name

    def __repr__(self):
        """Represent a file as string."""
        return f'{self.name}[{self.hash}][{self.size}]'


@dataclass(eq=True)
class Directory:
    """Represents a recursive directory holding files and subdirectories.

    Attributes:
        name: The directory's name.
        contents: The files and directories inside the directory.

    Methods:
        copy: Create a clone of the directory.
        to_dict: Create a dictionary representation of the directory..
        to_json: Create a JSON representation of the directory.
        search: Search a term in the directory. 

    Class Methods:
        from_path: Create a Directory object representing of a directory in the OS filesystem.

    Iteration:
        Directories are iterable, recursively traverse all files and subdirs.
    """
    name: str
    contents: Sequence[Self | File]

    @classmethod
    async def from_path(cls, path: pathlib.Path) -> Directory:
        """Create a directory from a directory path in file system."""
        contents: list[Directory | File] = []
        for name in await os.listdir(path):
            x = path / name
            if await os.path.isfile(x):
                contents.append(await File.from_path(x))
            elif await os.path.isdir(x):
                contents.append(await cls.from_path(x))
        return cls(path.name, contents)

    @classmethod
    def from_dict(cls, data: DirectoryDict) -> Self:
        return cls(data['name'], [_parse_dict_to_file_or_directory(x) for x in data['contents']])

    def to_dict(self) -> DirectoryDict:
        """Represent dictionary as dict."""
        return {
            'type': 'directory',
            'name': self.name,
            'contents': [c.to_dict() for c in self.contents]
        }

    def search(self, term: str) -> Optional[Self]:
        """Search a directory, return a clone of that directory with the non-matching files removed."""
        if term in self.name:
            return self.copy()
        name = self.name
        contents: Sequence[Self | File] = []
        for x in self.contents:
            if isinstance(x, Directory):
                if (searched := x.search(term)) is not None:
                    contents.append(searched)
            else:
                if term in x:
                    contents.append(x)
        if not contents:
            return None
        return type(self)(name, contents)

    def copy(self) -> Self:
        """Create a copy of the directory."""
        return type(self)(self.name, [x.copy() for x in self.contents])

    def __iter__(self) -> Iterator[Self | File]:
        """Iterate the directory tree."""
        yield self
        for x in self.contents:
            if isinstance(x, Directory):
                yield from x
            else:
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


@overload
def _parse_dict_to_file_or_directory(data: DirectoryDict) -> Directory: ...

@overload
def _parse_dict_to_file_or_directory(data: FileDict) -> File: ...

def _parse_dict_to_file_or_directory(data: DirectoryDict | FileDict) -> Directory | File:
    if data['type'] == 'file':
        return File.from_dict(data)
    else:
        return Directory.from_dict(data)
