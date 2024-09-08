from typing import Any, Dict, List, Union
from time import time as unixtime
from random import randint
from pathlib import Path


__all__ = ["Json", "JsonD", "random_id", "logf"]


JsonD = Dict[str, Any]
Json = Union[JsonD, List[Any]]


def random_id() -> int:
    return randint(0, 999_999_999)


def logf(err: str | Exception, warn: int = 0):
    """Log.
    `txt` - error text.
    `warn` - warning level (0 - info, 1 - warning, >1 - error).
    """

    warn_level = 'E' if warn > 1 else 'W' if warn else 'I'
    with open(Path(__file__).parent.parent/'log.txt', 'a') as f:
        f.write(f'[{warn_level}]-{str(unixtime())}:\n{err}\n\n')
