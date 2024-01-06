"""Receives commands from user and talks to server.#!/usr/bin/env python."""

from __future__ import annotations
import logging
from signal import signal, SIGINT
from typing import Optional
from curio import Kernel, Task, TaskGroup, UniversalEvent, run, run_in_thread, open_connection, UniversalQueue, sleep, spawn
import curio.io
from directories import Directory, File
from pathlib import Path
import shlex
from server_protocol import *

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

RECV_SIZE: int = 1024 ** 2
TRACKER_ADDRESS: tuple[str, int] = "localhost", 25000
DECLARE_DIR: str = 'DECLAREDIR {}'
DEFAULT_DOWNLOAD_DIR: Path = Path("./_downloads/")
COMMANDS: list[str] = ["hello", "ping", "status", "quit", "declare [directory]", "all", "query [file hash]", "search [name]", "search", "help"]
HELPTEXT: str = """\
ping                    Pings the server - prints if it's online or offline
hello                   Prints "meow"
status                  Prints the server's online status without pinging
quit                    Exits the client
declare [directory]     Declares a directory (recursively) to the server, sending file hashes information and file/directory names
all                     Prints all declared directories in the server from all clients
query [file hash]       Requests a list of all clients that declared a file which hash matches the given hash
search [name]           Asks the server to search for something and allows you to choose what to download
history                 Shows previous search results
history [index]         Chooses a history listing to download
help                    Print this"""


class LoginDetails(NamedTuple):
    username: str
    password: str


class ServerProtocol:
    """The protocol to communicate with the server.

    All methods should only be executed from the context manager:

    with ServerProtocol(("address", 1234), LoginDetails("foo", "bar")) as sp:
        sp.login()
        sp.ping()
    """

    def __init__(self, server_address: tuple[str, int], login: LoginDetails, retry_timer: int = 1) -> None:
        """Initialize the server communication with the server address.

        server_address: The server's IP address and port
        sock: the socket to the server - None if it's not initialized yet
        login_details: The username and password to identify with
        """
        self.server_address = server_address
        self.sock: Optional[curio.io.Socket] = None
        self.login_details: LoginDetails = login

        # why is this here?
        if not DEFAULT_DOWNLOAD_DIR.exists():
            DEFAULT_DOWNLOAD_DIR.mkdir()

    async def __aenter__(self) -> None:
        """Connect to server and send login."""
        self.sock = await open_connection(*self.server_address)

    async def __aexit__(self, *_) -> None:
        """Closes the server """
        if self.sock is not None:
            await self.sock.close()
            self.sock = None

    async def send_message_get_response(self, message: ServerMessage) -> ServerMessage:
        """Send a message to the server, and return a response."""
        assert self.sock is not None # this command should only be run *after* run()

        if self.sock is None:
            raise ValueError("I/O operation on a closed server.")

        try:
            await send_message(self.sock, message)
            return await read_message(self.sock)
        except ValueError as e:
            return Error(error_text=str(e))

    async def ping(self) -> bool:
        """Pings the server, returning True if server is online else False."""
        response = await self.send_message_get_response(Ping())

        match response:
            case Pong() | Ok():
                return True
            case _:
                return False

    async def login(self):
        """Send login details - typically immediately after connecting."""
        match await self.send_message_get_response(Login(**self.login_details._asdict())):
            case Ok():
                print(f"Logged in as {self.login_details.username}!")
            case WrongPassword():
                raise PermissionError("Wrong password!")
            case Error(error_text=error):
                raise ValueError(error)
            case other:
                raise ValueError(f"Unknown response: {other}")

    async def retrieve_dirs(self) -> SearchResults:
        """Request a list of all the declared directories from the server.

        Returns a list of (User, Directory) pairs of all the declared files.
        Can raise ValueError.
        """
        match await self.send_message_get_response(All()):
            case SearchResults() as results:
                return results
            case Error(error_text=text):
                raise ValueError(text)
            case other:
                raise ValueError(f"Unsupported response: {other}")

    async def declare_directory(self, directory: Directory | Path | str) -> Ok:
        """Send a directory structure to the server, declaring files available.

        Can raise FileNotFoundError if can't find the directory
        Can raise ValueError if poor response
        """
        if not isinstance(directory, Directory):
            directory = Directory.from_path(directory)

        match await self.send_message_get_response(Declare(directory=directory)):
            case Ok() as ok:
                return ok
            case other:
                raise ValueError(f"Unrecognized response {other}")

    async def query_file(self, filehash: str) -> QuerySearchResults:
        """Query a file by hash from the server, returns a list of clients.

        Can raise ValueError.
        """
        match await self.send_message_get_response(Query(file_hash=filehash)):
            case QuerySearchResults() as response:
                return response
            case other:
                raise ValueError(f"Unrecognized response {other}")

    async def search(self, search_term: str) -> SearchResults:
        """Request the server for all search results.

        Returns a list of partial user-declared directories containing search results.
        Can raise ValueError
        """
        match await self.send_message_get_response(Search(search_term=search_term)):
            case SearchResults() as results:
                return results
            case other:
                raise ValueError(f"Unrecognized response {other}")


class Client:
    """The client receiving commands from CLI, interacting with the server."""
    # TODO: rename to CliClient, move history functionality to new Client class.

    def __init__(self, address: tuple[str, int], login: LoginDetails):
        """Initialize client with server's address."""
        self.address: tuple[str, int] = address
        self.server_comm: ServerProtocol = ServerProtocol(self.address, login)
        self.connected: bool | None = None  # None if not pinged yet
        self.signals: UniversalQueue = UniversalQueue()
        self.history: list[tuple[str, SearchResults]] = []

    async def run(self):
        """Start the client daemons and REPL."""
        print(f"Available commands: {', '.join(COMMANDS)}")

        signal(SIGINT, lambda signo, frame: self.quit())

        while True:
            # automatically reconnect to server on disconnect
            try:
                async with self.server_comm:
                    await self.server_comm.login()
                    await self.stdinput_loop()
            except ConnectionError:
                print("Connection error... Retrying.")
                await sleep(1)

    async def auto_pinger(self):
        """Indefinitely ping the server, updating connection status."""
        while True:
            await self.cmd_ping()
            await sleep(20)

    async def events_loop(self):
        """Read client-related events."""
        while True:
            signal = await self.signals.get()
            print('!EVENT! ', end='')
            match signal:
                case "quit":
                    print("Client shutting down")
                    return
                case "online":
                    print("Server online")
                case "offline":
                    print("Server offline")
                case _:
                    print("Nothing?")

    async def stdinput_loop(self):
        """User input REPL."""
        while True:
            try:
                user_input: str = await run_in_thread(input, ">> ")
            except EOFError:
                return

            try:
                await self.process_stdinput(user_input)
            except ValueError as e:
                print(e)
                continue

    async def process_stdinput(self, command: str):
        """Process a single command from the user.

        Each command is a single line from stdin.
        """
        try:
            user_input = shlex.split(command)
        except ValueError:
            print("???")
            return

        match user_input:
            case ["hello"]:
                print('meow')
            case ["help"]:
                print(HELPTEXT)
            case ["status"]:
                print(f'Server {"connected" if self.connected else "disconnected"}.')
            case ["ping"]:
                print(await self.cmd_ping())
            case ["quit"]:
                print(self.quit())
            case ["declare", filename]:
                try:
                    print(await self.server_comm.declare_directory((Directory.from_path(filename))))
                except FileNotFoundError:
                    print("Couldn't find it. Try again!")
            case ["all"]:
                print(str(await self.server_comm.retrieve_dirs()))
            case ["query", hash]:
                print(await self.server_comm.query_file(hash))
            case ["search", search_term]:
                search_res = await self.cmd_search(search_term)
                try:
                    selection = self.cmd_select_search_result(search_res)
                except ValueError as e:
                    print(e)
                    return
                self.download(selection)
            case ["history"]:
                for index, (query, result) in enumerate(self.history):
                    print(f"--{index}-- {query}\n---------------------------\n{result}\n\n")
            case ["history", num]:
                history_selection = self.cmd_select(self.history, num)
                selection = self.cmd_select_search_result(history_selection[1])
                self.download(selection)
            case []:
                return
            case _:
                print("Unknown command: ", command)

    def download(self, item: Directory | File, dldir: Path = DEFAULT_DOWNLOAD_DIR):
        """Download a directory or file.

        Replicates the directory hierarchy in the file system.
        """
        # TODO: per-user download folder
        if isinstance(item, File):
            pass  # The actual download logic
        elif isinstance(item, Directory):
            dldir /= item.name
            if not dldir.exists():
                dldir.mkdir()
            for x in item.contents:
                self.download(x, dldir)
            pass  # create dir, download children inside modified dldir

    def cmd_select[T](self, lst: list[T], selection: Optional[str]=None) -> T:
        """Process the user input to select something from a list.

        Can raise ValueError if bad user input."""
        try:
            return lst[int(input("Select element: ")) if selection is None else int(selection)]
        except ValueError:
            raise ValueError("NaN try again!")
        except IndexError:
            raise ValueError("Bad index try again!")

    def cmd_select_search_result(self, search_result: SearchResults) -> Directory | File:
        """Select items to download from search result.

        Can raise ValueError if bad user selection
        """
        index = 0
        items: list[Directory] = []
        for user, dirs in search_result.results.items():
            for dir in dirs:
                items.append(dir)
                print(index, user, dir)
                index += 1

        selected_dir = self.cmd_select(items)
        return self.cmd_select(list(selected_dir))

    async def cmd_search(self, query: str) -> SearchResults:
        """Search a term, store the result in history."""
        result = await self.server_comm.search(query)
        self.history.append((query, result))
        return result

    async def cmd_ping(self) -> bool:
        """Ping the server, return True if online, otherwise False."""
        if await self.server_comm.ping():
            logging.debug("Ping successful - server online")
            if self.connected:
                await self.signals.put("online")
            self.connected = True
            return True
        else:
            logging.debug("Ping unsuccessful - server offline")
            if not self.connected:
                await self.signals.put("offline")
            self.connected = False
            return False

    def quit(self) -> str:
        """Close the client."""
        raise KeyboardInterrupt


async def main():
    """Start the client."""
    client = Client(TRACKER_ADDRESS, LoginDetails('abc', 'def'))
    await client.run()


if __name__ == '__main__':
    kernel = Kernel()
    try:
        kernel.run(main)
    except KeyboardInterrupt:
        print("Quitting.")
    finally:
        kernel.run(shutdown=True)
