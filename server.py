from __future__ import annotations
import logging
from signal import signal, SIGINT
from curio import run, tcp_server
from directories import File, Directory, decode
import json
from collections import defaultdict


KILOBYTE = 1024
declared_dirs = []
files: defaultdict[str, set[str]] = defaultdict(set)


def add_user_dir(clientaddr, dir: Directory):
    print('adding folder', dir.name, 'from client', clientaddr)
    declared_dirs.append(dir)

    def get_all_file_hashes(dir: Directory):
        for x in dir.contents:
            match x:
                case File():
                    yield(x.hash)
                case Directory():
                    yield from get_all_file_hashes(x)

    for filehash in get_all_file_hashes(dir):
        files[filehash].add(clientaddr)


async def receive_message(client, addr):
    # responsible for retrieving a single request from a client
    logging.debug(f'Connection from {addr}')
    msg = bytearray()
    while True:
        data = await client.recv(KILOBYTE)
        if not data:
            break
        msg += data
    logging.info('Message received')
    response = await process_message(addr, msg)
    print(f'Sending response: {response.decode()}')
    await client.sendall(response)


async def process_message(clientaddr, msg: bytearray) -> bytes:
    # parses the message and returns a reply
    # this server should return the ip addresses and data ranges of clients for specific files
    # therefore, the msg should include info on the file in question
    # a client can find info on a speciic file
    # or retrieve a list of files via search
    # the client-tracker protocol should be implemented here
    # first the message is unwrapped from the communication protocol
    # it is then processed
    # lastly the response is wrapped in the communication protocol and returned
    # TODO: handle search queries
    msg = msg.decode()
    if msg == 'ping':
        logging.debug("Ping received")
        return b"I'm awake!"
    elif msg.startswith('DECLAREDIR'):
        logging.debug("Dir declaration received")
        dir = decode(msg.split(maxsplit=1)[1])
        logging.info(dir)
        add_user_dir(clientaddr, dir)
        return f'Sure mate, {dir.name} was added'.encode()
    elif msg == 'ALL':
        print(declared_dirs)
        return Directory('ALL FILES', declared_dirs).to_json().encode()
    elif msg.startswith('QUERY'):
        filehash = msg.split(maxsplit=1)[1]
        if users_with_file := files.get(filehash):
            return json.dumps(list(users_with_file)).encode()
        return b'NOUSERS'


if __name__ == '__main__':
    logging.info('Started. Currently supports "ping", "all" and "declare" command(s).')
    try:
        run(tcp_server, '', 25000, receive_message)
    except KeyboardInterrupt:
        logging.info("Server shutting down...")
