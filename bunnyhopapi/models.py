from typing import TypeVar, Generic, Type

from dataclasses import dataclass

T = TypeVar("T")


class PathParam(Generic[T]):
    def __init__(self, param_type: Type[T]):
        self.param_type = param_type

    def validate(self, value: str) -> T:
        try:
            return self.param_type(value)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid value for type {self.param_type}: {value}")


@dataclass
class ServerConfig:
    port: int = 8000
    host: str = "0.0.0.0"
    cors: bool = False
