"""Server stores knowledge about which client has which file."""
from __future__ import annotations
import curio, curio.io
from directories import File, Directory
from server_protocol import *


class Server:
    def __init__(self):
        """Create a new server.

        declared_dirs: All directories declared by a user.
        users_by_hash: Used to find which users have a file with some hash.
        users: Maps username to IP and password
        """
        self.declared_dirs: dict[User, list[Directory]] = dict()
        self.users_by_hash: dict[str, list[User]] = dict()
        self.hashes_by_user: dict[User, list[str]] = dict()
        self.users_by_username: dict[str, tuple[User, str]] = dict()
        self.bind_address = '', 25000

    async def run(self):
        """Run the server, indefinitely accept client requests."""
        print(f"Starting server on {self.bind_address}")
        await curio.tcp_server(*self.bind_address, self.client_daemon)

    async def declare_dir(self, user: User, dir: Directory):
        """Declare a directory."""
        self.declared_dirs[user].append(dir)
        for x in dir:
            if isinstance(x, File):
                if x.hash not in self.users_by_hash:
                    self.users_by_hash[x.hash] = [user]
                else:
                    self.users_by_hash[x.hash].append(user)

    async def search(self, search_term: str) -> dict[User, list[Directory]]:
        """Search a term across all declared directories."""
        return {user: [searched for dir in dirs if (searched := dir & search_term)] for user, dirs in self.declared_dirs.items()}

    def remove_user(self, user: User):
        """Remove user."""
        del self.users_by_username[user.username]
        del self.declared_dirs[user]
        for file_hash, users in self.users_by_hash.items():
            if user in users:
                users.remove(user)
            if users == []:
                del self.users_by_hash[file_hash]

    def add_user(self, user: User, password: str):
        """Register new user with password. Raise PermissionError if user already registered."""
        # TODO: handle user already existing case
        self.users_by_username[user.username] = (user, password)
        self.declared_dirs[user] = []

    async def client_daemon(self, client: curio.io.Socket, addr: tuple[str, int]):
        """Start communication with client.

        client: The newly received socket connection to the user.
        addr: IP-address and port of the client socket.
        """
        try:
            login_details = await read_message(client)
        except ValueError as e:
            await send_message(client, Error(error_text=str(e)))
            return
        except ConnectionError:
            print("User disconnected...")
            return

        if not isinstance(login_details, Login):
            await send_message(client, Error(error_text="Should be login! BYE!"))
            return

        user = User(login_details.username, addr[0])
        self.add_user(user, login_details.password)
        await send_message(client, Ok())
        print(f"New client connected: {user}")

        while True:
            try:
                message = await read_message(client)
            except ValueError as e:
                await send_message(client, Error(error_text=str(e)))
                continue
            except ConnectionError as e:
                print(e)
                self.remove_user(user)
                return

            match message:
                case Ping(message=msg):
                    response = Pong(message=msg)
                case Declare(directory=dir):
                    await self.declare_dir(user, dir)
                    response = Ok()
                case All():
                    response = SearchResults(results=self.declared_dirs)
                    print(response)
                case Query(file_hash=hash):
                    response = QuerySearchResults(results=self.users_by_hash[hash])
                case Search(search_term=term):
                    response = SearchResults(results=await self.search(term))
                case _:
                    response = Error(error_text="Unrecognized or unsupported message!")

            try:
                await send_message(client, response)
            except ConnectionError as e:
                print(e)
                self.remove_user(user)
                return


def main():
    server = Server()
    try:
        curio.run(server.run)
    except KeyboardInterrupt:
        print("Shutting down...")

if __name__ == '__main__':
    main()
