'''Receives commands from user and talks to server'''
import logging
from curio import run, run_in_thread, open_connection, spawn, TaskGroup, Queue
from socket import SHUT_WR

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.DEBUG)

RECV_SIZE = 1024

TRACKER_ADDRESS = "localhost", 25000
PING_MSG = b"ping"

HELLO_INP = "hello"
PING_INP = "ping"
QUIT_INP = "quit"
HELLO_RSP = "meow"

async def async_input(msg: str = "") -> str:
    return await run_in_thread(input, msg)

async def process_input(user_input: str):
    if user_input == HELLO_INP:
        print(HELLO_RSP)
    elif user_input == PING_INP:
        logging.info("pinging . . .")
        conn = await open_connection(*TRACKER_ADDRESS)
        await conn.sendall(PING_MSG)
        await conn.shutdown(SHUT_WR)
        response = await conn.recv(RECV_SIZE)
        logging.info(f"Message received: {response}")
    elif user_input == QUIT_INP:
        logging.info("Shutting down . . .")
        raise NotImplemented # implement this with a message queue back to input
    

async def main():
    input_queue = Queue()

    async def input_loop():
        while True:
            await input_queue.put(await async_input())

    async def process_loop():
        while True:
            user_input = await input_queue.get()
            async with TaskGroup() as g:
                await g.spawn(process_input, user_input)

    async with TaskGroup(wait=any) as g:
        await g.spawn(input_loop)
        await g.spawn(process_loop)
    

if __name__ == '__main__':
    run(main)
