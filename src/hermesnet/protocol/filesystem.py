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
from typing import Any, Generator, Mapping, Optional, Sequence, TypeGuard, TypedDict
from dataclasses import dataclass
import hashlib
import pathlib

import aiofiles
from aiofiles import os


_BUFSIZE = 1024 ** 2  # chunk size to read from disk


class FileDict(TypedDict):
    type: str
    name: str
    hash: str
    size: int


class DirectoryDict(TypedDict):
    type: str
    name: str
    contents: list[DirectoryDict | FileDict]


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
    async def from_path(cls, path: pathlib.Path | str) -> File:
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

    def copy(self) -> File:
        """Create a copy of the file."""
        return File(self.name, self.hash, self.size)

    def to_dict(self) -> FileDict:
        """Represent the file as a dict for JSON processing."""
        return {
            'type': 'file',
            'name': self.name,
            'hash': self.hash,
            'size': self.size,
        }

    def search(self, term: str) -> Optional[File]:
        """Checks whether the term matches the file's name.

        This method is called by Directory.search for duck-typing.

        Parameters:
            term: The term to match against.
        """
        return self if term in self.name else None

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
    contents: Sequence[Directory | File]

    @classmethod
    async def from_path(cls, path: pathlib.Path | str) -> Directory:
        """Create a directory from a directory path in file system."""
        path = pathlib.Path(path)
        contents: list[Directory | File] = []
        for name in await os.listdir(path):
            x = path / name
            if await os.path.isfile(x):
                contents.append(await File.from_path(x))
            elif await os.path.isdir(x):
                contents.append(await cls.from_path(x))
        return Directory(path.name, contents)

    def copy(self) -> Directory:
        """Create a copy of the directory."""
        return Directory(self.name, [x.copy() for x in self.contents])

    def to_dict(self) -> DirectoryDict:
        """Represent dictionary as dict."""
        return {
            'type': 'directory',
            'name': self.name,
            'contents': [c.to_dict() for c in self.contents]
        }

    def search(self, term: str) -> Optional[Directory]:
        """Search a directory, return a clone of that directory with the non-matching files removed."""
        search_result = self.copy()
        search_result.contents = [searched for y in search_result.contents if (searched := y.search(term))]
        if search_result.contents == []:
            return None
        return search_result

    def __iter__(self) -> Generator[Directory | File, None, None]:
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


async def read_directory(path: pathlib.Path) -> Directory:
    return await Directory.from_path(path)


async def read_file(path: pathlib.Path) -> File:
    return await File.from_path(path)


def parse(data: Mapping[str, Any]) -> File | Directory:
    """Parse dict to a File or Directory.
    
    Parameters:
        data: The dictionary to parse.

    Raises:
        ValueError: If the dict cannot be parsed.
    """

    def list_of_dicts(lst: Sequence[Any]) -> TypeGuard[list[dict[Any, Any]]]:
        return all(isinstance(item, dict) for item in lst)

    match data:
        case {'type': 'file', 'name': str(name), 'hash': str(hash), 'size': int(size)}:
            return File(name, hash, size)
        case {'type': 'directory', 'name': str(name), 'contents': content} if list_of_dicts(content):
            parsed_content = [parse(element) for element in content]
            return Directory(name, parsed_content)
        case _:
            raise ValueError("Bad dict")
