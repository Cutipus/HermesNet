# Imports
import asyncio
from dataclasses import dataclass, field
from types import TracebackType
from typing import Awaitable, Callable, Self



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

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: tuple[type[BaseException], BaseException, TracebackType]) -> None:
        await self.disconnect()


@dataclass
class SessionSpawner:
    callback: Callable[[Session], Awaitable[None]]
    address: tuple[str, int]
    _asyncio_server: asyncio.Server = field(init=False)

    async def _handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        session = Session(reader, writer)
        await self.callback(session)

    async def start(self) -> None:
        self._asyncio_server = await asyncio.start_server(self._handler, self.address[0], self.address[1])

    async def stop(self) -> None:
        self._asyncio_server.close()


# Factories
async def start_server(callback: Callable[[Session], Awaitable[None]], address: tuple[str, int]=('0.0.0.0', 13371)) -> SessionSpawner:
    s = SessionSpawner(callback, address)
    await s.start()
    return s


async def connect(address: tuple[str, int]) -> Session:
    reader, writer = await asyncio.open_connection(*address)
    s = Session(reader, writer)
    return s
