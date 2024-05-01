"""Tests for protocol/filesystem"""
# Imports
from __future__ import annotations
from hermesnet.protocol import filesystem
import pathlib
import pytest
from collections import Counter
from typing import Iterator, Literal, Optional, Protocol, Self, Sequence, TypedDict



# Protocols
class FileDict(TypedDict):
    """A dictionary representation of a File.

    Useful for serialization.
    """
    type: Literal['file']
    name: str
    hash: str
    size: int


class DirectoryDict(TypedDict):
    """A dictionary representation of a Directory.

    Useful for serialization.
    """
    type: Literal['directory']
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

    @classmethod
    def from_dict(cls, data: FileDict) -> Self:
        """Alternative constructor, creating a File from DictionaryDict."""
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

    @classmethod
    def from_dict(cls, data: DirectoryDict) -> Self:
        """Alternative constructor, creating a Directory from DictionaryDict."""
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
def file_class() -> type[File]:
    return filesystem.File


@pytest.fixture
def directory_class() -> type[Directory]:
    return filesystem.Directory


@pytest.fixture
def dir_path(tmp_path: pathlib.Path) -> pathlib.Path:
    d = tmp_path / "test dir"
    d.mkdir()
    (d / "byebye.txt").write_bytes(b"Sionara, World!")
    (d / "hello world.txt").write_bytes(b"Hello, World!")
    (d / "subdir").mkdir()
    (d / "subdir" / "Loremps.txt").write_bytes(b"Wow a loremp!")
    (d / "subdir" / "hello world 2.txt").write_bytes(b"Hello, World!")
    (d / "subdir" / "other_format.meow").write_bytes(b"238327!")
    (d / "Sub Directory").mkdir()
    (d / "Sub Directory" / "SubSub Dir").mkdir()
    (d / "Sub Directory" / "SubSub Dir" / "Devlog.txt").write_bytes(b"Hewwo, world!!")
    (d / "EmptySubdir").mkdir()
    return d


@pytest.fixture
def file_path(tmp_path: pathlib.Path) -> pathlib.Path:
    path = (tmp_path / "testFile.txt")
    path.write_bytes(b"Hello. World.")
    return path


@pytest.fixture
async def file(file_path: pathlib.Path) -> File:
    return await filesystem.File.from_path(file_path)


@pytest.fixture
async def dir(dir_path: pathlib.Path) -> Directory:
    return await filesystem.Directory.from_path(dir_path)


@pytest.fixture
async def empty_dir(tmp_path: pathlib.Path) -> Directory:
    (tmp_path / "empty_dir").mkdir()
    return await filesystem.Directory.from_path(tmp_path / "empty_dir")



# Tests
async def test_can_traverse_directory(dir: Directory):
    """Check that traversing the directory yields all the files therein."""
    expected_files: list[str] = ["byebye.txt", "hello world.txt", "Loremps.txt", "hello world 2.txt", "Devlog.txt", "other_format.meow"]
    actual_files: list[str] = []
    for x in dir:
        if isinstance(x, filesystem.File):
            actual_files.append(x.name)
    assert Counter(expected_files) == Counter(actual_files)


async def test_dir_from_dict_cancels_with_to_dict(dir: Directory):
    """Check that transforming a directory to dict and parsing it back returns the same directory."""
    assert dir == dir.from_dict(dir.to_dict())


async def test_searching_nothing_returns_none(dir: Directory) -> None:
    """Check that you get no results when looking for what isn't there."""
    assert dir.search('nothing here') is None


async def test_search_result_includes_all_files_with_matching_term(dir: Directory, file_class: type[File]) -> None:
    """Check that when searching a term, all and only files that contain the term are returned."""
    searched = dir.search('.txt')
    assert searched is not None
    matching_files = [file for file in dir if isinstance(file, file_class) and '.txt' in file]
    assert [file for file in searched if isinstance(file, file_class)] == matching_files


async def test_file_from_path_raises_error_when_bad_filepath(file_class: type[File]) -> None:
    """Check that providing a path of a nonexistent file raises an error."""
    with pytest.raises(FileNotFoundError):
        await file_class.from_path(pathlib.Path('/nonexistent_path'))


async def test_directory_from_path_raises_error_when_bad_dirpath(directory_class: type[Directory]) -> None:
    """Check that providing a path of a nonexistent file raises an error."""
    with pytest.raises(FileNotFoundError):
        await directory_class.from_path(pathlib.Path('/nonexistent_path'))


def test_directory_from_path_content_is_empty_when_path_empty_directory(empty_dir: Directory) -> None:
    """Check that an empty directory has no content."""
    assert len(empty_dir.contents) == 0


def test_directory_from_path_has_right_number_of_subdirectories(dir: Directory, directory_class: type[Directory]) -> None:
    """Check that the directory iterable contains all subdirectories, itself included."""
    assert len([d for d in dir if isinstance(d, directory_class)]) == 5
