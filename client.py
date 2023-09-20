'''Receives commands from user and talks to server'''
from __future__ import annotations
import logging
from signal import signal, SIGINT
from curio import run, run_in_thread, open_connection, spawn, TaskGroup, Queue, Kernel, UniversalQueue, sleep
from socket import SHUT_WR
from hashlib import sha1
import json
from directories import File, Directory, decode

# TODO: use a more generic protocol
# TODO: Add a help command
logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

RECV_SIZE = 1024 ** 2
TRACKER_ADDRESS = "localhost", 25000
DECLARE_DIR = 'DECLAREDIR {}'
COMMANDS = ["hello", "ping", "status", "quit", "declare [directory]", "all", "query [file hash]", "help"]
HELPTEXT = """\
ping                    Pings the server - prints if it's online or offline
hello                   Prints "meow"
status                  Prints the server's online status without pinging
quit                    Exits the client
declare [directory]     Declares a directory (recursively) to the server, sending file hashes information and file/directory names
all                     Prints all declared directories in the server from all clients
query [file hash]       Requests a list of all clients that declared a file which hash matches the given hash
"""

class ServerProtocol:
    def __init__(self, address: tuple[str, int]):
        self.address = address

    async def send_message(self, message: bytes) -> bytes:
        '''Sends a message to the server and retrieves a response, may raise ConnectionRefusedError'''
        logging.debug("Sending message")
        conn = await open_connection(*self.address)
        await conn.sendall(message)
        await conn.shutdown(SHUT_WR) # end message signal
        return await conn.recv(RECV_SIZE) # TODO: retrieve until shutdown instead

    async def ping(self) -> bool:
        """Pings the server, returning True if server is online, otherwise returns False"""
        try:
            await self.send_message(b'ping')
            return True
        except ConnectionRefusedError:
            return False

    async def declare_directory(self, directory: Directory):
        """Sends a directory structure to the server, declaring files available to download."""
        return await self.send_message(DECLARE_DIR.format(directory.to_json()).encode())

    async def retrieve_dirs(self) -> Directory:
        '''Requests a list of all the declared directories from the server. Returns an "ALL" directory with all the directories as subdirs.'''
        response = decode(await self.send_message(b'all'))
        assert isinstance(response, Directory)
        return response

    async def query_file(self, filehash: str) -> list[str]:
        '''Asks the server for a list of clients with the file, returns empty list of no users have it.'''
        response = (await self.send_message(f"download {hash}".encode())).decode()
        if response == 'NOUSERS':
            return []
        else:
            return json.loads(response)


class Client:
    def __init__(self, address: tuple[str, int]):
        self.address = address
        self.server_comm = ServerProtocol(self.address)
        self.connected = None # None if not pinged yet
        self.signals = UniversalQueue()
        self.commands: dict = {}

    async def run(self):
        print(f"Available commands: {', '.join(COMMANDS)}")
        signal(SIGINT, lambda signo, frame: self.quit())
        async with TaskGroup(wait=any) as g:
            await g.spawn(self.stdinput_loop)
            await g.spawn(self.events_loop)
            await g.spawn(self.auto_pinger)
            print("Connecting... Please wait")

    async def auto_pinger(self):
        """Indefinitely pings the server, updating `self.connected` accordingly."""
        while True:
            await self.cmd_ping()
            await sleep(20)

    async def events_loop(self):
        """Reads client-related events"""
        while True:
            signal = await self.signals.get()
            print('!EVENT! ', end='')
            match signal:
                case "quit":
                    logging.debug("Quit msg received; Closing . . .")
                    print("Client shutting down")
                    return
                case "online":
                    logging.debug("Server online")
                    print("Server online")
                case "offline":
                    logging.debug("Server offline")
                    print("Server offline")
                case _:
                    print("Nothing?")

    async def stdinput_loop(self):
        """Indefinitely reads user input from a different thread and processes it"""
        async with TaskGroup() as g:
            while True:
                try:
                    user_input = await run_in_thread(input)
                    await g.spawn(self.process_stdinput, user_input)
                except EOFError:
                    logging.debug("End of input")

    async def process_stdinput(self, user_input: str):
        """Processes a single line of user input, responding to user commands"""
        if user_input == 'hello':
            print('meow')
        elif user_input == 'help':
            print(HELPTEXT)
        elif user_input == 'status':
            print(await self.cmd_status())
        elif user_input == 'ping':
            print(await self.cmd_ping())
        elif user_input == 'quit':
            print(self.quit())
        elif user_input.startswith("declare"):
            print(await self.cmd_declare_folder(Directory.from_path(user_input.split(maxsplit=1)[1])))
        elif user_input == "all":
            print(await self.retrieve_all_dirs())
        elif user_input.startswith("query"):
            print(await self.cmd_download(user_input.split(maxsplit=1)[1]))

    async def cmd_ping(self) -> str:
        if await self.server_comm.ping():
            logging.debug("Ping successful - server online")
            if self.connected != True:
                await self.signals.put("online")
            self.connected = True
            return 'Online'
        else:
            logging.debug("Ping unsuccessful - server offline")
            if self.connected != False:
                await self.signals.put("offline")
            self.connected = False
            return 'Offline'

    async def cmd_status(self) -> str:
        return f'Server {"connected" if self.connected else "disconnected"}.'

    async def cmd_declare_folder(self, directory: Directory) -> str:
        return await self.server_comm.declare_directory(directory) 

    async def retrieve_all_dirs(self) -> str:
        return str(await self.server_comm.retrieve_dirs())

    async def cmd_query_file(self, hash: str) -> str:
        return(await self.server_comm.query_file(hash))

    def quit(self) -> str:
        logging.debug("Sending quit signal")
        self.signals.put("quit")
        return 'Quitting...'


async def main():
    client = Client(TRACKER_ADDRESS)
    await client.run()


if __name__ == '__main__':
    run(main)
