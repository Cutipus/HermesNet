"""Defines the client-server communication protocol.

The protocol is built on by both client and server, and is therefore generic
and allows sending and receiving messages of all kinds.

Contants:
    FRAME_SIZE: The amount of bytes that are used to represent the length of the message.
    CHUNK_SIZE: The size of a chunk read from the socket.

Classes:
    Session: Handles communication between client and server using messages.

Logging:
    Logging functionality is provided.
"""
# Imports
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
import logging

from asyncio import StreamReader, StreamWriter
from typing import Self

from hermesnet.protocol import messages



# Consts
FRAME_SIZE = 4 
CHUNK_SIZE = 1024
_logger = logging.getLogger(__name__)



# Classes
@dataclass
class Connection:
    reader: StreamReader
    writer: StreamWriter

    @classmethod
    async def create_connection(cls, addr: tuple[str, int]) -> Self:
        return cls(*await asyncio.open_connection(*addr))

    async def read(self, n: int) -> bytes:
        return await self.reader.read(n)

    async def write(self, data: bytes) -> None:
        self.writer.write(data)
        await self.writer.drain()


@dataclass
class Session:
    """A class representing the connection between client and server.

    Attributes:
        reader: The asyncio StreamReader.
        writer: The asyncio StreamWriter.
        addr: The connection address.

    Methods:
        read_message: Read a message from the server.
        send_message: Send a message to the server.
        disconnect: Send a disconnect message and close the socket connection.
    """
    # conn: Connection
    reader: StreamReader
    writer: StreamWriter
    addr: tuple[str, int] = field(init=False)
    _is_closed: bool = field(default=False, init=False)

    def __post_init__(self):
        self.addr = self.writer.get_extra_info('peername')
        _logger.debug(f"New Session at {self.addr}")

    async def read_message(self) -> messages.ServerMessage:
        """Send a message to the server."""
        if self._is_closed:
            raise ValueError("I/O operation on closed socket.")

        try:
            if not (frame := await self.reader.read(FRAME_SIZE)):
                self._is_closed = True
                raise ConnectionAbortedError("Connection closed while reading frame.")
        except OSError:
            self._is_closed = True
            raise ConnectionAbortedError("Connection closed while reading frame.")
        _logger.debug(f"FRAME IS: {frame}")
        message_length = int.from_bytes(frame)
        _logger.debug(f"Message length: {message_length}")
        msg = bytearray()
        while len(msg) < message_length:            
            _logger.debug(f"msg: {msg}")
            try:
                if not (chunk := await self.reader.read(CHUNK_SIZE)):
                    raise ConnectionAbortedError("Connection closed while reading message.")
            except OSError:
                self._is_closed = True
                raise ConnectionAbortedError("Connection closed while reading message.")
            msg += chunk
        _logger.debug(f"msg: {msg}")
        return messages.from_bytes(bytes(msg))

    async def send_message(self, message: messages.ServerMessage):
        """Read a message from the server."""
        if self._is_closed:
            raise ValueError("I/O operation on closed socket.")
        encoded_message = bytes(message)
        try:
            _logger.debug(f"Sending message: {len(encoded_message).to_bytes(FRAME_SIZE) + encoded_message}")
            self.writer.write(len(encoded_message).to_bytes(FRAME_SIZE) + encoded_message)
            await self.writer.drain()
        except OSError:
            self._is_closed = True
            raise ConnectionAbortedError("Connection closed while reading frame.")

    async def disconnect(self):
        """Send a disconnect message and close the socket."""
        if self._is_closed:
            return
        await self.send_message(messages.Fin())
        self.writer.close()
        await self.writer.wait_closed()
        self._is_closed = True
