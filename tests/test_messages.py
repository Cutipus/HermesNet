"""Tests for protocol/messages"""
# Imports
from __future__ import annotations
from typing import Callable, ClassVar, Protocol
import pytest

from hermesnet.protocol import messages



# Protocols
type Decoder = Callable[[bytes], Message]


class Message(Protocol):
    command: ClassVar[int]
        
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


@pytest.fixture
def decoder() -> Decoder:
    return messages.from_bytes



# Tests
def test_converting_message_to_bytes_and_back_is_equal_to_the_message(message: Message, decoder: Decoder) -> None:
    assert message == decoder(bytes(message))


def test_messages_can_be_compared(message: Message, identical_message: Message) -> None:
    assert message == identical_message


def test_decoder_raises_exception_when_given_bad_data(decoder: Decoder) -> None:
    with pytest.raises(ValueError):
        decoder(b'meow')


def test_decoder_raises_exception_when_given_no_data(decoder: Decoder) -> None:
    with pytest.raises(ValueError):
        decoder(b'')


def test_decoder_raises_exception_when_given_malicious_data(decoder: Decoder) -> None:
    with pytest.raises(ValueError):
        decoder((30).to_bytes(2) + b'[1, 2, 3]')
