import asyncio
import json
import logging
import inspect
import re
from typing import Type, get_type_hints, TypeVar, Generic
from dataclasses import dataclass, field
from pydantic import BaseModel

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
    routes_with_params: dict = field(default_factory=dict)
    cors: bool = False

    def _parse_path(self, path: str):
        param_pattern = re.compile(r"<(\w+)>")
        regex_pattern = re.sub(param_pattern, r"(?P<\1>[^/]+)", path)
        return re.compile(regex_pattern)

    def _extract_params(self, path: str, route_path: str):
        if route_path not in self.routes_with_params:
            return None

        compiled_pattern = self.routes_with_params[route_path]
        match = compiled_pattern.match(path)
        if not match:
            return None

        return match.groupdict()

    async def generate_swagger_json(self):
        if SWAGGER_JSON["paths"]:
            return 200, SWAGGER_JSON

        TYPE_MAPPING = {
            "int": "integer",
            "float": "number",
            "str": "string",
            "bool": "boolean",
        }
        for path, methods in self.routes.items():
            if path in {"/docs", "/swagger.json"}:
                continue

            swagger_path = re.sub(r"<(\w+)>", r"{\1}", path)
            SWAGGER_JSON["paths"][swagger_path] = {}
            for method, details in methods.items():
                handler = details["handler"]
                type_hints = get_type_hints(handler)
                response_schema = {}
                parameters = []
                request_body = None

                # Procesar path parameters
                for param_name, param_type in type_hints.items():
                    if isinstance(param_type, PathParam):
                        inner_type = param_type.param_type
                        type_name = inner_type.__name__.lower()
                        swagger_type = TYPE_MAPPING.get(type_name, type_name)
                        parameters.append(
                            {
                                "name": param_name,
                                "in": "path",
                                "required": True,
                                "schema": {"type": swagger_type},
                            }
                        )

                # Procesar body parameters (modelos Pydantic)
                for param_name, param_type in type_hints.items():
                    if (
                        inspect.isclass(param_type)
                        and issubclass(param_type, BaseModel)
                        and not isinstance(param_type, PathParam)
                    ):
                        request_body = {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": param_type.schema(
                                        ref_template="#/components/schemas/{model}"
                                    )
                                }
                            },
                        }
                        # Añadir el modelo a los componentes schemas si no está ya
                        if "components" not in SWAGGER_JSON:
                            SWAGGER_JSON["components"] = {"schemas": {}}
                        SWAGGER_JSON["components"]["schemas"][param_type.__name__] = (
                            param_type.schema()
                        )

                if details["content_type"] == "text/event-stream":
                    response_schema[200] = {
                        "description": "Server-Sent Events stream",
                        "content": {
                            "text/event-stream": {
                                "schema": {"type": "string", "format": "binary"}
                            }
                        },
                    }

                # Procesar return types
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
                                # Añadir el modelo de respuesta a los componentes
                                if "components" not in SWAGGER_JSON:
                                    SWAGGER_JSON["components"] = {"schemas": {}}
                                SWAGGER_JSON["components"]["schemas"][
                                    model.__name__
                                ] = model.schema()
                    elif inspect.isclass(return_type) and issubclass(
                        return_type, BaseModel
                    ):
                        response_schema[200] = {
                            "description": "Successful response",
                            "content": {
                                "application/json": {"schema": return_type.schema()}
                            },
                        }
                        # Añadir el modelo de respuesta a los componentes
                        if "components" not in SWAGGER_JSON:
                            SWAGGER_JSON["components"] = {"schemas": {}}
                        SWAGGER_JSON["components"]["schemas"][return_type.__name__] = (
                            return_type.schema()
                        )

                # Construir la operación Swagger
                operation = {
                    "summary": f"Handler for {method} {path}",
                    "responses": response_schema
                    or {
                        200: {
                            "description": "Successful response",
                            "content": {"application/json": {"schema": {}}},
                        }
                    },
                }

                if parameters:
                    operation["parameters"] = parameters

                if request_body and method.upper() in ["POST", "PUT", "PATCH"]:
                    operation["requestBody"] = request_body

                SWAGGER_JSON["paths"][swagger_path][method.lower()] = operation

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
            if "<" in path:
                self.routes_with_params[path] = self._parse_path(path)

        self.routes[path][method] = {"handler": handler, "content_type": content_type}

    async def execute_handler(self, path, method, body=None):
        if path in self.routes and method in self.routes[path]:
            route_info = self.routes[path][method]
            return await self._process_handler(route_info, {}, path, method, body)

        for route_path, methods in self.routes.items():
            if method not in methods:
                continue

            params = self._extract_params(path, route_path)
            if params is not None:
                route_info = methods[method]
                return await self._process_handler(
                    route_info, params, path, method, body
                )

        # Si no se encontró ninguna ruta válida
        error_msg = f"Route {method} {path} not found"
        return "application/json", 404, {"error": error_msg}

    async def _process_handler(self, route_info, params, path, method, body):
        handler = route_info["handler"]
        content_type = route_info["content_type"]
        type_hints = get_type_hints(handler)
        validated_params = {}

        for param_name, param_value in params.items():
            if param_name in type_hints:
                param_type = type_hints[param_name]
                logger.debug(f"Processing param {param_name} with type {param_type}")

                if isinstance(param_type, PathParam):
                    try:
                        validated_params[param_name] = param_type.validate(param_value)
                    except ValueError as e:
                        error_msg = f"Invalid path parameter '{param_name}': {str(e)}"
                        return (
                            content_type,
                            422,
                            {"error": error_msg, "field": param_name},
                        )
                else:
                    validated_params[param_name] = param_value

        if body:
            for param_name, param_type in type_hints.items():
                if (
                    inspect.isclass(param_type)
                    and issubclass(param_type, BaseModel)
                    and param_name not in validated_params
                ):
                    try:
                        body_data = json.loads(body)
                    except json.JSONDecodeError:
                        error_msg = "Invalid JSON format in request body"
                        return content_type, 400, {"error": error_msg}

                    try:
                        validated_params[param_name] = param_type(**body_data)
                    except ValueError as e:
                        errors = e.errors()
                        error_details = [
                            {
                                "field": "->".join(str(loc) for loc in error["loc"]),
                                "message": error["msg"],
                                "type": error["type"],
                            }
                            for error in errors
                        ]

                        return (
                            content_type,
                            422,
                            {"error": "Validation error", "details": error_details},
                        )

        try:
            result = handler(**validated_params)

            if inspect.isasyncgen(result):
                return "text/event-stream", 200, result

            response = await result if asyncio.iscoroutine(result) else result

            status_code, response_data = response

            if content_type == "text/html" and isinstance(response_data, str):
                response_data = response_data.encode("utf-8")
            else:
                response_data = json.dumps(response_data).encode("utf-8")

            return content_type, status_code, response_data

        except Exception as e:
            logger.error(f"Handler error for {method} {path}: {str(e)}", exc_info=True)
            return (
                content_type,
                500,
                {"error": "Internal server error", "message": str(e)},
            )

    async def handle_response(self, path, method, body=None):
        cors_headers = (
            (
                b"Access-Control-Allow-Origin: *\r\n"
                b"Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
                b"Access-Control-Allow-Headers: Content-Type\r\n"
            )
            if self.cors
            else b""
        )

        try:
            content_type, status_code, response_data = await self.execute_handler(
                path, method, body
            )

            if content_type == "text/event-stream" and inspect.isasyncgen(
                response_data
            ):
                # Crear una respuesta inicial
                response = (
                    (
                        b"HTTP/1.1 200 OK\r\n"
                        b"Content-Type: text/event-stream\r\n"
                        b"Cache-Control: no-cache\r\n"
                        b"Connection: keep-alive\r\n"
                    )
                    + cors_headers
                    + b"\r\n"
                )

                return response, response_data

            # Si es un error, asegurarnos que el content_type es application/json
            if status_code >= 400:
                content_type = "application/json"
                if isinstance(response_data, dict):
                    response_data = json.dumps(response_data).encode("utf-8")
                else:
                    response_data = json.dumps({"error": str(response_data)}).encode(
                        "utf-8"
                    )

            content_length = len(response_data)

            response = (
                (
                    b"HTTP/1.1 " + str(status_code).encode("utf-8") + b"\r\n"
                    b"Content-Type: " + content_type.encode("utf-8") + b"\r\n"
                    b"Content-Length: " + str(content_length).encode("utf-8") + b"\r\n"
                )
                + cors_headers
                + b"Connection: close\r\n\r\n"
            )
            return response + response_data
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            error_data = json.dumps(
                {"error": "Internal server error", "message": str(e)}
            ).encode("utf-8")
            return (
                (
                    b"HTTP/1.1 500 Internal Server Error\r\n"
                    b"Content-Type: application/json\r\n"
                    b"Content-Length: " + str(len(error_data)).encode("utf-8") + b"\r\n"
                )
                + cors_headers
                + b"Connection: close\r\n\r\n"
                + error_data
            )

    async def handle_client(self, reader, writer):
        try:
            request_data = await reader.read(8192)
            if not request_data:
                await self._close_writer(writer)
                return

            try:
                request_lines = request_data.decode().split("\r\n")
                if len(request_lines) < 1:
                    await self._close_writer(writer)
                    return

                first_line = request_lines[0].split(" ", 2)
                if len(first_line) < 2:
                    await self._close_writer(writer)
                    return

                method, path = first_line[0], first_line[1]

                if method.upper() == "OPTIONS":
                    response = (
                        b"HTTP/1.1 204 No Content\r\n"
                        b"Access-Control-Allow-Origin: *\r\n"
                        b"Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
                        b"Access-Control-Allow-Headers: Content-Type\r\n"
                        b"Content-Length: 0\r\n"
                        b"Connection: close\r\n"
                        b"\r\n"
                    )
                    writer.write(response)
                    await writer.drain()
                    await self._close_writer(writer)
                    return

                headers = {}
                body = None
                for line in request_lines[1:]:
                    if not line.strip():
                        break
                    if ":" in line:
                        key, value = line.split(":", 1)
                        headers[key.strip().lower()] = value.strip()

                if "content-length" in headers:
                    try:
                        content_length = int(headers["content-length"])
                        body_start = request_data.find(b"\r\n\r\n") + 4
                        if body_start > 0 and body_start + content_length <= len(
                            request_data
                        ):
                            body = request_data[
                                body_start : body_start + content_length
                            ].decode("utf-8")
                    except (ValueError, UnicodeDecodeError):
                        pass

                try:
                    response = await self.handle_response(path, method, body)
                    if isinstance(response, tuple) and len(response) == 2:
                        headers, generator = response
                        writer.write(headers)
                        await writer.drain()

                        try:
                            async for chunk in generator:
                                if isinstance(chunk, str):
                                    chunk = chunk.encode("utf-8")
                                writer.write(chunk)
                                await writer.drain()
                        except ConnectionResetError:
                            logger.debug("Client disconnected SSE stream")
                        finally:
                            await self._close_writer(writer)
                        return

                    writer.write(response)
                    await writer.drain()
                except ConnectionResetError:
                    logger.debug("Client disconnected before response could be sent")
                except Exception as e:
                    logger.error(f"Error handling response: {e}")

            except Exception as e:
                logger.error(f"Error processing request: {e}")

        except ConnectionResetError:
            logger.debug("Client connection reset before request could be read")
        except Exception as e:
            logger.error(f"Unexpected client handling error: {e}")
        finally:
            await self._close_writer(writer)

    async def _close_writer(self, writer):
        try:
            if writer.can_write_eof():
                writer.write_eof()
            writer.close()
            await writer.wait_closed()
        except Exception as e:
            logger.debug(f"Error closing writer: {e}")

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
