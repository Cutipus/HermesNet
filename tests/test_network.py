"""Tests for protocol/network."""
# Imports
from __future__ import annotations
from typing import Any, AsyncIterator, Protocol
import pytest
from hermesnet.protocol import tcp_network



# Protocols
type Address = tuple[Any, Any]

class Session(Protocol):
    async def send(self, data: bytes):
        ...

    async def receive(self) -> bytes:
        ...

    async def disconnect(self) -> None:
        ...


class Server(Protocol):
    async def stop(self) -> None:
        ...

    async def __anext__(self) -> Session:
        ...

    def __aiter__(self) -> AsyncIterator[Session]:
        ...



# Fixtures
@pytest.fixture
def local_address() -> Address:
    return ('127.0.0.1', 13375)


@pytest.fixture
async def session_pair(local_address: Address) -> tuple[Session, Session]:
    server = await tcp_network.start_server(local_address)
    client = await tcp_network.connect(local_address)
    async for server_client in server:
        return server_client, client
    else:
        assert False



# Tests
async def test_when_session_sends_message_then_other_session_can_receive_it(session_pair: tuple[Session, Session]) -> None:
    sess1, sess2 = session_pair
    await sess1.send(b"hello")
    assert (await sess2.receive()) == b"hello"


async def test_multiple_messages_arrive_in_correct_order(session_pair: tuple[Session, Session]) -> None:
    sess1, sess2 = session_pair
    await sess1.send(b"meow")
    await sess1.send(b"woof")
    await sess1.send(b"woof")
    await sess1.send(b"grr")
    assert (await sess2.receive()) == b"meow"
    assert (await sess2.receive()) == b"woof"
    assert (await sess2.receive()) == b"woof"
    assert (await sess2.receive()) == b"grr"
