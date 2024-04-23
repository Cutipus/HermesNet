"""A simple CLI client for HermesNet.

Constants:
    TRACKER_ADDRESS: The server's address
    DEFAULT_DOWNLOAD_DIR: The directory to download files into.

Classes:
    CliClient: A simple command-line client interface for communicating with server.
"""
# stdlib
import logging
import shlex
import pathlib
import signal
from typing import Optional

# curio
import asyncio

# project
from hermesnet.client import network
from hermesnet import protocol as sprotocol

_logger = logging.getLogger(__name__)


TRACKER_ADDRESS: tuple[str, int] = "localhost", 25000
DEFAULT_DOWNLOAD_DIR = pathlib.Path("./_downloads/")
DEFAULT_PROMPT = '>> '
COMMAND_HELPTEXT = {
    "ping": "Pings the server - prints if it's online or offline",
    "hello": "Prints \"meow\"",
    "status": "Prints the server's online status without pinging",
    "quit": "Exits the client",
    "declare [directory]": "Declares a directory (recursively) to the server, sending file hashes information and file/directory names",
    "all": "Prints all declared directories in the server from all clients",
    "query [file hash]": "Requests a list of all clients that declared a file which hash matches the given hash",
    "search [name]": "Asks the server to search for something and allows you to choose what to download",
    "history": "Shows previous search results",
    "history [index]": "Chooses a history listing to download",
    "help": "Print this",
}


type SelectionOption[T] = tuple[str, T]


class CliClient:
    """The client receiving commands from CLI, interacting with the server.
    
    Attributes:
        prompt: Prompt to show before user input.
        address: The server's connection address.
        download_dir: The downloads directory.
        history: Cache of previous searches.

    Methods:
        run: Start the client, processing user input indefinitely.        
    """

    def __init__(self, address: tuple[str, int], prompt: str=DEFAULT_PROMPT, download_dir: pathlib.Path=DEFAULT_DOWNLOAD_DIR):
        """Initialize client with server's address.

        Parameters:
            address: Server's address (hostname, port).
            prompt: The prompt to show before user input.
            download_dir: Downloads directory location..
        """
        self.prompt: str = prompt
        self.address: tuple[str, int] = address
        self.download_dir = download_dir
        self.history: list[SelectionOption[sprotocol.SearchResults]] = []
        signal.signal(signal.SIGINT, lambda signo, frame: self._quit())

    async def run(self, show_helptext: bool=True):
        """Start the client daemons and REPL."""
        if show_helptext:
            print(f"Available commands: {', '.join(COMMAND_HELPTEXT.keys())}")

        while True:
            # automatically reconnect to server on disconnect
            try:
                async with network.ClientSession(*self.address) as client_session:
                    await self._stdinput_loop(client_session)
            except ConnectionError:
                print("Connection error... Retrying.")
                await asyncio.sleep(1)

    async def _stdinput_loop(self, client_session: network.ClientSession):
        """User input REPL."""
        while True:
            try:
                user_input: str =  await asyncio.get_running_loop().run_in_executor(
                        None, lambda : input(self.prompt))
            except EOFError:
                self._quit()
                return

            try:
                print(await self._process_stdinput(client_session, user_input))
            except network.ServerError as e:
                print(e)

    async def _process_stdinput(self, client_session: network.ClientSession, command: str) -> str:
        """Process a single command from the user.

        Parameters:
            command: A single line from stdin.

        Returns:
            The output of the command.
        """
        _logger.info(f"Processing new command: {command}")
        try:
            user_input = shlex.split(command)
        except ValueError:
            return "??"

        match user_input:
            case ["hello"]:
                return 'meow'
            case ["help"]:
                return "\n".join(f"{cmd}\t\t{explanation}" for cmd, explanation in COMMAND_HELPTEXT.items())
            case ["status"]:  # same as ping?!
                return f'Server {"connected" if (await client_session.ping()) else "disconnected"}.'
            case ["login", username, password]:
                await client_session.login(username, password)
                return "Logged in as " + username
            case ["ping"]:
                return 'Connected' if (await client_session.ping()) else 'Disconnected'
            case ["quit"]:
                return self._quit()
            case ["declare", filename]:
                try:
                    directory = sprotocol.Directory.from_path(filename)
                except FileNotFoundError:
                    return f"Couldn't find {filename}"
                await client_session.declare_directory(directory)
                return "Ok!"
            case ["all"]:
                return str(await client_session.retrieve_dirs())
            case ["query", hash]:
                return str(await client_session.query_file(hash))
            case ["search", search_term]:
                result = await client_session.search(search_term)
                self.history.append((search_term, result))
                try:
                    selection = self._cmd_select_search_result(result)
                except ValueError:
                    return "Bad selection!"
                await self._download(selection)
                return f"Started downloading {selection}!"
            case ["history"]:
                output = ''
                for index, (query, result) in enumerate(self.history):
                    output += f"--{index}-- {query}\n---------------------------\n{result}\n\n"
                return output
            case ["history", num]:
                history_selection = self._cmd_select(self.history, num)
                selection = self._cmd_select_search_result(history_selection[1])
                await self._download(selection)
                return "Downloaded"
            case []:
                return ""
            case _:
                return "Unrecognized command."

    async def _download(self, item: sprotocol.Directory | sprotocol.File, dldir: pathlib.Path = DEFAULT_DOWNLOAD_DIR):
        """Download a directory or file.

        Replicates the directory hierarchy in the file system.
        """
        # TODO: per-user download folder
        if isinstance(item, sprotocol.File):
            print("fake: downloading", item)
        else:
            print("downloading ", item.name)
            dldir /= item.name
            if not dldir.exists():
                dldir.mkdir()
            for x in item.contents:
                await self._download(x, dldir)
            pass  # create dir, download children inside modified dldir

    def _cmd_select[T](self, lst: list[SelectionOption[T]], selection: Optional[str]=None) -> SelectionOption[T]:
        """Process the user input to select something from a list.

        If selection is specified then no user input is taken.
        Can raise ValueError if bad user input."""
        if len(lst) == 0:
            raise ValueError("Empty selection list")

        if selection is not None:
            print(
                *(f'{index} - {name}\n{option}' for index, (name, option) in enumerate(lst)),
                sep='\n',
                )

        try:
            index = int(input("Select element: ") if selection is None else selection)
            return lst[index]
        except ValueError:
            raise ValueError("NaN try again!")
        except IndexError:
            raise ValueError("Bad index try again!")

    def _cmd_select_search_result(self, search_result: sprotocol.SearchResults) -> sprotocol.Directory | sprotocol.File:
        """Select a file or directory to download from a search.

        Can raise ValueError if bad user selection or empty list
        """
        results = search_result.results
        if len(results) == 0:
            raise ValueError("No results to choose from")
        items: list[SelectionOption[sprotocol.Directory]] = [(str(user), d) for user, ds in search_result.results.items() for d in ds]
        user, dir = self._cmd_select(items)
        selected_subdir = self._cmd_select([(user, x) for x in dir])
        return selected_subdir[1]

    def _quit(self) -> str:
        """Close the client."""
        raise KeyboardInterrupt


async def main():
    """Start the client."""
    client = CliClient(TRACKER_ADDRESS)
    await client.run()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Quitting.")
