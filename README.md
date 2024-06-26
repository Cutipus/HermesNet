> [!NOTE]
> This project is still **work in progress**. It is unsafe and no security considerations have been made. Discretion is advised.

# HermesNet

A distributed file sharing application inspired by SoulSeek and Torrent written in Python.

## Features

- Supports a CLI interactive interface for testing
- Automatically pings server and notifies when the server goes online and offline
- Search for files declared by other users
- Cache previous search results

## Currently Available Commands

| command             | description                                                                                                |
| ------------------- | ---------------------------------------------------------------------------------------------------------- |
| ping                | Pings the server - prints if it's online or offline                                                        |
| hello               | Prints "meow"                                                                                              |
| status              | Prints the server's online status without pinging                                                          |
| quit                | Exits the client                                                                                           |
| declare [directory] | Declares a directory (recursively) to the server, sending file hashes information and file/directory names |
| all                 | Prints all declared directories in the server from all clients                                             |
| query [file hash]   | Requests a list of all clients that declared a file which hash matches the given hash                      |
| help                | Prints this table                                                                                          |
| search [name]       | Asks the server to search all declared files or folders and choose download                                |
| history             | Shows previous search results                                                                              |
| history [n]         | Select the nth previous search result and prompts to download like search                                  |
| login [name] [pass] | Login to server with username. It also registers :3                                                        |

## Getting Started

### Requirements

- Python 3.12+
- Curio

### Installation

1. Clone the project using `git clone https://github.com/Cutipus/HermesNet`.
2. Create virtual environment using `cd HermesNet`, `pip -m venv .venv` - activate using relevant instructions for your OS.
3. Install the package using `python -m pip install .`.

### Running

- Run the server using `python -m hermesnet.server`.
- Run the client using `python -m hermesnet.client`.

### Help

Please forward any questions or problems regarding the prject to Cutipus@protonmail.me
