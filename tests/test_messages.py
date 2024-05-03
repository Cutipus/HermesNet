"""Tests for protocol/messages"""
# Imports
from __future__ import annotations
from typing import ClassVar, Protocol, Self
import pytest

from hermesnet.protocol import messages



# Protocols
class Message(Protocol):
    command: ClassVar[int]

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        ...
        
    def __bytes__(self) -> bytes:
        ...

    def __eq__(self, other: object) -> bool:
        ...



# Fixtures
@pytest.fixture
def message() -> Message:
    return messages.All()

@pytest.fixture
def identical_message(message: Message) -> Message:
    return message



# Tests
def test_converting_message_to_bytes_and_back_is_equal_to_the_message(message: Message) -> None:
    assert message == type(message).from_bytes(bytes(message))


def test_messages_can_be_compared(message: Message, identical_message: Message):
    assert message == identical_message
