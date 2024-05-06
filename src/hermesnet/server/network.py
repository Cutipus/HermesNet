"""Defines the networking aspects of the server.

Classes:
    Server: Handles low-level communication with clients.

Protocols:
    Processor: Handle the processing of each request using queues.

Logging:
    Logging functionality is provided for debugging and monitoring.

Concurrency:
    Uses 'asyncio' for async and I/O.

Example:
    class PingProcessor:
        @asynccontextmanager
        def add_client(self, addr):
            requests = curio.Queue()
            responses = curio.Queue()
            await curio.spawn(self._client_handler(requests, responses))
            try:
                yield requests, responses
            finally:
                await requests.put(sprotocol.Fin())

        def _client_handler(self, requests, responses):
            while True:
                request = await requests.get()
                match request:
                    case protocol.Fin:
                        break
                    case protocol.ServerMessage:
                        response = request
                await responses.put(response)


    if __name__ == '__main__':
        server = Server('127.0.0.1', 22848, PingProcessor())
        curio.run(server.run())
"""
# Imports
from contextlib import AbstractAsyncContextManager
from typing import Protocol
from dataclasses import dataclass
import logging.config

import asyncio

from hermesnet import protocol as sprotocol



# Globals
_logger = logging.getLogger(__name__)



# Protocols
class Processor(Protocol):
    """A Protocol to represet a processor that can be used with the server."""
    def add_client(self, addr: tuple[str, int]) -> AbstractAsyncContextManager[tuple[asyncio.Queue[sprotocol.ServerMessage], asyncio.Queue[sprotocol.ServerMessage]]]:
        ...



# Classes
@dataclass
class Server:
    """A class to represent a server.

    Attributes:
        processor: The processor to process requests and return responses.
        host: The server's IP address.
        port: The server's port.
    """
    host: str
    port: int
    processor: Processor

    async def run(self):
        """Run the server, Indefinitely accept clients."""
        _logger.info(f"Starting server on {self.host}:{self.port}.")
        await asyncio.start_server(self._handle_new_client, self.host, self.port)

    async def _handle_new_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle the lifetime of a single connected client.

        First, creates a request/response queue pair for processing the
        communication through an external processor.
        Then, indefinitely read requests from the sock, passing them to the
        requests queue and sending responses back to the sock from the
        responses queue.

        Parameters:
            sock: The client's connection - closed at the end of the function.
            addr: The client's unique IP/Port address.
        """
        addr: tuple[str, int] | None = writer.get_extra_info('peername')
        if addr is None:
            raise Exception()  # TODO: networkerror?

        _logger.info(f"{addr}: Connected.")
        client = sprotocol.Session(reader, writer)
        _logger.debug(f"{addr}: Prepared Protocol object - {client}")
        async with self.processor.add_client(addr) as (request_queue, response_queue):
            _logger.debug(f"{addr}: Received request/response queues.")

            while True:
                # read request
                try:
                    request = await client.read_message()
                except ConnectionError:
                    _logger.info(f"{addr}: Connection error while reading request.")
                    break
                if isinstance(request, sprotocol.Fin):
                    _logger.info(f"{addr}: Received disconnect message.")
                    break
                _logger.info(f"{addr}: Received request {request}")

                # process request
                await request_queue.put(request)
                _logger.debug(f"{addr}: Request sent to queue {request}")
                response = await response_queue.get()
                _logger.debug(f"{addr}: Response retrieved from queue {response}")

                # send response
                try:
                    await client.send_message(response)
                except ConnectionError:
                    _logger.info(f"{addr}: Connection error while sending response.")
                    break
                if isinstance(response, sprotocol.Fin):
                    _logger.info(f"{addr}: Fin response from queue, closing.")
                    break
                _logger.info(f"{addr}: Sending response {response}")

            _logger.info(f"{addr}: Finished handling.")
 