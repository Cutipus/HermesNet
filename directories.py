from __future__ import annotations
from pathlib import Path
from hashlib import sha1
import json

BUFSIZE = 1024 ** 2

class File:
    def __init__(self, name: str, hash: str):
        self.name = name
        self.hash = hash

    @classmethod
    def from_path(cls, path: Path):
        name = path.name
        filehash = sha1()
        with path.open() as f:
            while data := f.read(BUFSIZE):
                filehash.update(data)
        hash = filehash.hexdigest()
        return cls(name, hash)

    def to_dict(self) -> dict:
        return {'type': 'file', 'name': self.name, 'hash': self.hash}

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    def __eq__(self, other: File) -> bool:
        return self.name == other.name and self.hash == other.hash

    def __repr__(self):
        return f'{self.name}[{self.hash}]'


class Directory:
    def __init__(self, name: str, contents: list[Directory | File]):
        self.name = name
        self.contents = contents

    @classmethod
    def from_path(cls, path: Path | str) -> FileTree:
        path = Path(path)
        contents = []
        for x in path.iterdir():
            if x.is_file():
                contents.append(File.from_path(x))
            elif x.is_dir():
                contents.append(cls.from_path(x))
        return Directory(path.name, contents)

    def to_dict(self) -> dict:
        return {'type': 'directory', 'name': self.name, 'contents': [c.to_dict() for c in self.contents]}

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    def __eq__(self, other: Directory) -> bool:
        return self.name == other.name and self.contents == other.contents

    def __repr__(self):
        out = self.name + "{\n"
        for x in self.contents:
            match x:
                case File():
                    out += '    ' + repr(x) + "\n"
                case Directory():
                    out += '    ' + repr(x).replace("\n", "\n    ") + '\n'
        return out + '\n}'


def decode(encoded: str) -> File | Directory:
    # TODO: the `loads` method can be very time consuming - use curio to put it in background
    # TODO: validate the json
    decode = json.loads(encoded)
    def parse(obj: dict) -> File | Directory:
        if obj['type'] == 'file':
            return File(obj['name'], obj['hash'])
        elif obj['type']== 'directory':
            return Directory(obj['name'], [parse(c) for c in obj['contents']])
    return parse(decode)

