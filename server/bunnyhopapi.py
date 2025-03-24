import asyncio
import json
import logging
import inspect
import re
from typing import Any, Type, Union, get_type_hints, TypeVar, Generic
from dataclasses import dataclass, field
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

SWAGGER_JSON = {
    "openapi": "3.0.0",
    "info": {
        "title": "BunnyHop API",
        "version": "1.0.0",
    },
    "paths": {},
}

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
class Server:
    port: int = 8000
    host: str = "0.0.0.0"
    routes: dict = field(default_factory=dict)

    def _parse_path(self, path: str):
        param_pattern = re.compile(r"<(\w+)>")
        return re.sub(param_pattern, r"(?P<\1>[^/]+)", path)

    def _extract_params(self, path: str, route_path: str):
        param_pattern = re.compile(r"<(\w+)>")
        param_names = param_pattern.findall(route_path)
        match = re.match(self._parse_path(route_path), path)
        if not match:
            return None
        return {name: match.group(name) for name in param_names}

    async def generate_swagger_json(self):
        if SWAGGER_JSON["paths"]:
            return 200, SWAGGER_JSON

        for path, methods in self.routes.items():
            if path in {"/docs", "/swagger.json"}:
                continue

            # Reemplazar <param> con {param} para Swagger
            swagger_path = re.sub(r"<(\w+)>", r"{\1}", path)
            SWAGGER_JSON["paths"][swagger_path] = {}
            for method, details in methods.items():
                handler = details["handler"]
                type_hints = get_type_hints(handler)
                response_schema = {}
                parameters = []
                for param_name, param_type in type_hints.items():
                    # Detectar y procesar parámetros de tipo PathParam
                    if isinstance(param_type, PathParam):
                        inner_type = (
                            param_type.param_type
                        )  # Acceder a param_type directamente
                        parameters.append(
                            {
                                "name": param_name,
                                "in": "path",
                                "required": False,
                                "schema": {"type": inner_type.__name__.lower()},
                            }
                        )

                if "return" in type_hints:
                    return_type = type_hints["return"]
                    if isinstance(return_type, dict):
                        for status_code, model in return_type.items():
                            if inspect.isclass(model) and issubclass(model, BaseModel):
                                response_schema[status_code] = {
                                    "description": f"Response with status {status_code}",
                                    "content": {
                                        "application/json": {"schema": model.schema()}
                                    },
                                }
                    elif inspect.isclass(return_type) and issubclass(
                        return_type, BaseModel
                    ):
                        response_schema[200] = {
                            "description": "Successful response",
                            "content": {
                                "application/json": {"schema": return_type.schema()}
                            },
                        }

                SWAGGER_JSON["paths"][swagger_path][method.lower()] = {
                    "summary": f"Handler for {method} {path}",
                    "parameters": parameters,
                    "responses": response_schema
                    or {
                        200: {
                            "description": "Successful response",
                            "content": {"application/json": {"schema": {}}},
                        }
                    },
                }
        return 200, SWAGGER_JSON

    async def swagger_ui_handler(self):
        return (
            200,
            """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Swagger UI</title>
            <link rel="stylesheet" type="text/css" href="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.20.0/swagger-ui.css">
        </head>
        <body>
            <div id="swagger-ui"></div>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.20.0/swagger-ui-bundle.js"></script>
            <script>
                const ui = SwaggerUIBundle({
                    url: '/swagger.json',
                    dom_id: '#swagger-ui',
                });
            </script>
        </body>
        </html>
        """,
        )

    def add_route(self, path, method, handler, content_type="application/json"):
        logger.info(f"Adding route {method} {path}")
        if path not in self.routes:
            self.routes[path] = {}
        self.routes[path][method] = {"handler": handler, "content_type": content_type}

    async def execute_handler(self, path, method):
        # Ordenar las rutas por longitud descendente para evitar conflictos
        sorted_routes = sorted(self.routes.items(), key=lambda item: -len(item[0]))
        for route_path, methods in sorted_routes:
            params = self._extract_params(path, route_path)
            if params is not None and method in methods:
                route = methods[method]
                handler = route["handler"]
                content_type = route["content_type"]

                # Validar y convertir parámetros
                type_hints = get_type_hints(handler)
                validated_params = {}
                for param_name, param_value in params.items():
                    if param_name in type_hints:
                        param_type = type_hints[param_name]
                        logger.info(f"{param_name} {param_type.__dict__} {param_value}")
                        if isinstance(param_type, PathParam):
                            logger.info("**********************")
                            logger.info("**********************")
                            logger.info("**********************")
                            logger.info("**********************")
                            logger.info("**********************")
                            logger.info(f"{param_type} {param_value}")
                            validated_params[param_name] = param_type.validate(
                                param_value
                            )
                        else:
                            validated_params[param_name] = param_value

                response = await handler(**validated_params)

                if asyncio.iscoroutine(response):
                    response = await response

                status_code, response_data = response

                if content_type == "text/html" and isinstance(response_data, str):
                    response_data = response_data.encode("utf-8")
                else:
                    response_data = json.dumps(response_data).encode("utf-8")

                return content_type, status_code, response_data

        raise KeyError("Route not found")

    async def handle_response(self, path, method):
        try:
            content_type, status_code, response_data = await self.execute_handler(
                path, method
            )
            content_length = len(response_data)

            response = (
                b"HTTP/1.1 " + str(status_code).encode("utf-8") + b"\r\n"
                b"Content-Type: " + content_type.encode("utf-8") + b"\r\n"
                b"Content-Length: " + str(content_length).encode("utf-8") + b"\r\n"
                b"Connection: close\r\n"
                b"\r\n"
            )
            return response + response_data
        except KeyError:
            return b"HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n"
        except TypeError as e:
            logger.error(f"Serialization error: {e}")
            return b"HTTP/1.1 500 Internal Server Error\r\nConnection: close\r\n\r\n"

    async def handle_client(self, reader, writer):
        try:
            request_line = await reader.read(
                8192
            )  # Incrementar tamaño del búfer de lectura
            if not request_line:
                writer.close()
                await writer.wait_closed()
                return

            method, path, _ = request_line.decode().split(" ", 2)

            response = await self.handle_response(path, method)

            writer.write(response)
            await writer.drain()
        except Exception as e:
            logger.error(f"Error manejando cliente: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def _run(self):
        server = await asyncio.start_server(
            self.handle_client,
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
