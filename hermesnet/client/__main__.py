import logging.config
import curio

from hermesnet.client import client_term


# TODO: fix logger
_logger = logging.getLogger('hermesnet.client.__main__')
_file_handler = logging.FileHandler('hermesnet-client.log')
_file_handler.setLevel(logging.DEBUG)
_logger.addHandler(_file_handler)


def main():
    c = client_term.CliClient(('127.0.0.1', 13371))
    try:
        curio.run(c.run())
    except KeyboardInterrupt:
        print("Sayonara!")


if __name__ == '__main__':
    main()