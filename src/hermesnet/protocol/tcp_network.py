# Imports
import asyncio
from dataclasses import dataclass, field
from types import TracebackType
from typing import Awaitable, Callable, Self



# Constants
FRAME_SIZE = 4
MESSAGE_CHUNK_SIZE = 1024



# Classes
@dataclass
class Session:
    _reader: asyncio.StreamReader
    _writer: asyncio.StreamWriter
    _is_closed: bool = field(default=False, init=False)

    async def send(self, data: bytes) -> None:
        frame = self._get_message_frame(data)
        await self._write(frame + data)

    async def receive(self) -> bytes:
        message_length = await self._get_message_length()
        return await self._read_message(message_length)

    async def disconnect(self) -> None:
        self._verify_the_socket_is_open()
        await self._close_writer()
        self._is_closed = True

    def _get_message_frame(self, data: bytes):
        return len(data).to_bytes(FRAME_SIZE)

    async def _get_message_length(self):
        frame_data = await self._get_frame_data()
        message_length = self._get_message_length_from_frame(frame_data)
        return message_length

    async def _read_message(self, message_length: int):
        return await self._read(message_length, MESSAGE_CHUNK_SIZE)

    def _get_message_length_from_frame(self, frame: bytes) -> int:
        return int.from_bytes(frame)

    async def _get_frame_data(self):
        return await self._read(FRAME_SIZE, FRAME_SIZE)

    async def _close_writer(self):
        self._writer.close()
        await self._writer.wait_closed()

    async def _write(self, data: bytes) -> None:
        self._verify_the_socket_is_open()
        await self._try_writing_to_buffer(data)

    async def _try_writing_to_buffer(self, data: bytes):
        try:
            await self._send_data_to_writer(data)
        except OSError:
            self._is_closed = True
            raise ConnectionAbortedError("Connection closed while reading frame.")

    def _verify_the_socket_is_open(self):
        if self._is_closed:
            raise ValueError("I/O operation on closed socket.")

    async def _send_data_to_writer(self, data: bytes):
        self._writer.write(data)
        await self._writer.drain()

    async def _read(self, size: int, chunk_size: int):
        self._verify_the_socket_is_open()
        return await self._read_message_incrementally(size, chunk_size)

    async def _read_message_incrementally(self, size: int, chunk_size: int):
        msg = bytearray()
        while (delta := size - len(msg)) > 0:
            msg += await self._try_to_read_chunk(chunk_size if delta > chunk_size else delta)
        return bytes(msg)

    async def _try_to_read_chunk(self, chunk_size: int):
        try:
            chunk = await self._read_data_from_reader(chunk_size)
        except OSError:
            self._is_closed = True
            raise ConnectionAbortedError("Connection closed while reading.")
        if not chunk:
            self._is_closed = True
            raise ConnectionAbortedError("Connection closed while reading.")
        return chunk

    async def _read_data_from_reader(self, chunk_size: int) -> bytes:
        return await self._reader.read(chunk_size)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: tuple[type[BaseException], BaseException, TracebackType]) -> None:
        await self.disconnect()


@dataclass
class SessionSpawner:
    callback: Callable[[Session], Awaitable[None]]
    address: tuple[str, int]
    _asyncio_server: asyncio.Server = field(init=False)

    async def start(self) -> None:
        self._asyncio_server = await asyncio.start_server(self._handle_new_connection, self.address[0], self.address[1])

    async def stop(self) -> None:
        self._asyncio_server.close()

    async def _handle_new_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        session = Session(reader, writer)
        await self.callback(session)



# Factories
async def start_server(
        callback: Callable[[Session], Awaitable[None]],
        address: tuple[str, int]=('0.0.0.0', 13371)
        ) -> SessionSpawner:
    s = SessionSpawner(callback, address)
    await s.start()
    return s


async def connect(address: tuple[str, int]) -> Session:
    reader, writer = await asyncio.open_connection(*address)
    s = Session(reader, writer)
    return s
