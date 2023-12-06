"""Server stores knowledge about which client has which file."""
from __future__ import annotations
import logging
from curio import run, tcp_server
from directories import File, Directory, decode
import json
from collections import defaultdict


RECV_SIZE = 1024
declared_dirs = []
files: defaultdict[str, set[str]] = defaultdict(set)


def search_user_dir(dir: Directory, term: str) -> Directory:
    """Search a term in a user directory, returns False if no matches."""
    search_result = dir.copy()

    def search(x: Directory | File) -> bool:
        if term in x.name:
            return True
        match x:
            case File():
                return False
            case Directory():
                x.contents = [y for y in x.contents if search(y)]
                return x.contents != []

    if not search(search_result):
        return False
    else:
        return search_result


def add_user_dir(clientaddr, dir: Directory):
    """Register a user directory, recursively adding files into `files`."""
    declared_dirs.append(dir)

    def get_all_file_hashes(dir: Directory):
        for x in dir.contents:
            match x:
                case File():
                    yield x.hash
                case Directory():
                    yield from get_all_file_hashes(x)

    for filehash in get_all_file_hashes(dir):
        files[filehash].add(clientaddr)


async def receive_message(client, addr):
    """Receive a message from a client connection, and return response."""
    msg = bytearray()
    while data := await client.recv(RECV_SIZE):
        msg += data
    msg = msg.decode()
    response = await process_message(addr, msg)
    logging.info(f"Received message from {addr}: {msg}")
    logging.info(f"Sending response: {response}")
    await client.sendall(response)


async def process_message(clientaddr, msg: str) -> bytes:
    """Parse a single user message, returning a response."""
    if msg == 'ping':
        return b"I'm awake!"
    elif msg.startswith('DECLAREDIR'):
        dir = decode(msg.split(maxsplit=1)[1])
        add_user_dir(clientaddr, dir)
        return f'Sure mate, {dir.name} was added'.encode()
    elif msg == 'ALL':
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
