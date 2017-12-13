import logging

def test():
    logging.basicConfig()
    logger = logging.getLogger("snowboy")
    logger.setLevel(logging.INFO)
    logger.info('test')


def main():
    logging.basicConfig()
    logger = logging.getLogger("snowboy")
    logger.setLevel(logging.INFO)
    test()
    logger.info('main')

if __name__ == '__main__':
    main()
