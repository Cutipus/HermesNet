"""Defines the client-server communication protocol"""

from __future__ import annotations
from dataclasses import dataclass
from json import dumps, loads
from typing import ClassVar, NamedTuple, Self, Protocol
from directories import Directory, decode, parse

CHUNK_SIZE = 1024
FRAME_SIZE = 4
COMMAND_SIZE = 1


class Socket(Protocol):
    async def sendall(self, data: bytes):
        ...

    async def recv(self, maxsize: int) -> bytes:
        ...


async def read_message(socket: Socket) -> ServerMessage:
    """Send a message to the server."""
    # TODO: custom ServerMessage in case of error
    message_length = int.from_bytes(await socket.recv(FRAME_SIZE))
    msg = bytearray()
    while len(msg) < message_length and (chunk := await socket.recv(CHUNK_SIZE)):
        msg += chunk

    return ServerMessage.from_bytes(msg)


async def send_message(socket: Socket, message: ServerMessage):
    """Read a message from the server."""
    encoded_message = bytes(message)
    await socket.sendall(len(encoded_message).to_bytes(FRAME_SIZE) + encoded_message)


class User(NamedTuple):
    """Represents a user."""
    username: str
    ip_address: str


@dataclass(kw_only=True)
class ServerMessage():
    """Class for representing a message to send to the server."""
    _registered_message_types: ClassVar[dict[int, type]] = dict()
    command: int

    @classmethod
    def from_bytes(cls, bts: bytes) -> Self:
        """Decode a message prefixed by a byte denoting its type."""
        bytecode: int = int.from_bytes(bts[:COMMAND_SIZE])
        if bytecode not in cls._registered_message_types:
            raise TypeError(f"{bytecode} is an unsupported command code.")
        if rest_of_data := bts[COMMAND_SIZE]:
            return cls._registered_message_types[bytecode].from_bytes(rest_of_data)
        else:
            return cls._registered_message_types[bytecode]()

    def __init_subclass__(cls, **kwargs):
        """Register new subclasses of ServerMessage based on their commandcode."""
        if cls.command in cls._registered_message_types:
            raise TypeError(f"Already exists a message class with command code {cls.command}.")
        cls._registered_message_types[cls.command] = cls
        super().__init_subclass__(**kwargs)

    def __bytes__(self) -> bytes:
        return self.command.to_bytes(1)

@dataclass(kw_only=True)
class Login(ServerMessage):
    """Initial login message to be sent at every connection start."""
    username: str
    password: str
    command: int = 30

    def __bytes__(self) -> bytes:
        return super().__bytes__() + f'{self.username}:{self.password}'.encode()

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        """"""
        username, password = data.decode().split(':')
        return cls(username=username, password=password)


@dataclass(kw_only=True)
class Ping(ServerMessage):
    """Ping message - to be responded by Pong."""
    command: int = 10
    message: str = "Sup!"

    def __bytes__(self) -> bytes:
        return super().__bytes__() + self.message.encode()

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        return cls(message=data.decode())


@dataclass(kw_only=True)
class Pong(ServerMessage):
    """Response to Ping."""
    command: int = 11
    message: str = "Eyo!!"

    def __bytes__(self) -> bytes:
        return super().__bytes__() + self.message.encode()

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        return cls(message=data.decode())

@dataclass(kw_only=True)
class All(ServerMessage):
    """Ask for all the directories declared on the server."""
    command: int = 20


@dataclass(kw_only=True)
class Ok(ServerMessage):
    """Operation was successful."""
    command: int = 1


@dataclass(kw_only=True)
class Error(ServerMessage):
    """Generic error message."""
    command: int = 80
    error_text: str

    def __bytes__(self) -> bytes:
        return super().__bytes__() + self.error_text.encode()

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        return cls(error_text=data.decode())


@dataclass(kw_only=True)
class Declare(ServerMessage):
    """Declare a directory structure in the server."""
    command: int = 15
    directory: Directory

    def __bytes__(self) -> bytes:
        return super().__bytes__() + self.directory.to_json().encode()

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        directory = decode(data)
        if not isinstance(directory, Directory):
            raise TypeError("Not a directory!")
        return cls(directory=directory)


@dataclass(kw_only=True)
class Search(ServerMessage):
    """Search for specific pattern in all declared directories on server."""
    command: int = 40
    search_term: str

    def __bytes__(self) -> bytes:
        return super().__bytes__() + self.search_term.encode()

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        return cls(search_term=data.decode())


@dataclass(kw_only=True)
class SearchResults(ServerMessage):
    """Results of search operation."""
    command: int = 41
    results: list[tuple[User, Directory]]

    def __bytes__(self) -> bytes:
        return super().__bytes__() + dumps(self.results, default=lambda x: x.to_dict()).encode()

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        results: list[tuple[User, Directory]]= []
        for (username, ip_addr), directory_dict in loads(data):
            directory = parse(directory_dict)
            if not isinstance(directory, Directory):
                raise TypeError(f"{directory} is not a Directory")
            results.append((User(username, ip_addr), directory))
        return cls(results=results)


@dataclass(kw_only=True)
class NoUsers(ServerMessage):
    """No users for query."""
    command: int = 81


@dataclass(kw_only=True)
class Query(ServerMessage):
    """Send hash to server and retrieve all clients with that file."""
    command: int = 43
    file_hash: str

    def __bytes__(self) -> bytes:
        return super().__bytes__() + self.file_hash.encode()

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        return cls(file_hash=data.decode())


@dataclass(kw_only=True)
class QuerySearchResults(ServerMessage):
    """Results of search operation."""
    command: int = 42
    results: list[User]

    def __bytes__(self) -> bytes:
        return super().__bytes__() + dumps(self.results).encode()

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        return cls(results=[User(name, addr) for name, addr in loads(data)])
