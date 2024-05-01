"""Tests for protocol/filesystem

Requirements:
    - when given an invalid path it should raise an error
    - when given a directory it should return an object with a name matching the directory
    - when given an empty directory it should return an object whose contents are an empty sequence
    - when given a directory with only files it should return 
    - you should be able to traverse a directory hierarchy
    - you should be able to list all the files in the directory
    - when you search for a term it should clump sub-hierarchis that match
    - you should be able to only view files with a certain extension
    - when you search for a term you should be able to see the hashes of all the files in the result
    - you should be able to know how many folders there are
"""
# Imports
from __future__ import annotations
from hermesnet.protocol import filesystem
import pathlib
import pytest
from collections import Counter
from typing import Iterator, Optional, Protocol, Self, Sequence, TypedDict



# Protocols
class FileDict(TypedDict):
    """A dictionary representation of a File.

    Useful for serialization.
    """
    type: str
    name: str
    hash: str
    size: int


class DirectoryDict(TypedDict):
    """A dictionary representation of a Directory.

    Useful for serialization.
    """
    type: str
    name: str
    contents: list[DirectoryDict | FileDict]


class File(Protocol):
    """A file in the system.

    Attributes:
        name: The file's name.
        hash: The calculated hash of the file's contents.
    """
    name: str
    hash: str

    @classmethod
    async def from_path(cls, path: pathlib.Path) -> Self:
        """Alternative constructor, creating a File object from a file path."""
        ...

    def to_dict(self) -> FileDict:
        """Convert the class instance to a dictionary."""
        ...

    def __contains__(self, term: str) -> bool:
        """Check if the file contains a string inside it."""
        ...


class Directory(Protocol):
    """A directory in the system.

    Attributes:
        name: The directory's name.
        contents: A sequence of subdirectories and files contained in the directory.
    """
    name: str

    @property  # declare it as immutable
    def contents(self) -> Sequence[Directory | File]: ...

    @classmethod
    async def from_path(cls, path: pathlib.Path) -> Self:
        """Alternative constructor, creating a Directory object from a directory path."""
        ...

    def to_dict(self) -> DirectoryDict:
        """Convert the directory to a dictionary."""
        ...

    def __iter__(self) -> Iterator[File | Directory]:
        """Traverse the directory hierarchy."""
        ...

    def search(self, term: str) -> Optional[Self]:
        """Filter a term from the directory hierarchy.
        
        The returned directory should not have 
        """
        ...



# Fixtures
@pytest.fixture
def tmp_dir_path(tmp_path: pathlib.Path) -> pathlib.Path:
    d = tmp_path / "test dir"
    d.mkdir()
    (d / "byebye.txt").write_bytes(b"Sionara, World!")
    (d / "hello world.txt").write_bytes(b"Hello, World!")
    (d / "subdir").mkdir()
    (d / "subdir" / "Loremps.txt").write_bytes(b"Wow a loremp!")
    (d / "subdir" / "hello world 2.txt").write_bytes(b"Hello, World!")
    (d / "Sub Directory").mkdir()
    (d / "Sub Directory" / "SubSub Dir").mkdir()
    (d / "Sub Directory" / "SubSub Dir" / "Devlog.txt").write_bytes(b"Hewwo, world!!")
    return d


@pytest.fixture
def tmp_file_path(tmp_path: pathlib.Path) -> pathlib.Path:
    path = (tmp_path / "testFile.txt")
    path.write_bytes(b"Hello. World.")
    return path


@pytest.fixture
async def tmp_file(tmp_file_path: pathlib.Path) -> File:
    return await filesystem.File.from_path(tmp_file_path)


@pytest.fixture
async def tmp_dir(tmp_dir_path: pathlib.Path) -> Directory:
    return await filesystem.Directory.from_path(tmp_dir_path)



# Tests
async def test_can_traverse(tmp_dir: Directory):
    """Check that traversing the directory yields all the files therein."""
    expected_files: list[str] = ["byebye.txt", "hello world.txt", "Loremps.txt", "hello world 2.txt", "Devlog.txt"]
    actual_files: list[str] = []
    for x in tmp_dir:
        if isinstance(x, filesystem.File):
            actual_files.append(x.name)
    assert Counter(expected_files) == Counter(actual_files)


async def test_to_dict_and_parse_is_equal(tmp_dir: Directory):
    """Check that transforming a directory to dict and parsing it back returns the same directory."""
    assert tmp_dir == filesystem.parse(tmp_dir.to_dict())


async def test_searching_nothing_returns_none(tmp_dir: Directory) -> None:
    assert tmp_dir.search('nothing here') is None


async def test_search_result_includes_all_results(tmp_dir: Directory) -> None:
    searched = tmp_dir.search('world')
    assert searched is not None
    assert len(searched.contents) == 2
    for x in searched:
        if isinstance(x, filesystem.File):
            assert 'world' in x.name
