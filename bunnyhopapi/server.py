import asyncio
from typing import Dict
import re
from .models import ServerConfig
from .swagger import SwaggerGenerator, SWAGGER_JSON
from .request import RequestParser
from .response import ResponseHandler
from .handlers import RouteHandler
from .client import ClientHandler

from . import logger


class Server(ServerConfig):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.routes: Dict = {}
        self.routes_with_params: Dict = {}
        self.request_parser = RequestParser(self.routes, self.routes_with_params)
        self.response_handler = ResponseHandler(self.cors)
        self.route_handler = RouteHandler(self.routes, self.routes_with_params)
        self.client_handler = ClientHandler()

    def add_route(self, path, method, handler, content_type="application/json"):
        logger.info(f"Adding route {method} {path}")
        if path not in self.routes:
            self.routes[path] = {}
            if "<" in path:  # Si es una ruta con parámetros
                # Registrar el patrón compilado para extraer parámetros
                self.routes_with_params[path] = self._compile_route_pattern(path)

        self.routes[path][method] = {"handler": handler, "content_type": content_type}

    def _compile_route_pattern(self, path: str):
        """Compila un patrón de ruta con parámetros a una expresión regular"""
        param_pattern = re.compile(r"<(\w+)>")
        regex_pattern = re.sub(param_pattern, r"(?P<\1>[^/]+)", path)
        return re.compile(regex_pattern + r"/?$")

    async def generate_swagger_json(self):
        if SWAGGER_JSON["paths"]:
            return 200, SWAGGER_JSON

        for path, methods in self.routes.items():
            if path in {"/docs", "/swagger.json"}:
                continue
            SwaggerGenerator.generate_path_item(path, methods)

        return 200, SWAGGER_JSON

    async def swagger_ui_handler(self):
        return 200, SwaggerGenerator.get_swagger_ui_html()

    async def handle_response(self, path, method, body=None):
        handler_response = await self.route_handler.execute_handler(path, method, body)

        # Si es una respuesta de error directa
        if isinstance(handler_response, tuple) and len(handler_response) == 3:
            content_type, status_code, response_data = handler_response
            return self.response_handler.prepare_response(
                content_type, status_code, response_data
            )

        # Si es un diccionario con la estructura nueva
        if isinstance(handler_response, dict):
            return self.response_handler.prepare_response(
                handler_response["content_type"],
                handler_response["status_code"],
                handler_response["response_data"],
            )

        # Respuesta por defecto para errores desconocidos
        return self.response_handler.prepare_response(
            "application/json",
            500,
            {"error": "Internal server error", "message": "Unknown response format"},
        )

    async def handle_request(self, request_data: bytes):
        method, path, headers, body = self.request_parser.parse_request(request_data)

        if method is None:
            return self.response_handler.prepare_response(
                "application/json", 400, {"error": "Invalid request"}
            )

        if method.upper() == "OPTIONS":
            return self.response_handler.prepare_options_response()

        return await self.handle_response(path, method, body)

    async def _run(self):
        server = await asyncio.start_server(
            lambda r, w: self.client_handler.handle_client(r, w, self.handle_request),
            self.host,
            self.port,
            reuse_address=True,
            reuse_port=True,
        )

        addr = server.sockets[0].getsockname()
        logger.info(f"Servidor HTTP escuchando en {addr}")

        async with server:
            await server.serve_forever()

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

    def run(self):
        self.add_swagger()
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self._run())
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        finally:
            logger.info("Server stopped")
