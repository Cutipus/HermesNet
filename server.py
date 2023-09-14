from __future__ import annotations

import logging
from signal import signal, SIGINT

from curio import run, tcp_server
from pathlib import Path
import json

KILOBYTE = 1024

declared_dirs = []

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
    def from_path(cls, path: Path) -> FileTree:
        path = Path(path) # extra verification
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
    decode = json.loads(encoded)
    def parse(obj: dict) -> File | Directory:
        if obj['type'] == 'file':
            return File(obj['name'], obj['hash'])
        elif obj['type']== 'directory':
            return Directory(obj['name'], [parse(c) for c in obj['contents']])
    return parse(decode)


async def receive_message(client, addr):
    # responsible for retrieving a single request from a client
    print('Connection from', addr)
    msg = bytearray()
    while True:
        data = await client.recv(KILOBYTE)
        if not data:
            break
        msg += data
    print('Message received')
    response = await process_message(msg)
    await client.sendall(response)


async def process_message(msg: bytearray) -> bytes:
    # parses the message and returns a reply
    # this server should return the ip addresses and data ranges of clients for specific files
    # therefore, the msg should include info on the file in question
    # a client can find info on a speciic file
    # or retrieve a list of files via search
    # the client-tracker protocol should be implemented here
    # first the message is unwrapped from the communication protocol
    # it is then processed
    # lastly the response is wrapped in the communication protocol and returned
    # TODO: handle search queries
    msg = msg.decode()
    if msg == 'ping':
        print("Ping received")
        return b"I'm awake!"
    elif msg.startswith('DECLAREDIR'):
        print("Dir declaration received")
        dir = decode(msg.split(maxsplit=1)[1])
        print(dir)
        declared_dirs.append(dir)
        return f'Sure mate, {dir.name} was added'.encode()
    # elif msg.startswith('SEARCH'): ...


if __name__ == '__main__':
    print('Started. Currently supports "ping" and "declare" command(s).')
    try:
        run(tcp_server, '', 25000, receive_message)
    except KeyboardInterrupt:
        print("Server shutting down...")
