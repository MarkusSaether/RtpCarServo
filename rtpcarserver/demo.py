import logging
from server import Server

logger = logging.getLogger(__name__)

def setup_logger(log_level=logging.DEBUG):
    logging.basicConfig(handlers=[logging.StreamHandler()], level=logging.INFO)

def main():
    setup_logger(logging.INFO)
    server = Server()
    server.start()

if __name__ == '__main__':
    main()
