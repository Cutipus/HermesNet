"""Receives commands from user and talks to server.

This module enables communication between a client and a server by implementing various methods
to send requests and receive responses asynchronously.

Classes:
    ClientSession: A class representing a client connection session to the server.
    ServerError: An exception class for handling unexpected server responses.

Examples:
    try:
        async with ClientSession('127.0.0.1', 31828) as sp:
            await sp.login("foo", "bar")
            await sp.ping()
            try:
                search_result = await sp.search("some_search_term")
            except ServerError:
                pass  # handle server error for particular command
    except ConnectionError:
        pass  # restart the session or handle gracefully
"""
# stdlib
from __future__ import annotations
import logging
from typing import Self, assert_never, Optional, get_overloads, get_type_hints, overload

# curio
import curio

# project
from hermesnet import protocol as sprotocol


_logger = logging.getLogger(__name__)


class ServerError(Exception):
    """A special exception for unexpected server responses."""
    pass


class ClientSession:
    """A class to represent a client connection session to the server.

    Examples:
        try:
            async with ClientSession('127.0.0.1', 31828) as sp:
                await sp.login("foo", "bar")
                await sp.ping()
                try:
                    search_result = await sp.search("some_search_term")
                except ServerError:
                    pass  # handle server error for particular command
        except ConnectionError:
            pass  # restart the session or handle gracefully

    Note:
        Every method may raise either a ConnectionError or a ServerError.
    """
    def __init__(self, server_ip: str, server_port: int):
        self._protocol: Optional[sprotocol.Session] = None
        self._server_address = (server_ip, server_port)

    async def ping(self) -> sprotocol.Pong | sprotocol.Ok:
        """Pings the server, returning True if server is online else False."""
        return await self._send_message_get_response(sprotocol.Ping())

    async def login(self, name: str, passwd: str) -> sprotocol.Ok:
        """Send login details - typically immediately after connecting."""
        return await self._send_message_get_response(sprotocol.Login(name, passwd))

    async def retrieve_dirs(self) -> sprotocol.SearchResults:
        """Request a list of all the declared directories from the server."""
        return await self._send_message_get_response(sprotocol.All())

    async def declare_directory(self, directory: sprotocol.Directory) -> sprotocol.Ok:
        """Send a directory structure to the server, declaring files available."""
        return await self._send_message_get_response(sprotocol.Declare(directory=directory))

    async def query_file(self, filehash: str) -> sprotocol.QuerySearchResults:
        """Query a file by hash from the server, returns a list of clients."""        
        return await self._send_message_get_response(sprotocol.Query(file_hash=filehash))

    async def search(self, search_term: str) -> sprotocol.SearchResults:
        """Request the server for all search results.

        Returns a list of partial user-declared directories containing search results.
        """
        return await self._send_message_get_response(sprotocol.Search(search_term=search_term))

    @overload
    async def _send_message_get_response(self, message: sprotocol.Login) -> sprotocol.Ok:
        ...
    @overload
    async def _send_message_get_response(self, message: sprotocol.Ping) -> sprotocol.Pong | sprotocol.Ok:
        ...
    @overload
    async def _send_message_get_response(self, message: sprotocol.All) -> sprotocol.SearchResults:
        ...
    @overload
    async def _send_message_get_response(self, message: sprotocol.Declare) -> sprotocol.Ok:
        ...
    @overload
    async def _send_message_get_response(self, message: sprotocol.Search) -> sprotocol.SearchResults:
        ...
    @overload
    async def _send_message_get_response(self, message: sprotocol.Query) -> sprotocol.QuerySearchResults:
        ...
    async def _send_message_get_response(self, message: sprotocol.ServerMessage) -> sprotocol.ServerMessage:
        """Send a message to the server, and return a response.

        Parameters:
            message: The message to send to the server.

        Raises:
            ValueError: If there's an I/O operation on a closed server.
            TypeError: If the message type is not recognized.
            ServerError: If the response isn't the expected response type for that type of message.

        Example:
            response = await self.send_message_get_response(Ping())
        """
        _logger.debug(f"Sending message: {message}")
        if self._protocol is None:
            raise ValueError("I/O operation on a closed session.")

        # find expected response type for given message based on method overload
        for overloaded in map(get_type_hints, get_overloads(self._send_message_get_response)):
            if isinstance(message, overloaded['message']):
                expected_response_type = overloaded['return']
                _logger.debug(f"Message of type {overloaded['message']}! Expecting response of type {expected_response_type}.")
                break
        else:
            raise NotImplemented(f"Messages of type {type(message)} are not supported.")

        # send message and read response
        await self._protocol.send_message(message)
        _logger.info(f"Sent message: {message}")
        response = await self._protocol.read_message()

        # validate response
        match response:
            case sprotocol.ServerMessage() if isinstance(response, expected_response_type):
                _logger.info(f"Received correct response type: {response}")
                return response
            case sprotocol.Error(error):
                _logger.info(f"Received error: {error}")
                raise ServerError(error)
            case sprotocol.ServerMessage():
                _logger.info(f"Received wrong response type: {response}")
                raise ServerError(f"Expected response of type {expected_response_type}, but  got {response} instead.")

    async def __aenter__(self) -> Self:
        """Opens a connection to the server."""
        self._protocol = sprotocol.Session(await curio.open_connection(*self._server_address))
        _logger.info(f"Started session on {self._server_address}")
        return self

    async def __aexit__(self, *_) -> None:
        """Closes the server."""
        _logger.info(f"Closed session.")
        if self._protocol is not None:
            await self._protocol.disconnect()
            self._protocol = None
