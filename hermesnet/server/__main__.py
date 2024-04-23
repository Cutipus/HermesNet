"""Run script for the server."""

import logging.config
import asyncio
from hermesnet.common import log_config
from hermesnet.server import Server, Processor


_logger = logging.getLogger('hermesnet.server.__main__')

log_config['handlers']['logfile'] = { # type: ignore
    'level': 'DEBUG',
    'formatter': 'standard',
    'class': 'logging.FileHandler',
    'filename': 'hermesnet-server.log',
    'mode': 'a',
}


def main():
    logging.config.dictConfig(log_config)
    s = Server('0.0.0.0', 13371, Processor())
    _logger.debug("Starting server...")
    try:
        asyncio.run(s.run())
    except KeyboardInterrupt:
        print("Sayonara!")


if __name__ == '__main__':
    main()