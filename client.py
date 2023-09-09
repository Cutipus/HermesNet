'''Receives commands from user and talks to server'''
# TODO: Transition from using if-else on input types to using StdSignals processing with match case.
import logging
from signal import signal, SIGINT
from curio import run, run_in_thread, open_connection, spawn, TaskGroup, Queue, Kernel, UniversalQueue, sleep
from socket import SHUT_WR

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

RECV_SIZE = 1024

TRACKER_ADDRESS = "localhost", 25000
PING_MSG = b"ping"

# TODO: Rewrite every command as a function with an explanation for the user
# TODO: Add a help command
# TODO: Add a command to declare files 

COMMANDS = ["hello", "ping", "status", "quit"]

HELLO_INP = "hello"
PING_INP = "ping"
STATUS_INP = "status"
QUIT_INP = "quit"

class StdInput:
    __match_args__ = ("input_line", )
    def __init__(self, input_line: str):
        self.input_line = input_line


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

    async def cmd_declare_folder(self):
        raise NotImplementedError

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
                case StdInput(user_input): # no longer useful
                    logging.debug("STDIN: " + str(user_input))
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
