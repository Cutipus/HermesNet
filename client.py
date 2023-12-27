"""Receives commands from user and talks to server.#!/usr/bin/env python."""
from __future__ import annotations
import logging
from signal import signal, SIGINT
from typing import Sequence
from curio import run, run_in_thread, open_connection, TaskGroup, UniversalQueue, sleep
import curio.io
from socket import SHUT_WR
from directories import Directory, File, decode
import json
from pathlib import Path
import shlex

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
help                    Print this
"""


class ServerProtocol:
    """The protocol to communicate with the server.

    TODO: username
    TODO: answer pings from server
    """

    def __init__(self, address: tuple[str, int]):
        """Initialize the server communication with the server address."""
        self.address = address
        if not DEFAULT_DOWNLOAD_DIR.exists():
            DEFAULT_DOWNLOAD_DIR.mkdir()

    async def run(self):
        """Run the daemon to communicate with the server."""
        ...

    async def send_message(self, message: bytes) -> str:
        """Send a message to the server and retrieves a response.

        May raise ConnectionRefusedError.
        """
        logging.debug("Sending message")
        conn = await open_connection(*self.address)
        await conn.sendall(message)
        await conn.shutdown(SHUT_WR)  # end message signal
        msg = bytearray()
        while data := await conn.recv(RECV_SIZE):
            msg += data
        return msg.decode()

    async def ping(self) -> bool:
        """Pings the server, returning True if server is online else False."""
        try:
            await self.send_message(b'ping')
            return True
        except ConnectionRefusedError:
            return False

    async def retrieve_dirs(self) -> Directory:
        """Request a list of all the declared directories from the server.

        Returns an "ALL" directory with all the directories as subdirs.
        Can raise ConnectionRefusedError if server is offline
        """
        response = decode(await self.send_message(b'ALL'))
        assert isinstance(response, Directory)
        return response

    async def declare_directory(self, directory: Directory | Path | str) -> str:
        """Send a directory structure to the server, declaring files available.

        Can raise ConnectionRefusedError if server is offline
        Can raise FileNotFoundError if can't find the directory
        """
        if not isinstance(directory, Directory):
            directory = Directory.from_path(directory)
        return await self.send_message(DECLARE_DIR.format(directory.to_json()).encode())

    async def query_file(self, filehash: str) -> list[tuple[str, int]]:
        """Query a file by hash from the server, returns a list of clients."""
        response = (await self.send_message(f"QUERY {filehash}".encode()))
        if response == 'NOUSERS':
            return []
        # BUG: May raise JSON parsing error
        return json.loads(response)

    async def search(self, search_term: str) -> list[Directory]:
        """Request the server for all search results.

        Returns a list of partial user-declared directories containing search results.
        Can raise ConnectionRefusedError if server is offline
        """
        dirs: list[Directory] = []
        response = decode(await self.send_message(f"SEARCH {search_term}".encode()))
        if isinstance(response, File):
            raise Exception("Expected directory.")
        for x in response.contents:
            if isinstance(x, File):
                raise Exception("Expected directory.")
            elif isinstance(x, Directory):
                dirs.append(x)
        return dirs

class Client:
    """The client receiving commands from CLI, interacting with the server."""
    # TODO: rename to CliClient, move history functionality to new Client class.

    def __init__(self, address: tuple[str, int]):
        """Initialize client with server's address."""
        self.address: tuple[str, int] = address
        self.server_comm: ServerProtocol = ServerProtocol(self.address)
        self.connected: bool | None = None  # None if not pinged yet
        self.signals: UniversalQueue = UniversalQueue()
        self.history: list[tuple[str, list[Directory]]] = []

    async def run(self):
        """Start the client daemons and REPL."""
        print(f"Available commands: {', '.join(COMMANDS)}")

        signal(SIGINT, lambda signo, frame: self.quit())

        async with TaskGroup(wait=any) as g:
            await g.spawn(self.stdinput_loop)
            await g.spawn(self.events_loop)
            await g.spawn(self.auto_pinger)
            print("Connecting... Please wait")

    async def auto_pinger(self):
        """Indefinitely ping the server, updating connection status."""
        while True:
            await self.cmd_ping()
            await sleep(20)

    async def events_loop(self, display=False):
        """Read client-related events. Only prints events on display."""
        while True:
            signal = await self.signals.get()
            if display:
                print('!EVENT! ', end='')
            match signal:
                case "quit":
                    logging.debug("Quit msg received; Closing . . .")
                    if display:
                        print("Client shutting down")
                    return
                case "online":
                    logging.debug("Server online")
                    if display:
                        print("Server online")
                case "offline":
                    logging.debug("Server offline")
                    if display:
                        print("Server offline")
                case _:
                    if display:
                        print("Nothing?")

    async def stdinput_loop(self):
        """User input REPL."""
        while True:
            try:
                # BUG: will throw nonsense error when using SIGINT to stop program
                user_input = await run_in_thread(input, ">> ")
                await self.process_stdinput(user_input)
            except EOFError:
                logging.debug("End of input")

    async def process_stdinput(self, command: str):
        """Process a single command from the user.

        Each command is a single line from stdin.
        """
        match shlex.split(command):
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
                selection = self.cmd_select_from_search(search_res)
                if not selection:
                    print("No selection, not downloading")
                    return
                self.download(selection)
            case ["history"]:
                for index, (query, result) in enumerate(self.history):
                    print(f"--{index}-- {query}\n---------------------------\n{result}\n\n")
            case ["history", num]:
                history_selection = self.cmd_select(num, self.history)
                if not history_selection:
                    return
                selection = self.cmd_select_from_search(history_selection[1])
                if not selection:
                    return
                self.download(selection)
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

    def cmd_select[T](self, input: str, lst: list[T]) -> T | None:
        """Process the user input to select something from a list."""
        # NOTE: Returns None if input error
        if input == "":
            print("Closing selection")
            return

        try:
            index = int(input)
        except ValueError:
            print("NaN try again!")
            return

        try:
            return lst[index]
        except IndexError:
            print("Bad index try again!")
            return

    def cmd_select_from_search(self, search_result: list[Directory]) -> Directory | File | None:
        """Select items to download from search result."""
        # NOTE: This function is interactive, it will print to stdout.
        search_items: Sequence[Directory | File] = [x
                        for xs in map(list, search_result)
                        for x in xs]
        for index, item in enumerate(search_items):
            print(index, item)

        return self.cmd_select(input("Select index to download: "), search_items)

    async def cmd_search(self, query: str) -> list[Directory]:
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
        logging.debug("Sending quit signal")
        self.signals.put("quit")  # UniversalQueue can run from non-async code # pyright: ignore
        return 'Quitting...'


async def main():
    """Start the client."""
    client = Client(TRACKER_ADDRESS)
    await client.run()


if __name__ == '__main__':
    run(main)
