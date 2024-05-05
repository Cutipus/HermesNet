"""Tests for protocol/network."""
# Imports
from __future__ import annotations
import asyncio
from types import TracebackType
from typing import Any, Awaitable, Callable, Protocol, Self
import pytest
from hermesnet.protocol import tcp_network



# Protocols
type Address = tuple[Any, Any]
type Callback = Callable[[Session], Awaitable[None]]
type ServerFactory = Callable[[Callback, Address], Awaitable[Server]]
type ClientFactory = Callable[[Address], Awaitable[Session]]

class Session(Protocol):
    async def send(self, data: bytes):
        ...

    async def receive(self) -> bytes:
        ...

    async def disconnect(self) -> None:
        ...

    async def __aenter__(self) -> Self:
        ...

    async def __aexit__(self, *_: tuple[type[BaseException], BaseException, TracebackType]) -> None:
        ...


class Server(Protocol):
    callback: Callable[[Session], Awaitable[None]]

    async def stop(self) -> None:
        ...



# Fixtures
@pytest.fixture
def local_address() -> Address:
    return ('127.0.0.1', 13375)


@pytest.fixture
def server_factory() -> ServerFactory:
    return tcp_network.start_server


@pytest.fixture
def client_factory() -> ClientFactory:
    return tcp_network.connect


# Tests
async def test_server_can_serve_multiple_clients(
        server_factory: ServerFactory,
        client_factory: ClientFactory,
        local_address: Address
        ) -> None:
    connected_clients: asyncio.Queue[Session] = asyncio.Queue()
    server = await server_factory(connected_clients.put, local_address)
    async with (
            await client_factory(local_address) as s1,
            await client_factory(local_address) as s2,
            await client_factory(local_address) as s3,
            await connected_clients.get() as ss1,
            await connected_clients.get() as ss2,
            await connected_clients.get() as ss3,
            ):
        await s1.send(b"eenie")
        await s2.send(b"meanie")
        await s3.send(b"moe")
        assert await ss1.receive() == b"eenie"
        assert await ss2.receive() == b"meanie"
        assert await ss3.receive() == b"moe"
    await server.stop()


async def test_message_sent_by_client_is_received_on_serverside(
        server_factory: ServerFactory,
        client_factory: ClientFactory,
        local_address: Address
        ) -> None:
    connected_clients: asyncio.Queue[Session] = asyncio.Queue()
    server = await server_factory(connected_clients.put, local_address)
    async with await client_factory(local_address) as client, await connected_clients.get() as serverside_client:
        await client.send(b"hello")
        assert (await serverside_client.receive()) == b"hello"
    await server.stop()


async def test_multiple_messages_arrive_in_correct_order(
        server_factory: ServerFactory,
        client_factory: ClientFactory,
        local_address: Address
        ) -> None:
    connected_clients: asyncio.Queue[Session] = asyncio.Queue()
    server = await server_factory(connected_clients.put, local_address)
    async with await client_factory(local_address) as client, await connected_clients.get() as serverside_client:
        await client.send(b"meow")
        await client.send(b"woof")
        await client.send(b"woof")
        await client.send(b"grr")
        assert (await serverside_client.receive()) == b"meow"
        assert (await serverside_client.receive()) == b"woof"
        assert (await serverside_client.receive()) == b"woof"
        assert (await serverside_client.receive()) == b"grr"
    await server.stop()
