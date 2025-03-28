import asyncio
from typing import Dict, Callable
import re
from .models import ServerConfig
from .swagger import SwaggerGenerator, SWAGGER_JSON
from .client_handler import ClientHandler

from . import logger


class Server(ServerConfig):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.routes: Dict = {}
        self.routes_with_params: Dict = {}
        self.websocket_handlers: Dict[str, Callable] = {}

    def add_route(self, path, method, handler, content_type="application/json"):
        logger.info(f"Adding route {method} {path}")
        if path not in self.routes:
            self.routes[path] = {}
            if "<" in path:
                self.routes_with_params[path] = self._compile_route_pattern(path)

        self.routes[path][method] = {"handler": handler, "content_type": content_type}

    def add_websocket_route(self, path, handler):
        logger.info(f"Adding websocket route {path}")
        self.websocket_handlers[path] = handler

    def _compile_route_pattern(self, path: str):
        param_pattern = re.compile(r"<(\w+)>")
        regex_pattern = re.sub(param_pattern, r"(?P<\1>[^/]+)", path)
        return re.compile(regex_pattern + r"/?$")

    async def generate_swagger_json(self):
        if not SWAGGER_JSON["paths"]:
            for path, methods in self.routes.items():
                if path in {"/docs", "/swagger.json"}:
                    continue
                SwaggerGenerator.generate_path_item(path, methods)
        return 200, SWAGGER_JSON

    async def swagger_ui_handler(self):
        return 200, SwaggerGenerator.get_swagger_ui_html()

    def add_swagger(self):
        self.add_route(
            "/swagger.json",
            "GET",
            self.generate_swagger_json,
            content_type="application/json",
        )
        self.add_route(
            "/docs", "GET", self.swagger_ui_handler, content_type="text/html"
        )

    async def _run(self):
        client_handler = ClientHandler(
            self.routes, self.routes_with_params, self.websocket_handlers, self.cors
        )

        server = await asyncio.start_server(
            client_handler.handle_client,
            self.host,
            self.port,
            reuse_address=True,
            reuse_port=True,
        )

        addr = server.sockets[0].getsockname()
        logger.info(f"Servidor HTTP escuchando en {addr}")

        async with server:
            await server.serve_forever()

    def run(self):
        self.add_swagger()
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self._run())
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        finally:
            logger.info("Server stopped")
