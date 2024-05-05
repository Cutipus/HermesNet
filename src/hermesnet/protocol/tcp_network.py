# Imports
import asyncio
from dataclasses import dataclass, field
from typing import AsyncIterator



# Constants
FRAME_SIZE = 4
CHUNK_SIZE = 1024



# Classes
@dataclass
class Session:
    _reader: asyncio.StreamReader
    _writer: asyncio.StreamWriter
    _is_closed: bool = field(default=False, init=False)

    async def send(self, data: bytes) -> None:
        await self._write(len(data).to_bytes(FRAME_SIZE) + data)

    async def receive(self) -> bytes:
        frame = await self._read(FRAME_SIZE, FRAME_SIZE)
        message_length = int.from_bytes(frame)
        return await self._read(message_length, CHUNK_SIZE)

    async def disconnect(self) -> None:
        if self._is_closed:
            return
        self._writer.close()
        await self._writer.wait_closed()
        self._is_closed = True

    async def _write(self, data: bytes) -> None:
        if self._is_closed:
            raise ValueError("I/O operation on closed socket.")
        try:
            self._writer.write(data)
            await self._writer.drain()
        except OSError:
            self._is_closed = True
            raise ConnectionAbortedError("Connection closed while reading frame.")

    async def _read(self, size: int, chunk_size: int):
        if self._is_closed:
            raise ValueError("I/O operation on closed socket.")
        msg = bytearray()
        while delta := size - len(msg) > 0:
            try:
                chunk = await self._reader.read(chunk_size if delta > chunk_size else delta)
            except OSError:
                self._is_closed = True
                raise ConnectionAbortedError("Connection closed while reading.")
            if not chunk:
                self._is_closed = True
                raise ConnectionAbortedError("Connection closed while reading.")
            msg += chunk
        return bytes(msg)


@dataclass
class Server:
    _address: tuple[str, int]
    _unhandled_clients: asyncio.Queue[Session] = field(default_factory=asyncio.Queue, init=False)
    _asyncio_server: asyncio.Server = field(init=False)

    async def _handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        session = Session(reader, writer)
        await self._unhandled_clients.put(session)

    async def start(self) -> None:
        self._asyncio_server = await asyncio.start_server(self._handler, self._address[0], self._address[1])

    async def stop(self) -> None:
        self._asyncio_server.close()

    async def __anext__(self) -> Session:
        return await self._unhandled_clients.get()

    def __aiter__(self) -> AsyncIterator[Session]:
        return self



# Factories
async def start_server(address: tuple[str, int]) -> Server:
    s = Server(address)
    await s.start()
    return s


async def connect(address: tuple[str, int]=('0.0.0.0', 13371)) -> Session:
    reader, writer = await asyncio.open_connection(*address)
    s = Session(reader, writer)
    return s
