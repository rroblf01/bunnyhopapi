import inspect
from typing import AsyncGenerator, TypeVar, Generic, Type, Dict, Coroutine
import re
from functools import partial
from dataclasses import dataclass, field

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


@dataclass
class RouterBase:
    routes: Dict = field(default_factory=dict)
    routes_with_params: Dict[str, re.Pattern] = field(default_factory=dict)
    middleware: Coroutine = field(default=None)
    websocket_handlers: Dict[str, Coroutine] = field(default_factory=dict)
    prefix: str = field(default_factory=str)

    def include_router(self, router):
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

    def add_websocket_route(self, path, handler, middleware: AsyncGenerator = None):
        class_middleware = (
            self.middleware if inspect.isasyncgenfunction(self.middleware) else None
        )
        method_middleware = (
            middleware if inspect.isasyncgenfunction(middleware) else None
        )
        if class_middleware and method_middleware:
            final_middleware = partial(
                class_middleware,
                endpoint=partial(method_middleware, endpoint=handler),
            )
        elif class_middleware:
            final_middleware = partial(class_middleware, endpoint=handler)

        elif method_middleware:
            final_middleware = partial(method_middleware, endpoint=handler)
        else:
            final_middleware = None

        self.websocket_handlers[path] = {
            "handler": handler,
            "middleware": final_middleware,
        }
