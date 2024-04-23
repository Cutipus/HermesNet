"""Defines the processor that handles requests for the server.

Classes:
    Processor: Manages processing requests and responses with clients.
    UserManager: Manages a pool of users and their states.
    LoggedInUser: Represents a connected logged-in user.
    LoggedOutUser: Represents a logged-in user that just disconnected.
    OnlineGuest: Represents a connected unregistered user.
    OfflineGuest: Represents an unregistered user that just disconnected.

Types:
    ConnectedUser: A user that is currently connected.
    DisconnectedUser: A user that has just disconnected.

Logging:
    Logging functionality is provided.

Example:
    async def main():
        g = Processor()
        with await g.add_client(('ip.ad.re.ss', 6969)) as requests, responses:
            request = Ping()
            await requests.put(request)
            response = await responses.get()
            print(respnse)

    if __name__ == '__main__':
        curio.run(main())
"""

# stdlib
from __future__ import annotations
from dataclasses import field, dataclass
import datetime
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

# curio
import asyncio

# project
from .. import protocol as sprotocol


logger = logging.getLogger(__name__)
USER_EXPIRY_TIMER = datetime.timedelta(minutes=5)

type ConnectedUser = LoggedInUser | OnlineGuest
type DisconnectedUser = LoggedOutUser | OfflineGuest


@dataclass
class LoggedInUser:
    """A class to represent a logged-in user.

    Attributes:
        addr: The IP/port address of the user.
        name: The user's username.
        password: The user's password.
        declared_dirs: The directories the user has declared .

    Methods:
        declare_dir: Declare a directory.
        to_tuple: Convert the user into a protocol-compliant user.
    """
    addr: tuple[str, int]
    name: str
    password: str
    declared_dirs: list[sprotocol.Directory] = field(default_factory=list)

    def decalre_dir(self, dir: sprotocol.Directory):
        """Declare a directory, adding it to self.declared_dirs.
        
        Parameters:
            dir: The directory to declare.
        """
        self.declared_dirs.append(dir)
    
    def to_tuple(self) -> sprotocol.User:
        """Convert the user to a NamedTuple User as defined by the protocol."""
        return sprotocol.User(self.name, self.addr[0])


@dataclass
class LoggedOutUser:
    """A class to represent a logged-in user that has disconnected.

    Attributes:
        name: The user's name.
        password: The user's password.
        last_connected: The time when the user disconnected.
    """
    name: str
    password: str
    last_connected: datetime.datetime = field(default_factory=datetime.datetime.now)


@dataclass
class OnlineGuest:
    """A class to represent a guest user that is connected.

    Attributes:
        addr: The user's IP/port address.
    """
    addr: tuple[str, int]


@dataclass
class OfflineGuest:
    """A class to represent an online guest that has disconnected.
    
    Attributes:
        last_connected: The time when the user disconnected.
    """
    last_connected: datetime.datetime = field(default_factory=datetime.datetime.now)


class UserManager():
    """A class to represent a group of users and their states.

    Is responsible for creating new users, registering and disconnecting them.
    All users start as guest accounts until they are logged in.

    Attributes:
        logged_in_users: All the currently logged-in and connected users.
        logged_out_users: All the disconnected logged-in users.
        online_guests: All the currently connected guests.
        offline_guests: All the disconnected guests.

    Methods:
        create_guest: Create a new guest user.
        login_or_register_guest: Try to log-in a guest user, or register if name not taken.
        disconnecct_guest: Disconnect a connected guest.
        log_out_user: Disconnect a logged-in connected user.
    """

    def __init__(self):
        #self.logged_in_users: set[LoggedInUser] = set()
        #self.logged_out_users: set[LoggedOutUser] = set()
        #self.online_guests: set[OnlineGuest] = set()
        #self.offline_guests: set[OfflineGuest] = set()
        
        self.logged_in_users: list[LoggedInUser] = []
        self.logged_out_users: list[LoggedOutUser] = []
        self.online_guests: list[OnlineGuest] = []
        self.offline_guests: list[OfflineGuest] = []

    def create_guest(self, addr: tuple[str, int]) -> OnlineGuest:
        """Create a new guest user.

        Parameters:
            addr: The guest's IP/port address.
        """
        logger.debug(f"Creating guest from {addr}.")
        user = OnlineGuest(addr)
        self.online_guests.append(user)
        logger.info(f"Created guest from {addr}.")
        return user

    def login_or_register_guest(self, guest: OnlineGuest, name: str, password: str) -> LoggedInUser:
        """Log-in a guest, or try to register a new account.

        If the name isn't taken a new account will be created.

        Parameters:
            guest: The guest user to log-in.
            name: The username to log-in as.
            password: The password matching the username.
        
        Raises:
            PermissionError: If a user already exists but the password provided doesn't match.
        """
        logger.debug(f"{guest}: Attempting to login/register to {name}.")
        try:
            logged_in = self._log_in_guest(guest, name, password)
            logger.info(f"{logged_in}: Login successful")
            return logged_in
        except PermissionError:
            logger.info(f"{guest}: Login permission denied! Wrong password")
            raise
        except LookupError:
            logger.debug(f"{guest}: Login failed, trying to register to {name}.")
            logged_in = self._register_guest(guest, name, password)
            logger.info(f"{logged_in}: Registeration successful")
            return logged_in

    def disconnect_guest(self, guest: OnlineGuest) -> OfflineGuest:
        """Disconnect a guest.

        Parameters:
            guest: The guest to disconnect.
        """
        logger.debug(f"{guest}: Disconnecting...")
        user = OfflineGuest()
        self.offline_guests.append(user)
        self.online_guests.remove(guest)
        logger.info(f"{guest}: Disconnected.")
        del guest
        return user

    def log_out_user(self, user: LoggedInUser) -> LoggedOutUser:
        """Disconnect a logged-in user.

        Parameters:
            user: The user to disconnect.
        """
        logger.debug(f"{user}: Logging out...")
        offline_user = LoggedOutUser(user.name, user.password)
        self.logged_in_users.remove(user)
        self.logged_out_users.append(offline_user)
        logger.info(f"{user}: Logged out.")
        del user
        return offline_user

    def _log_in_guest(self, guest: OnlineGuest, name: str, password: str) -> LoggedInUser:
        """Log-in a guest.

        Parameters:
            guest: The user to log-in.
            name: The username,
            Password: The password matching username.

        Raises:
            LookupError: When no user is found matching the name.
            PermissionError: When the user exists but the password is incorrect.
        """
        logger.debug(f"{guest}: Logging in...")
        for user in self.logged_out_users:
            if user.name == name:
                break
        else:
            logger.debug(f"{guest}: Couldn't find user with {name}!")
            raise LookupError  # TODO: disconnect a currently connected user if its online tho.
        if user.password != password:
            logger.debug(f"{guest}: Couldn't find user with {name}!")
            raise PermissionError("Wrong password")
        logger.debug(f"{guest}: Password matches, connecting...")
        connected = LoggedInUser(guest.addr, user.name, user.password)
        self.online_guests.remove(guest)
        self.logged_out_users.remove(user)
        self.logged_in_users.append(connected)
        logger.info(f"{guest}: Logged in as {connected}")
        del guest
        del user
        return connected

    def _register_guest(self, guest: OnlineGuest, name: str, password: str) -> LoggedInUser:
        """Register a new user and connect a guest to it.

        Parameters:
            guest: The user to log-in to the new registered user.
            name: The name of the new user.
            password: The password of the new user.
        """
        logger.debug(f"{guest}: Registering as {name}")
        user = LoggedInUser(guest.addr, name, password)
        self.logged_in_users.append(user)
        self.online_guests.remove(guest)
        logger.info(f"{guest}: Registered as {user}")
        del guest
        return user


class Processor:
    """A class to process client requests from server.

    A client is represented as a queue of requests/responses pair.
    Each client is represented by a user in the `user_manager`.
    If a user's state becomes offline, the client session is stopped.

    Attributes:
        user_manager: The manager for the users.

    Methods:
        add_client: Start handling requests from a new client. 
    """

    def __init__(self):
        """Initialize the processor."""
        self.user_manager = UserManager()

    @asynccontextmanager
    async def add_client(self, addr: tuple[str, int]) -> AsyncIterator[tuple[asyncio.Queue[sprotocol.ServerMessage], asyncio.Queue[sprotocol.ServerMessage]]]:
        """A context manager to match a client handler with a client-session.

        Will send a Fin message when the context-manager is closed, stopping
        down the handler.


        Parameters:
            addr: The address of the client.

        Example:
            async with Processor().add_client(('127.0.0.1', 1337)) as requests, responses:
                await requests.put(Ping())
                print(await responses.get())
        """
        logger.debug(f"Adding new client from {addr}")
        requests: asyncio.Queue[sprotocol.ServerMessage] = asyncio.Queue()
        responses: asyncio.Queue[sprotocol.ServerMessage] = asyncio.Queue()

        await asyncio.create_task(self._handle_client(addr, requests, responses))

        logger.info(f"Started client handler for {addr}")
        try:
            yield requests, responses
        finally:
            await requests.put(sprotocol.Fin())

    async def _handle_client(self, addr: tuple[str, int], requests: asyncio.Queue[sprotocol.ServerMessage], responses: asyncio.Queue[sprotocol.ServerMessage]):
        """Handle a single client's session, processing requests until disconnected.

        Will create a new user to represent the client.
        The user's state will change after every request.

        Parameters:
            addr: The client's IP/port address.
            requests: The requests queue of the client.
            responses: The responses queue to send responses for processed requests to.
        """
        logger.debug(f"Starting handler for {addr}")
        user = self.user_manager.create_guest(addr)
        while True:
            logger.debug(f"{user}: Waiting for requests...")
            request = await requests.get()
            logger.info(f"{user}: Got request: {request}")
            user, response = await self._handle_request(user, request)
            if isinstance(user, OfflineGuest) or isinstance(user, LoggedOutUser):
                break
            assert response is not None  # https://github.com/microsoft/pyright/discussions/7627
            logger.info(f"{user}: Sending response: {response}")
            await responses.put(response)

    async def _handle_request(self, user: ConnectedUser, request: sprotocol.ServerMessage) -> tuple[ConnectedUser, sprotocol.ServerMessage] | tuple[DisconnectedUser, None]:
        """Handle a single user's request and return a new user state and the response.

        Parameters:
            user: The user who made the request.
            request: The request to process.

        Note:
            Some requests can alter the user's state - such as logging-in
            or disconnecting. The new state for the user is returned every time.
        """
        match user, request:
            case LoggedInUser(), sprotocol.Fin():
                return self.user_manager.log_out_user(user), None
            case OnlineGuest(), sprotocol.Fin():
                return self.user_manager.disconnect_guest(user), None
            case OnlineGuest(), sprotocol.Login(username=name, password=passwd):
                try:
                    return self.user_manager.login_or_register_guest(user, name, passwd), sprotocol.Ok()
                except PermissionError:
                    return user, sprotocol.WrongPassword()
            case OnlineGuest(), _:
                return user, sprotocol.Error("Unregistered users are only allowed to login!")
            case LoggedInUser(), sprotocol.Ping(msg):
                return user, sprotocol.Pong(msg)
            case LoggedInUser(), sprotocol.Declare(dir):
                user.decalre_dir(dir)
                return user, sprotocol.Ok()
            case LoggedInUser(), sprotocol.All():
                return user, self._get_all_dirs()
            case LoggedInUser(), sprotocol.Search(term):
                return user, self._search(term)
            case LoggedInUser(), sprotocol.Query(hash):
                return user, self._query_file(hash)
            case LoggedInUser(), _:
                return user, sprotocol.Error("Unrecognized command??")

    def _get_all_dirs(self) -> sprotocol.SearchResults:
        """Get all declared directories from all users."""
        return sprotocol.SearchResults({user.to_tuple(): user.declared_dirs for user in self.user_manager.logged_in_users})

    def _search(self, term: str) -> sprotocol.SearchResults:
        """Recursively search all user declared directories for a term.

        The results contain only the relevant terms in the directory hierarchy.

        Parameters:
            term: The term to search

        Note:
            If the term doesn't match in a declared directory, it will not be
            included in the SearchResults objects.
            If a user has no directories the term matches in, it will not be
            included.
        """
        results: dict[sprotocol.User, list[sprotocol.Directory]] = {}
        for user in self.user_manager.logged_in_users:
            searched_directories: list[sprotocol.Directory] = []
            for dir in user.declared_dirs:
                if searched := dir.search(term):
                    searched_directories.append(searched)
            if searched_directories:
                results[user.to_tuple()] = searched_directories
        return sprotocol.SearchResults(results)

    def _query_file(self, hash: str) -> sprotocol.QuerySearchResults:
        """Find all users with a file matching some hash.

        Parammeters:
            hash: The hash of the file.
        """
        try:
            return sprotocol.QuerySearchResults(self._get_all_files()[hash])
        except KeyError:
            return sprotocol.QuerySearchResults([])

    def _get_all_files(self) -> dict[str, list[sprotocol.User]]:
        """Create a mapping between all file hashes and the users who declared them."""
        files: dict[str, list[sprotocol.User]] = {}
        for user in self.user_manager.logged_in_users:
            for file in (file for dir in user.declared_dirs for file in dir if isinstance(file, sprotocol.File)):
                if file.hash not in files:
                    files[file.hash] = [user.to_tuple()]
                else:
                    files[file.hash].append(user.to_tuple())
        return files    
