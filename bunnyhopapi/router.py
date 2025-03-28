from typing import Dict, Callable
from . import logger
import re
from dataclasses import dataclass, field


@dataclass
class Router:
    prefix: str = field(default_factory=str)
    routes: Dict[str, Dict[str, Callable]] = field(default_factory=dict)
    routes_with_params: Dict[str, re.Pattern] = field(default_factory=dict)
    websocket_handlers: Dict[str, Callable] = field(default_factory=dict)

    def add_route(self, path: str, method: str, handler: Callable):
        logger.info(f"Adding route {method} {path}")
        if self.routes is None:
            self.routes = {}
            self.routes_with_params = {}

        path = path.lstrip("/")
        full_path = f"/{self.prefix.lstrip('/')}/{path}".replace("//", "/")

        if full_path not in self.routes:
            self.routes[full_path] = {}
            if "<" in path:
                self.routes_with_params[full_path] = self._compile_route_pattern(
                    full_path
                )

        self.routes[full_path][method] = handler
        logger.info(f"Route {method} {full_path} added successfully")

    def _compile_route_pattern(self, path: str) -> re.Pattern:
        param_pattern = re.compile(r"<(\w+)>")
        regex_pattern = re.sub(param_pattern, r"(?P<\1>[^/]+)", path)
        return re.compile(regex_pattern + r"/?$")

    def add_websocket_route(self, path: str, handler: Callable):
        logger.info(f"Adding websocket route {path}")
        if self.websocket_handlers is None:
            self.websocket_handlers = {}
        self.websocket_handlers[path] = handler
        logger.info(f"Websocket route {path} added successfully")
