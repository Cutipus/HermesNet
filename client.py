'''Receives commands from user and talks to server'''
# TODO: Transition from using if-else on input types to using StdSignals processing with match case.
import logging
from signal import signal, SIGINT
from curio import run, run_in_thread, open_connection, spawn, TaskGroup, Queue, Kernel, UniversalQueue, sleep
from socket import SHUT_WR

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.DEBUG)

RECV_SIZE = 1024

TRACKER_ADDRESS = "localhost", 25000
PING_MSG = b"ping"

HELLO_INP = "hello"
PING_INP = "ping"
STATUS_INP = "status"
QUIT_INP = "quit"
HELLO_RSP = "meow"

QUIT = 0


class QuitSignal:
    pass


class StdInput:
    __match_args__ = ("input_line", )
    def __init__(self, input_line: str):
        self.input_line = input_line


class ServerProtocol:
    def __init__(self, address: tuple[str, int]):
        self.address = address

    async def ping(self) -> bytes | bool:
        """Pings the server, returning it's response. If the server is offline returns False"""
        logging.info("pinging . . .")
        logging.debug("Opening connection")
        try:
            conn = await open_connection(*self.address)
        except ConnectionRefusedError:
            logging.debug("Connection from server refused")
            return False
        logging.debug("Sending message")
        await conn.sendall(PING_MSG)
        await conn.shutdown(SHUT_WR)
        logging.debug("Message sent")
        logging.debug("Retrieving response . . .")
        response = await conn.recv(RECV_SIZE)
        logging.debug("Responsed retrieved")
        return response


class Client:
    def __init__(self, address: tuple[str, int]):
        self.address = address
        self.server_comm = ServerProtocol(self.address)
        self.connected = False

        self.signals = UniversalQueue()


    async def run(self):
        signal(SIGINT, lambda signo, frame: self.quit())
        async with TaskGroup(wait=any) as g:
            await g.spawn(self.stdinput_loop)
            await g.spawn(self.events_loop)
            await g.spawn(self.auto_pinger)


    def quit(self):
        logging.debug("Sending quit signal")
        self.signals.put(QuitSignal())


    async def events_loop(self):
        """Reads client-related events"""
        # at the moment this only checks for quit signals
        while True:
            signal = await self.signals.get()
            match signal:
                case QuitSignal():
                    logging.info("Quit msg received; Closing . . .")
                    return
                case StdInput(user_input): # no longer useful
                    logging.info("omg: " + str(user_input))
                case "online":
                    pass
                case "offline":
                    pass


    async def auto_pinger(self):
        """Automatically pings the server every 20 secondes"""
        while True:
            if await self.server_comm.ping():
                logging.info("Ping successful - server online")
                if self.connected == False:
                    await self.signals.put("online")
                self.connected = True
            else:
                logging.info("Ping unsuccessful - server offline")
                if self.connected == True:
                    await self.signals.put("offline")
                self.connected = False
            await sleep(20)


    async def process_stdinput(self, user_input: str):
        """Processes a single line of user input, responding to user commands"""
        if user_input == HELLO_INP:
            print(HELLO_RSP)
        elif user_input == STATUS_INP:
            print(self.connected)
        elif user_input == PING_INP:
            if response := self.server_comm.ping():
                print(f"Ping successful! [{response}]")
            else:
                print ("Server offline or wrong address")
        elif user_input == QUIT_INP:
            quit()


    async def stdinput_loop(self):
        """Indefinitely reads user input from a different thread and processes it"""
        async with TaskGroup() as g:
            while True:
                try:
                    user_input = await run_in_thread(input)
                    await g.spawn(self.process_stdinput, user_input)
                except EOFError:
                    logging.debug("End of input")

async def main():
    client = Client(TRACKER_ADDRESS)
    await client.run()

if __name__ == '__main__':
    run(main)
