"""Represents the messages that can be communicated in the protocol.

Specification:
    A message is a simple object that can be encoded and decoded to and from bytes.
    These messages are generated by clients and servers using the protocol.
    Every message type is represented by a class, and has a `command` variable that represents its type.

Constants:
    COMMAND_SIZE: The amount of bytes to represent the type of the message.

Functions:
    from_bytes: Get a concrete Message object from bytes.

Classes:
    User: Represents a client for other clients to communicate with.
    ServerMessage: An abstract class representing a message used in Protocol.
    Login: A login request sent by client.
    WrongPassword: A response indicating unauthorized login request.
    Ping: A blank message to check the server is still online.
    Pong: A server response to the ping message.
    All: A request for all data on all users in the server.
    Ok: A generic response for an operation that was successful.
    Error: A generic response for an error.
    Declare: A request declaring a directory.
    Search: A request to search for a term in all other users' declared directories.
    SearchResults: A response with the results of a Search/All operation.
    Fin: The final message sent in the Protocol.
    Query: A request to find all users that have declared some file.
    QuerySearchResults: A response to Query with all the users.
"""
# imports
from abc import ABC
from typing import Any, ClassVar, NamedTuple, Self, TypeGuard
from dataclasses import dataclass
import json
from hermesnet.protocol import filesystem


# consts
COMMAND_SIZE = 1


# types
type JSON = dict[str, 'JSON'] | list['JSON'] | str | int | float | bool | None


# classes
class User(NamedTuple):
    """Represents a user."""
    username: str
    ip_address: str


@dataclass
class ServerMessage(ABC):
    """Class for representing a message to send to the server."""
    _registered_message_types: ClassVar[dict[int, type[Self]]] = dict()
    command: ClassVar[int]

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        """Decode a message prefixed by a byte denoting its type."""
        if not data:
            raise ValueError(f"No data to decode.")

        bytecode: int = int.from_bytes(data[:COMMAND_SIZE])
        if bytecode not in cls._registered_message_types:
            raise ValueError(f"{bytecode} is an unsupported command code.")

        message_data = data[COMMAND_SIZE:]
        return cls._registered_message_types[bytecode]._from_bytes(message_data)

    @classmethod
    def _from_bytes(cls, data: bytes) -> Self:
        return cls()

    def __init_subclass__(cls, **kwargs: dict[Any, Any]):
        """Register new subclasses of ServerMessage based on their commandcode."""
        if cls.command in cls._registered_message_types:
            raise TypeError(f"Already exists a message class with command code {cls.command}.")
        cls._registered_message_types[cls.command] = cls
        super().__init_subclass__(**kwargs)

    def __bytes__(self) -> bytes:
        return self.command.to_bytes(COMMAND_SIZE)


@dataclass
class Login(ServerMessage):
    """Initial login message to be sent at every connection start."""
    command: ClassVar[int] = 30
    username: str
    password: str

    def __bytes__(self) -> bytes:
        return super().__bytes__() + f'{self.username}:{self.password}'.encode()

    @classmethod
    def _from_bytes(cls, data: bytes) -> Self:
        username, password = data.decode().split(':')
        return cls(username=username, password=password)


@dataclass
class WrongPassword(ServerMessage):
    command: ClassVar[int] = 19


@dataclass
class Ping(ServerMessage):
    """Ping message - to be responded by Pong."""
    command: ClassVar[int] = 10
    message: str = "Sup!"

    def __bytes__(self) -> bytes:
        return super().__bytes__() + self.message.encode()

    @classmethod
    def _from_bytes(cls, data: bytes) -> Self:
        return cls(message=data.decode())


@dataclass
class Pong(ServerMessage):
    """Response to Ping."""
    command: ClassVar[int] = 11
    message: str = "Eyo!!"

    def __bytes__(self) -> bytes:
        return super().__bytes__() + self.message.encode()

    @classmethod
    def _from_bytes(cls, data: bytes) -> Self:
        return cls(message=data.decode())


@dataclass
class All(ServerMessage):
    """Ask for all the directories declared on the server."""
    command: ClassVar[int] = 20


@dataclass
class Ok(ServerMessage):
    """Operation was successful."""
    command: ClassVar[int] = 1


@dataclass
class Error(ServerMessage):
    """Generic error message."""
    command: ClassVar[int] = 80
    error_text: str

    def __bytes__(self) -> bytes:
        return super().__bytes__() + self.error_text.encode()

    @classmethod
    def _from_bytes(cls, data: bytes) -> Self:
        return cls(error_text=data.decode())


@dataclass
class Declare(ServerMessage):
    """Declare a directory structure in the server."""
    command: ClassVar[int] = 15
    directory: filesystem.Directory

    def __bytes__(self) -> bytes:
        return super().__bytes__() + json.dumps(self.directory.to_dict()).encode()

    @classmethod
    def _from_bytes(cls, data: bytes) -> Self:
        try:
            directory_dict: JSON = json.loads(data)
        except json.JSONDecodeError:
            raise ValueError("Can't parse data from JSON.")
        if not isinstance(directory_dict, dict):
            raise ValueError('Data should be a dictionary.')
        if not filesystem.is_directorydict(directory_dict):
            raise ValueError("Data does not conform to DirectoryDict rules.")
        directory = filesystem.Directory.from_dict(directory_dict)
        return cls(directory=directory)


@dataclass
class Search(ServerMessage):
    """Search for specific pattern in all declared directories on server."""
    command: ClassVar[int] = 40
    search_term: str

    def __bytes__(self) -> bytes:
        return super().__bytes__() + self.search_term.encode()

    @classmethod
    def _from_bytes(cls, data: bytes) -> Self:
        return cls(search_term=data.decode())


@dataclass
class SearchResults(ServerMessage):
    """Results of search operation."""
    command: ClassVar[int] = 41
    results: dict[User, list[filesystem.Directory]]

    def __bytes__(self) -> bytes:
        basic_results = [((name, ip), [d.to_dict() for d in dirs]) for (name, ip), dirs in self.results.items()]
        return super().__bytes__() + json.dumps(basic_results).encode()

    @staticmethod
    def _is_list_of(val: dict[Any, Any]) -> dict[User, list[filesystem.DirectoryDict]]:
        ...

    @classmethod
    def _from_bytes(cls, data: bytes) -> Self:
        # can raise ValueError
        results: dict[User, list[filesystem.Directory]] = dict()

        try:
            parsed: JSON = json.loads(data)
        except json.JSONDecodeError:
            raise ValueError(f"Can't parse {data}")
        if not isinstance(parsed, list):
            raise ValueError(f"Can't parse {data}")

        for entry in parsed:
            if not cls._is_entry(entry):
                raise ValueError(f"Can't parse data - not an entry: {data}")
            (username, ip_addr), directory_dicts = entry
            user = User(username, ip_addr)
            dirs: list[filesystem.Directory] = []

            for dir_dict in directory_dicts:
                if not isinstance(dir_dict, dict):
                    raise ValueError(f"Can't parse, should be a dictionary: {dir_dict}")
                if not filesystem.is_directorydict(dir_dict):
                    raise ValueError(f"Can't parse, doesn't conform to DirectoryDict: {dir_dict}")
                dirs.append(filesystem.Directory.from_dict(dir_dict))
            results[user] = dirs
        return cls(results=results)

    @staticmethod
    def _is_entry(val: JSON) -> TypeGuard[tuple[tuple[str, str], list[JSON]]]:
        try:
            return isinstance(val, list) \
                    and isinstance(val[0], list) \
                    and isinstance(val[0][0], str) \
                    and isinstance(val[0][1], str) \
                    and isinstance(val[1], list)
        except (IndexError, TypeError):
            return False


@dataclass
class Fin(ServerMessage):
    """Stop communication."""
    command: ClassVar[int] = 75


@dataclass
class Query(ServerMessage):
    """Send hash to server and retrieve all clients with that file."""
    command: ClassVar[int] = 43
    file_hash: str

    def __bytes__(self) -> bytes:
        return super().__bytes__() + self.file_hash.encode()

    @classmethod
    def _from_bytes(cls, data: bytes) -> Self:
        return cls(file_hash=data.decode())


@dataclass
class QuerySearchResults(ServerMessage):
    """Results of search operation."""
    command: ClassVar[int] = 42
    results: list[User]

    def __bytes__(self) -> bytes:
        return super().__bytes__() + json.dumps(self.results).encode()

    @classmethod
    def _from_bytes(cls, data: bytes) -> Self:
        # can raise json.decoder.JSONDecoderError
        try:
            parsed: JSON = json.loads(data) # NOTE: no type for list of size 2
        except json.JSONDecodeError:
            raise ValueError(f"Can't parse {data}")
        if not cls._is_list_of_lists_of_two_strings(parsed):
            raise ValueError(f"Can't parse {data}")
        return cls(results=[User(name, addr) for name, addr in parsed])
    
    @staticmethod
    def _is_list_of_lists_of_two_strings(val: JSON) -> TypeGuard[list[tuple[str, str]]]:
        if not isinstance(val, list):
            return False
        for subval in val:
            try:
                if not (isinstance(subval, list) and isinstance(subval[0], str) and isinstance(subval[1], str)):
                    return False
            except IndexError:
                return False
        return True


# functions
def from_bytes(data: bytes) -> ServerMessage:
    return ServerMessage.from_bytes(data)
