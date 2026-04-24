import logging

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with a standardized format for the SonarQube Quality Assistant application.
    Args:
        name: The name of the logger, typically the module or class name where it is used.
    Returns:
        A configured logger instance with INFO level and a consistent log message format.
    """
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] [%(name)s] %(message)s")
    return logging.getLogger(name)
