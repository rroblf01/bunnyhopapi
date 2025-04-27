import inspect
from typing import AsyncGenerator, TypeVar, Generic, Type, Coroutine, get_origin
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


class QueryParam(Generic[T]):
    def __init__(self, param_type: Type[T], required: bool = False):
        self.param_type = param_type
        self.required = required

    def validate(self, value: str) -> T:
        try:
            return self.param_type(value)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid value for type {self.param_type}: {value}")


class BaseEndpoint:
    middleware = None

    @staticmethod
    def MIDDLEWARE():
        def decorator(func):
            setattr(func, "__class__middleware__", True)

            return func

        return decorator

    @staticmethod
    def __generic_endpoint_method(
        method_name: str,
        middleware=None,
        content_type=None,
    ):
        def decorator(func):
            setattr(func, "__http_method__", method_name)
            setattr(func, "__middleware__", middleware)
            setattr(func, "__content_type__", content_type)

            return func

        return decorator

    @staticmethod
    def GET(middleware=None, content_type=None):
        return BaseEndpoint.__generic_endpoint_method(
            "GET", middleware=middleware, content_type=content_type
        )

    @staticmethod
    def POST(middleware=None, content_type=None):
        return BaseEndpoint.__generic_endpoint_method(
            "POST", middleware=middleware, content_type=content_type
        )

    @staticmethod
    def PUT(middleware=None, content_type=None):
        return BaseEndpoint.__generic_endpoint_method(
            "PUT", middleware=middleware, content_type=content_type
        )

    @staticmethod
    def DELETE(middleware=None, content_type=None):
        return BaseEndpoint.__generic_endpoint_method(
            "DELETE", middleware=middleware, content_type=content_type
        )

    @staticmethod
    def PATCH(middleware=None, content_type=None):
        return BaseEndpoint.__generic_endpoint_method(
            "PATCH", middleware=middleware, content_type=content_type
        )


class Endpoint(BaseEndpoint):
    path: str = ""
    middleware: Coroutine = None

    def get_routes(self):
        routes = {}
        for method_name in dir(self):
            method = getattr(self, method_name)
            if callable(method) and getattr(method, "__class__middleware__", None):
                self.middleware = method
                break

        for method_name in dir(self):
            end_point = getattr(self, method_name)
            if callable(end_point):
                http_method = getattr(end_point, "__http_method__", None)
                if http_method:
                    annotations = getattr(end_point, "__annotations__", {})
                    if annotations:
                        param_names = "/".join(
                            f"<{name}>"
                            for name, value in annotations.items()
                            if get_origin(value) is PathParam
                        )

                        if not param_names:
                            route_path = self.path
                        else:
                            route_path = f"{self.path}/{param_names}".replace("//", "/")
                    else:
                        route_path = self.path

                    method_middleware = getattr(end_point, "__middleware__", None)

                    final_middleware = None

                    if self.middleware and method_middleware:
                        final_middleware = partial(
                            self.middleware,
                            endpoint=partial(method_middleware, endpoint=end_point),
                        )
                    elif self.middleware:
                        final_middleware = partial(self.middleware, endpoint=end_point)
                    elif method_middleware:
                        final_middleware = partial(
                            method_middleware, endpoint=end_point
                        )

                    if route_path not in routes:
                        routes[route_path] = {}

                    routes[route_path][http_method] = {
                        "handler": end_point,
                        "content_type": getattr(end_point, "__content_type__")
                        or RouterBase.CONTENT_TYPE_JSON,
                        "middleware": final_middleware,
                    }
        return routes

    def get_ws_routes(self):
        route_path = self.path
        routes = {}
        routes[route_path] = {}
        start_end_methods = ["connection", "disconnect"]
        for method_name in dir(self):
            if method_name == "ws":
                method = getattr(self, method_name)

                final_middleware = None

                if self.middleware:
                    final_middleware = partial(self.middleware, endpoint=method)

                if callable(method):
                    routes[route_path].update(
                        {
                            "handler": method,
                            "middleware": final_middleware,
                        }
                    )
            elif method_name in start_end_methods:
                method = getattr(self, method_name)
                if callable(method):
                    routes[route_path].update(
                        {
                            method_name: method,
                        }
                    )

        return routes


@dataclass()
class ServerConfig:
    port: int = 8000
    host: str = "0.0.0.0"
    cors: bool = False


@dataclass()
class RouterBase:
    routes: dict = field(default_factory=dict)
    routes_with_params: dict[str, re.Pattern] = field(default_factory=dict)
    middleware: Coroutine = field(default=None)
    websocket_handlers: dict[str, Coroutine] = field(default_factory=dict)
    prefix: str = field(default_factory=str)

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"

    CONTENT_TYPE_JSON = "application/json"
    CONTENT_TYPE_HTML = "text/html"
    CONTENT_TYPE_SSE = "text/event-stream"

    def include_endpoint_class(self, endpoint_class: Type[Endpoint]):
        endpoint = endpoint_class()
        for path, context in endpoint.get_routes().items():
            for method, handler in context.items():
                self.add_route(
                    path=path,
                    method=method,
                    handler=handler.get("handler"),
                    middleware=handler.get("middleware"),
                    content_type=handler.get("content_type"),
                )

        for path, context in endpoint.get_ws_routes().items():
            self.add_websocket_route(
                path=path,
                handler=context.get("handler"),
                middleware=context.get("middleware"),
                connection=context.get("connection"),
                disconnect=context.get("disconnect"),
            )

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

                middleware = None
                if self.middleware and existing_middleware:
                    middleware = partial(
                        self.middleware,
                        endpoint=existing_middleware,
                    )
                elif self.middleware:
                    middleware = partial(self.middleware, endpoint=handler)
                elif existing_middleware:
                    middleware = existing_middleware

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
        content_type=CONTENT_TYPE_JSON,
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

        final_middleware = None
        if middleware and self.middleware:
            final_middleware = partial(
                self.middleware,
                endpoint=partial(middleware, endpoint=handler),
            )
        elif middleware:
            final_middleware = partial(middleware, endpoint=handler)
        elif self.middleware:
            final_middleware = partial(self.middleware, endpoint=handler)

        self.routes[full_path][method] = {
            "handler": handler,
            "middleware": final_middleware,
            "content_type": content_type,
        }

    def _compile_route_pattern(self, path: str) -> re.Pattern:
        param_pattern = re.compile(r"<(\w+)>")
        regex_pattern = re.sub(param_pattern, r"(?P<\1>[^/]+)", path)
        return re.compile(regex_pattern + r"/?$")

    def add_websocket_route(
        self,
        path,
        handler,
        middleware: AsyncGenerator = None,
        connection: Coroutine = None,
        disconnect: Coroutine = None,
    ):
        class_middleware = (
            self.middleware if inspect.isasyncgenfunction(self.middleware) else None
        )
        method_middleware = (
            middleware if inspect.isasyncgenfunction(middleware) else None
        )

        final_middleware = None

        if class_middleware and method_middleware:
            final_middleware = partial(
                class_middleware,
                endpoint=partial(method_middleware, endpoint=handler),
            )
        elif class_middleware:
            final_middleware = partial(class_middleware, endpoint=handler)

        elif method_middleware:
            final_middleware = partial(method_middleware, endpoint=handler)

        self.websocket_handlers[path] = {
            "handler": handler,
            "middleware": final_middleware,
            "connection": connection,
            "disconnect": disconnect,
        }
