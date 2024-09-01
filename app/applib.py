from typing import Any, Dict, List, Union, Callable
from random import randint


__all__ = ["Json", "random_id"]


def random_id() -> int:
    return randint(0, 999_999_999)


Json = Union[Dict[str, Any], List[Any]]
