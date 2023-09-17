'''Receives commands from user and talks to server'''
from __future__ import annotations
import logging
from signal import signal, SIGINT
from curio import run, run_in_thread, open_connection, spawn, TaskGroup, Queue, Kernel, UniversalQueue, sleep
from socket import SHUT_WR
from hashlib import sha1

from directories import File, Directory, decode

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

RECV_SIZE = 1024 ** 2
TRACKER_ADDRESS = "localhost", 25000

# TODO: use a more generic protocol
PING_MSG = b"ping"
DECLARE_DIR = 'DECLAREDIR {}'

# TODO: Rewrite every command as a function with an explanation for the user
# TODO: Add a help command

COMMANDS = ["hello", "ping", "status", "quit", "declare", "search"]
HELLO_INP = "hello"
PING_INP = "ping"
STATUS_INP = "status"
QUIT_INP = "quit"


class ServerProtocol:
    def __init__(self, address: tuple[str, int]):
        self.address = address

    async def search(self, term: str) ->  list[Directory]:
        pass
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
        response = str(await conn.recv(RECV_SIZE))
        print(response)
        logging.debug("Responsed retrieved")
        # TODO: handle decoder errors
        return list(map(decode, response.split('###SEP###')))

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

    async def retrieve_dirs(self) -> Directory:
        try:
            conn = await open_connection(*self.address)
        except ConnectionRefusedError:
            logging.debug("Connection from server refused")
            return False
        await conn.sendall(b"all")
        await conn.shutdown(SHUT_WR) # end message signal

        response = decode(await conn.recv(RECV_SIZE))
        assert isinstance(response, Directory)
        return response


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

    async def cmd_declare_folder(self, directory: Directory):
        response = await self.server_comm.declare_directory(directory) 
        print(response)

    async def cmd_quit(self):
        self.quit()

    async def cmd_search(self, term: str):
        pass
        response = await self.server_comm.search(term)
        print(response)

    async def retrieve_all_dirs(self):
        alldirs = await self.server_comm.retrieve_dirs()
        return(str(alldirs))
        return '\n-----------\n'.join(map(repr, alldirs.contents))

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
            dir = Directory.from_path(user_input.split(maxsplit=1)[1])
            await self.cmd_declare_folder(dir)
        elif user_input == "ALL":
            print(await self.retrieve_all_dirs())
        elif user_input.startswith("search"):
            await self.cmd_search(user_input.split(maxsplit=1)[1])

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
