"""
- when given an invalid path it should raise an error
- when given a directory it should return an object with a name matching the directory
- when given an empty directory it should return an object who's contents are an empty sequence
- when given a directory with only files it should return 
- you should be able to traverse a directory hierarchy
- you should be able to list all the files in the directory
- when you search for a term it should clump sub-hierarchis that match
- you should be able to only view files with a certain extension
- when you search for a term you should be able to see the hashes of all the files in the result
- you should be able to know how many folders there are
"""
from __future__ import annotations
from hermesnet.protocol import filesystem
import pathlib
import pytest
from collections import Counter
from typing import Iterator, Protocol, TypedDict


# Protocols
class FileDict(TypedDict):
    type: str
    name: str
    hash: str
    size: int

class File(Protocol):
    name: str
    hash: str

    def to_dict(self) -> FileDict:
        ...


class DirectoryDict(TypedDict):
    type: str
    name: str
    contents: list[DirectoryDict | FileDict]

class Directory(Protocol):
    def to_dict(self) -> DirectoryDict:
        ...

    def __iter__(self) -> Iterator[File | Directory]:
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
    expected_files: list[str] = ["byebye.txt", "hello world.txt", "Loremps.txt", "hello world 2.txt", "Devlog.txt"]
    actual_files: list[str] = []
    for x in tmp_dir:
        if isinstance(x, filesystem.File):
            actual_files.append(x.name)
    assert Counter(expected_files) == Counter(actual_files)


async def test_can_encode_decode(tmp_dir: Directory):
    assert tmp_dir == filesystem.parse(tmp_dir.to_dict())


async def test_file_search(tmp_file_path: pathlib.Path) -> None:
    file: filesystem.File = await filesystem.read_file(tmp_file_path)
    assert file.search(file.name) is not None
    assert file.search(file.name+"meow") is None
    assert file.search(file.name[1:]) is not None
    assert file.search(file.name[:3]) is not None


async def test_directory_search(tmp_dir_path: pathlib.Path) -> None:
    dir = await filesystem.read_directory(tmp_dir_path)
    assert dir.search('nothing here') is None
    searched = dir.search('world')
    assert searched is not None
    assert len(searched.contents) == 2
    for x in searched:
        if isinstance(x, filesystem.File):
            assert 'world' in x.name
