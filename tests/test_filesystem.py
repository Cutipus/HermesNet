from hermesnet.protocol import filesystem
import pytest


@pytest.fixture
def file() -> filesystem.File:
    return filesystem.File('Lorem', 'Ipsum', 400)


def test_file_copy(file: filesystem.File) -> None:
    assert file.copy() == file

def test_file_repr(file: filesystem.File) -> None:
    assert repr(file) == 'Lorem[Ipsum][400]'

