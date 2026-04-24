import os
from dotenv import load_dotenv

def load_env() -> None:
    load_dotenv()

def get_required_env(name: str) -> str:
    """Retrieve the value of a required environment variable, raising an error if it is not set.
    Args:        
        name: The name of the environment variable to retrieve.
    Returns:        
        The value of the environment variable.
    Raises:        
        RuntimeError: If the environment variable is not set or is empty.
    """
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

def get_optional_env(name: str, default: str | None = None) -> str | None:
    """
    Retrieve the value of an optional environment variable, returning a default value if it is not set.
    Args:
        name: The name of the environment variable to retrieve.
        default: The default value to return if the environment variable is not set.
    Returns:
        The value of the environment variable or the default value if it is not set.
    """
    return os.getenv(name, default)
