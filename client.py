'''Receives commands from user and talks to server'''
import logging
from signal import signal, SIGINT
from curio import run, run_in_thread, open_connection, spawn, TaskGroup, Queue, Kernel, UniversalEvent
from socket import SHUT_WR

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.DEBUG)

RECV_SIZE = 1024

TRACKER_ADDRESS = "localhost", 25000
PING_MSG = b"ping"

HELLO_INP = "hello"
PING_INP = "ping"
QUIT_INP = "quit"
HELLO_RSP = "meow"

QUIT = 0

    

async def main():
    user_inputs = Queue()
    events = Queue()
    
    sigint_evt = UniversalEvent()
    signal(SIGINT, lambda signo, frame: sigint_evt.set())

    async def quit():
        logging.info("Shutting down . . .")

        await sigint_evt.set()
        #await events.put(QUIT)

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
            await quit()

    async def input_loop():
        while True:
            try:
                await user_inputs.put(await run_in_thread(input))
            except EOFError:
                logging.info("End of input, closing loop")
                await quit()
                break

    async def process_loop():
        while True:
            user_input = await user_inputs.get()
            async with TaskGroup() as g:
                await g.spawn(process_input, user_input)

    async def events_loop():
        while True:
            async with TaskGroup() as g:
                #await g.spawn(events.get)
                await g.spawn(sigint_evt.wait)

                async for task in g:
                    if task.name == 'UniversalEvent.wait':
                        logging.info('wew')
                        logging.info("Quit msg received; Closing . . .")
                        return


            #if msg == QUIT:
            #    logging.info("Quit msg received; closing . . .")
            #    break

    async with TaskGroup(wait=any) as g:
        await g.spawn(input_loop)
        await g.spawn(process_loop)
        await g.spawn(events_loop)


if __name__ == '__main__':
    run(main)
    #kernel = Kernel()
    #try:
    #    kernel.run(main())
    #except KeyboardInterrupt:
    #    kernel.run(shutdown=True)
    #    print("OK")
