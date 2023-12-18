"""Server stores knowledge about which client has which file."""
from __future__ import annotations
import logging
from typing import Sequence
import curio, curio.io
from directories import File, Directory, decode
import json
from collections import defaultdict


RECV_SIZE = 1024
declared_dirs: Sequence[Directory] = []  # TODO: add names to user
files: defaultdict[str, set[str]] = defaultdict(set)


def search_user_dir(dir: Directory, term: str) -> Directory | None:
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
        return None
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


async def receive_message(client: curio.io.Socket, addr: tuple[str, int]):
    """Receive a message from a client connection, and return response."""
    print(client, type(client))
    print(addr, type(addr))
    msg: bytearray = bytearray()
    while data := await client.recv(RECV_SIZE):  # BUG: Can potentially cause exception
        msg += data
    response = await process_message(addr, msg.decode())
    logging.info(f"Received message from {addr}: {msg}")
    logging.info(f"Sending response: {response}")
    await client.sendall(response)


async def process_message(clientaddr: tuple[str, int], msg: str) -> bytes:
    """Parse a single user message, returning a response."""
    if msg == 'ping':
        return b"I'm awake!"
    elif msg.startswith('DECLAREDIR'):
        dir = decode(msg.split(maxsplit=1)[1])
        if isinstance(dir, File):
            return b"File declaration unsupported"
        add_user_dir(clientaddr, dir)
        return f'Sure mate, {dir.name} was added'.encode()
    elif msg == 'ALL':
        return Directory('ALL FILES', declared_dirs).to_json().encode()
    elif msg.startswith('QUERY'):
        filehash = msg.split(maxsplit=1)[1]
        if users_with_file := files.get(filehash):
            return json.dumps(list(users_with_file)).encode()
        return b'NOUSERS'
    elif msg.startswith('SEARCH'):
        search_term = msg.split(maxsplit=1)[1]
        search_results: list[Directory] = []
        for x in declared_dirs:
            y = search_user_dir(x, search_term)
            if y is not None:
                search_results.append(y)
        return Directory('SEARCH RESULTS', search_results).to_json().encode()
    else:
        return b"UNSUPPORTED"


def main():
    logging.info('Started. Currently supports "ping", "all" and "declare" command(s).')
    try:
        curio.run(curio.tcp_server, '', 25000, receive_message)
    except KeyboardInterrupt:
        logging.info("Server shutting down...")

if __name__ == '__main__':
    main()
