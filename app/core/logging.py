import logging


def configure_logging() -> None:
    # Never add questions, journal entries, credentials or retrieved text to logs.
    logging.basicConfig(level=logging.INFO)
