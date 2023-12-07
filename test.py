"""Testing module.

This module is meant to assist testing the project.
"""
import curio
import client
import server


async def main():
    """Check everything the client/server model can do.

    ... except for things that require more puters.
    """
    c = client.Client(client.TRACKER_ADDRESS).server_comm
    assert not await c.ping()

    # should fail
    try:
        await c.retrieve_dirs()
    except ConnectionRefusedError:
        pass

    try:
        await c.declare_directory('testdir')
    except ConnectionRefusedError:
        pass

    try:
        await c.query_file('da39a3ee5e6b4b0d3255bfef95601890afd80709')
    except ConnectionRefusedError:
        pass

    # bad paths - no such files to begin with
    try:
        await c.declare_directory('badfolder')
    except FileNotFoundError:
        pass

    try:
        await c.query_file('badhash')
    except ConnectionRefusedError:
        pass

    # starting server
    await curio.spawn(curio.tcp_server('', 25000, server.receive_message))
    assert await c.ping()

    # no files declared yet, these should fail despite connection established
    await c.retrieve_dirs()
    await c.query_file('da39a3ee5e6b4b0d3255bfef95601890afd80709')

    # declaring folder
    await c.declare_directory('testdir')
    await c.retrieve_dirs()  # should return one dir with 'testdir' as only subdir

    # bad input
    assert await c.query_file('badhash') == []

    try:
        await c.declare_directory('badfolder')
    except FileNotFoundError:
        pass

    assert (await c.query_file('da39a3ee5e6b4b0d3255bfef95601890afd80709')) != []

    assert (await c.search("file")).contents != []

    assert (await c.search("blablabla")).contents == []


if __name__ == '__main__':
    curio.run(main)
