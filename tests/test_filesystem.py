from hermesnet.protocol import filesystem
import pathlib
import hashlib
import pytest


@pytest.fixture
def file() -> filesystem.File:
    return filesystem.File('Lorem', 'Ipsum', 400)  # technically an invalid object

@pytest.mark.asyncio
async def test_file_from_path(tmp_path: pathlib.Path) -> None:
    file_name = "hello world.txt"
    file_content = b"Hello, World!"
    _hash = hashlib.sha1()
    _hash.update(file_content)
    file_hash = _hash.hexdigest()
    test_file = tmp_path / file_name
    test_file.write_bytes(file_content)
    file = await filesystem.File.from_path(test_file)
    assert file == filesystem.File(file_name, file_hash, len(file_content))


def test_file_search(file: filesystem.File) -> None:
    assert file.search(file.name) is not None
    assert file.search(file.name+"meow") is None
    assert file.search(file.name[1:]) is not None
    assert file.search(file.name[:3]) is not None


# NOTE: Need a better way to generate this data
@pytest.mark.asyncio
async def test_directory_from_path(tmp_path: pathlib.Path):
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
    dir = await filesystem.Directory.from_path(dir_path)

    expected_dir = filesystem.Directory("test dir", [
            await filesystem.File.from_path(tmp_path / "test dir/byebye.txt"),
            await filesystem.File.from_path(tmp_path / "test dir/hello world.txt"),
            filesystem.Directory("Sub Directory", [
                    filesystem.Directory("SubSub Dir", [
                        await filesystem.File.from_path(tmp_path / "test dir" / "Sub Directory" / "SubSub Dir" / "Devlog.txt"),
                    ]),
            ]),
            filesystem.Directory("subdir", [
                    await filesystem.File.from_path(tmp_path / "test dir" / "subdir" / "hello world 2.txt"),
                    await filesystem.File.from_path(tmp_path / "test dir" / "subdir" / "Loremps.txt"),
            ]),
    ])
    unexpected_dir = filesystem.Directory("test dir", [
            await filesystem.File.from_path(tmp_path / "test dir/byebye.txt"),
            await filesystem.File.from_path(tmp_path / "test dir/hello world.txt"),
            filesystem.Directory("subdir", [
                    await filesystem.File.from_path(tmp_path / "test dir" / "subdir" / "hello world 2.txt"),
                    await filesystem.File.from_path(tmp_path / "test dir" / "subdir" / "Loremps.txt"),
            ]),
    ])
    assert dir == expected_dir
    assert unexpected_dir != expected_dir
