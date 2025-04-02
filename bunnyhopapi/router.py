from typing import Dict, Coroutine
from . import logger
import re
from dataclasses import dataclass, field
from functools import partial


@dataclass
class Router:
    prefix: str = field(default_factory=str)
    routes: Dict[str, Dict[str, Coroutine]] = field(default_factory=dict)
    routes_with_params: Dict[str, re.Pattern] = field(default_factory=dict)
    websocket_handlers: Dict[str, Coroutine] = field(default_factory=dict)
    middleware: Coroutine = field(default=None)

    def include_router(self, router: "Router"):
        for path, context in router.routes.items():
            full_path = f"/{self.prefix.lstrip('/')}/{path.lstrip('/')}".replace(
                "//", "/"
            )

            if full_path not in self.routes:
                self.routes[full_path] = {}
                if "<" in path:
                    self.routes_with_params[full_path] = self._compile_route_pattern(
                        full_path
                    )

            for method, content in context.items():
                handler = content.get("handler")
                existing_middleware = content.get("middleware")

                if self.middleware and existing_middleware:
                    middleware = partial(
                        self.middleware,
                        endpoint=existing_middleware,
                    )
                elif self.middleware:
                    middleware = partial(self.middleware, endpoint=handler)
                elif existing_middleware:
                    middleware = existing_middleware
                else:
                    middleware = None

                self.routes[full_path][method] = {
                    "handler": handler,
                    "content_type": content.get("content_type"),
                    "middleware": middleware,
                }

        self.routes_with_params.update(router.routes_with_params)
        self.websocket_handlers.update(router.websocket_handlers)

    def add_route(
        self,
        path: str,
        method: str,
        handler: Coroutine,
        content_type="application/json",
        middleware: Coroutine = None,
    ):
        path = path.lstrip("/")
        full_path = f"/{self.prefix.lstrip('/')}/{path}".replace("//", "/")

        if full_path not in self.routes:
            self.routes[full_path] = {}
            if "<" in path:
                self.routes_with_params[full_path] = self._compile_route_pattern(
                    full_path
                )

        if middleware and self.middleware:
            final_middleware = partial(
                self.middleware,
                endpoint=partial(middleware, endpoint=handler),
            )
        elif middleware:
            final_middleware = partial(middleware, endpoint=handler)
        elif self.middleware:
            final_middleware = partial(self.middleware, endpoint=handler)
        else:
            final_middleware = handler

        self.routes[full_path][method] = {
            "handler": handler,
            "middleware": final_middleware,
            "content_type": content_type,
        }

    def _compile_route_pattern(self, path: str) -> re.Pattern:
        param_pattern = re.compile(r"<(\w+)>")
        regex_pattern = re.sub(param_pattern, r"(?P<\1>[^/]+)", path)
        return re.compile(regex_pattern + r"/?$")

    def add_websocket_route(self, path: str, handler: Coroutine):
        self.websocket_handlers[path] = handler
