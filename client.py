'''Receives commands from user and talks to server'''
from __future__ import annotations
# TODO: Transition from using if-else on input types to using StdSignals processing with match case.
import logging
from signal import signal, SIGINT
from curio import run, run_in_thread, open_connection, spawn, TaskGroup, Queue, Kernel, UniversalQueue, sleep
from socket import SHUT_WR
from pathlib import Path
import json
from hashlib import sha1

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

RECV_SIZE = 1024
TRACKER_ADDRESS = "localhost", 25000

# TODO: use a more generic protocol
PING_MSG = b"ping"
DECLARE_DIR = 'DECLAREDIR {}'

# TODO: Rewrite every command as a function with an explanation for the user
# TODO: Add a help command
# TODO: Add a command to declare files 

BUFSIZE = 1024**2 # one megabyte

COMMANDS = ["hello", "ping", "status", "quit", "declare"]

HELLO_INP = "hello"
PING_INP = "ping"
STATUS_INP = "status"
QUIT_INP = "quit"


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


class ServerProtocol:
    def __init__(self, address: tuple[str, int]):
        self.address = address

    async def ping(self) -> bytes | bool:
        """Pings the server, returning it's response. If the server is offline returns False"""
        logging.debug("pinging . . .")
        logging.debug("Opening connection")
        try:
            conn = await open_connection(*self.address)
        except ConnectionRefusedError:
            logging.debug("Connection from server refused")
            return False
        logging.debug("Sending message")
        await conn.sendall(PING_MSG)
        await conn.shutdown(SHUT_WR) # end message signal
        logging.debug("Message sent")
        logging.debug("Retrieving response . . .")
        response = await conn.recv(RECV_SIZE)
        logging.debug("Responsed retrieved")
        return response

    async def declare_directory(self, directory: Directory):
        """Sends a directory structure to the server, declaring files available to download."""
        logging.debug('Declaring directory: ' + directory.name)
        logging.debug("Opening connection")
        try:
            conn = await open_connection(*self.address)
        except ConnectionRefusedError:
            logging.debug("Connection from server refused")
            return False
        logging.debug("Sending message")
        await conn.sendall(DECLARE_DIR.format(directory.to_json()).encode())
        await conn.shutdown(SHUT_WR) # end message signal
        logging.debug("Message sent")
        logging.debug("Retrieving response . . .")
        response = await conn.recv(RECV_SIZE)
        logging.debug("Responsed retrieved")
        return response


    def decode(self, encoded: bytes) -> File | Directory:
        # TODO: the `loads` method can be very time consuming - use curio to put it in background
        # TODO: validate the json
        decode = json.loads(encoded.decode())
        def parse(obj: dict) -> File | Directory:
            if obj['type'] == 'file':
                return File(obj['name'], obj['hash'])
            elif obj['type']== 'directory':
                return Directory(obj['name'], [parse(c) for c in obj['contents']])
        return parse(decode)


class Client:
    def __init__(self, address: tuple[str, int]):
        self.address = address
        self.server_comm = ServerProtocol(self.address)
        self.connected = None # None if not pinged yet
        self.signals = UniversalQueue()

    async def run(self):
        print(f"Available commands: {', '.join(COMMANDS)}")
        signal(SIGINT, lambda signo, frame: self.quit())
        async with TaskGroup(wait=any) as g:
            await g.spawn(self.stdinput_loop)
            await g.spawn(self.events_loop)
            await g.spawn(self.auto_pinger)
            print("Connecting... Please wait")

    async def cmd_hello(self):
        return 'meow'

    async def cmd_ping(self):
        if response := await self.ping():
            return f'Ping OK: "{response}"'
        else:
            return "Ping failed"

    async def cmd_status(self):
        return f'Server {"connected" if self.connected else "disconnected"}.'

    async def cmd_declare_folder(self, directory: Path):
        directory = Directory.from_path(directory)
        response = await self.server_comm.declare_directory(directory) 
        print(response)

    async def cmd_quit(self):
        self.quit()

    async def process_stdinput(self, user_input: str):
        """Processes a single line of user input, responding to user commands"""
        if user_input == HELLO_INP:
            print(await self.cmd_hello())
        elif user_input == STATUS_INP:
            print(await self.cmd_status())
        elif user_input == PING_INP:
            print(await self.cmd_ping())
        elif user_input == QUIT_INP:
            await self.cmd_quit()
        elif user_input.startswith("declare"):
            await self.cmd_declare_folder(user_input.split(maxsplit=1)[1])

    def quit(self):
        logging.debug("Sending quit signal")
        self.signals.put("quit")

    async def ping(self) -> str | bool:
        if response := await self.server_comm.ping():
            logging.debug("Ping successful - server online")
            if self.connected != True:
                await self.signals.put("online")
            self.connected = True
            return response.decode()
        else:
            logging.debug("Ping unsuccessful - server offline")
            if self.connected != False:
                await self.signals.put("offline")
            self.connected = False
            return False

    async def auto_pinger(self):
        """Indefinitely pings the server, updating `self.connected` accordingly."""
        while True:
            await self.ping()
            await sleep(20)

    async def stdinput_loop(self):
        """Indefinitely reads user input from a different thread and processes it"""
        async with TaskGroup() as g:
            while True:
                try:
                    user_input = await run_in_thread(input)
                    await g.spawn(self.process_stdinput, user_input)
                except EOFError:
                    logging.debug("End of input")

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
                #case StdInput(user_input): # no longer useful
                #    logging.debug("STDIN: " + str(user_input))
                case "online":
                    logging.debug("Server online")
                    print("Server online")
                case "offline":
                    logging.debug("Server offline")
                    print("Server offline")
                case _:
                    print("Nothing?")


async def main():
    client = Client(TRACKER_ADDRESS)
    await client.run()


if __name__ == '__main__':
    run(main)
