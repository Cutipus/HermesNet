from hermesnet.protocol import filesystem
import pathlib
import hashlib
import pytest
import json


@pytest.fixture
def file() -> filesystem.File:
    return filesystem.File('Lorem', 'Ipsum', 400)

# NOTE: Is this a good idea?
@pytest.fixture
def directory() -> filesystem.Directory:
    return filesystem.Directory("meow", contents=[
            filesystem.File("hello", "world", 24)
    ])


def test_file_copy(file: filesystem.File) -> None:
    assert file.copy() == file


def test_file_repr(file: filesystem.File) -> None:
    assert repr(file) == 'Lorem[Ipsum][400]'


def test_file_from_path(tmp_path: pathlib.Path) -> None:
    file_name = "hello world.txt"
    file_content = b"Hello, World!"
    _hash = hashlib.sha1()
    _hash.update(file_content)
    file_hash = _hash.hexdigest()
    test_file = tmp_path / file_name
    test_file.write_bytes(file_content)
    file = filesystem.File.from_path(test_file)
    assert file == filesystem.File(file_name, file_hash, len(file_content))


# NOTE: Unnecessary to check
def test_file_to_dict(file: filesystem.File) -> None:
    assert file.to_dict() == {
            'type': 'file',
            'name': file.name,
            'hash': file.hash,
            'size': file.size,
    }


# NOTE: Unnecessary to check
def test_file_to_json(file: filesystem.File) -> None:
    assert file.to_json() == json.dumps({
            'type': 'file',
            'name': file.name,
            'hash': file.hash,
            'size': file.size,
    })


def test_file_search(file: filesystem.File) -> None:
    assert file.search(file.name) is not None
    assert file.search(file.name+"meow") is None
    assert file.search(file.name[1:]) is not None
    assert file.search(file.name[:3]) is not None


# NOTE: Unnecessary
def test_directory_copy(directory: filesystem.Directory) -> None:
    assert directory.copy() == directory


# NOTE: Need a better way to generate this data
def test_directory_from_path(tmp_path: pathlib.Path):
    def create_test_dir(tmp_path: pathlib.Path) -> pathlib.Path:
        d = tmp_path / "test dir"
        d.mkdir()
        (d / "byebye.txt").write_bytes(b"Sionara, World!")
        (d / "hello world.txt").write_bytes(b"Hello, World!")
        subdir1 = d / "subdir"
        subdir1.mkdir()
        (subdir1 / "Loremps.txt").write_bytes(b"Wow a loremp!")
        (subdir1 / "hello world 2.txt").write_bytes(b"Hello, World!")
        subdir2 = d / "Sub Directory"
        subdir2.mkdir()
        subdir3 = subdir2 / "SubSub Dir"
        subdir3.mkdir()
        (subdir3 / "Devlog.txt").write_bytes(b"Hewwo, world!!")
        return d

    dir_path = create_test_dir(tmp_path)
    dir = filesystem.Directory.from_path(dir_path)

    expected_dir = filesystem.Directory("test dir", [
            filesystem.File.from_path(tmp_path / "test dir/byebye.txt"),
            filesystem.File.from_path(tmp_path / "test dir/hello world.txt"),
            filesystem.Directory("Sub Directory", [
                    filesystem.Directory("SubSub Dir", [
                        filesystem.File.from_path(tmp_path / "test dir" / "Sub Directory" / "SubSub Dir" / "Devlog.txt"),
                    ]),
            ]),
            filesystem.Directory("subdir", [
                    filesystem.File.from_path(tmp_path / "test dir" / "subdir" / "hello world 2.txt"),
                    filesystem.File.from_path(tmp_path / "test dir" / "subdir" / "Loremps.txt"),
            ]),
    ])
    unexpected_dir = filesystem.Directory("test dir", [
            filesystem.File.from_path(tmp_path / "test dir/byebye.txt"),
            filesystem.File.from_path(tmp_path / "test dir/hello world.txt"),
            filesystem.Directory("subdir", [
                    filesystem.File.from_path(tmp_path / "test dir" / "subdir" / "hello world 2.txt"),
                    filesystem.File.from_path(tmp_path / "test dir" / "subdir" / "Loremps.txt"),
            ]),
    ])
    assert dir == expected_dir
    assert unexpected_dir != expected_dir
