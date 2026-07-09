import os
import sys

def try_getenv(key: str, default_value:str|None=None):
    value = os.getenv(key)
    if (value is None):
        print(f"Failed to load {key} from .env!")
        if default_value is not None:
            print(f"Default value loaded: {key}={default_value}")
            return default_value
        else:
            sys.exit(1)
    print(f"{key} value loaded from .env: {key}={value}")
    return value

BOT_TOKEN = try_getenv("BOT_TOKEN")
R34_API_KEY = try_getenv("R34_API_KEY")
R34_USER_ID = try_getenv("R34_USER_ID")
POOL_SIZE: int = int(try_getenv("POOL_SIZE", "10000"))
DEVICE = try_getenv("DEVICE", "cpu")
ENDLESS_SUBS = try_getenv("ENDLESS_SUBS")