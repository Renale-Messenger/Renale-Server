from typing import Any, Dict, List, Union
from random import randint


__all__ = ["Json", "JsonD", "random_id"]


def random_id() -> int:
    return randint(0, 999_999_999)


JsonD = Dict[str, Any]
Json = Union[JsonD, List[Any]]
