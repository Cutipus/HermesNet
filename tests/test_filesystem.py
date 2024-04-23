from hermesnet.protocol import filesystem
import pathlib
import hashlib
import pytest
import json


@pytest.fixture
def file() -> filesystem.File:
    return filesystem.File('Lorem', 'Ipsum', 400)


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


def test_file_copy(file: filesystem.File) -> None:
    assert file.copy() == file


def test_file_repr(file: filesystem.File) -> None:
    assert repr(file) == 'Lorem[Ipsum][400]'


def test_file_from_path(tmp_path: pathlib.Path) -> None:
    # test_dir = create_test_dir(tmp_path)
    file_name = "hello world.txt"
    file_content = b"Hello, World!"
    _hash = hashlib.sha1()
    _hash.update(file_content)
    file_hash = _hash.hexdigest()
    test_file = tmp_path / file_name
    test_file.write_bytes(file_content)
    file = filesystem.File.from_path(test_file)
    assert file == filesystem.File(file_name, file_hash, len(file_content))


def test_file_to_dict(file: filesystem.File) -> None:
    assert file.to_dict() == {
            'type': 'file',
            'name': file.name,
            'hash': file.hash,
            'size': file.size,
    }


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