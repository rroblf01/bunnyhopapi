import asyncio
import re
import hashlib
import base64
import struct
from typing import Dict, Callable

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
        self.websocket_handlers: Dict[
            str, Callable
        ] = {}  # Almacena los handlers de WebSocket

    def add_route(self, path, method, handler, content_type="application/json"):
        logger.info(f"Adding route {method} {path}")
        if path not in self.routes:
            self.routes[path] = {}
            if "<" in path:  # Si es una ruta con parámetros
                # Registrar el patrón compilado para extraer parámetros
                self.routes_with_params[path] = self._compile_route_pattern(path)

        self.routes[path][method] = {"handler": handler, "content_type": content_type}

    def add_websocket_route(self, path, handler):
        logger.info(f"Adding websocket route {path}")
        self.websocket_handlers[path] = handler

    async def _read_websocket_frame(self, reader):
        """
        Lee un frame WebSocket y devuelve el mensaje decodificado.
        Basado en RFC 6455: https://tools.ietf.org/html/rfc6455
        """
        header = await reader.read(2)
        if len(header) < 2:
            raise ConnectionResetError("Incomplete frame header")

        fin = (header[0] & 0x80) != 0
        opcode = header[0] & 0x0F
        masked = (header[1] & 0x80) != 0
        payload_len = header[1] & 0x7F

        if payload_len == 126:
            payload_len = struct.unpack(">H", await reader.read(2))[0]
        elif payload_len == 127:
            payload_len = struct.unpack(">Q", await reader.read(8))[0]

        if masked:
            mask = await reader.read(4)
        else:
            mask = None

        data = await reader.read(payload_len)

        if masked:
            decoded = bytearray(data)
            for i in range(len(decoded)):
                decoded[i] ^= mask[i % 4]
            data = decoded

        return opcode, data.decode("utf-8")

    async def _write_websocket_frame(self, writer, message):
        """
        Envía un mensaje como frame WebSocket.
        """
        message_bytes = message.encode("utf-8")
        frame = bytearray()
        frame.append(0x81)  # FIN + Opcode (texto)
        frame.append(len(message_bytes))  # Payload length

        frame.extend(message_bytes)
        writer.write(frame)
        await writer.drain()

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

    async def handle_websocket(self, reader, writer, path, headers):
        if path not in self.websocket_handlers:
            logger.info(f"No WebSocket handler found for {path}")
            return

        key = headers.get("sec-websocket-key")
        if not key:
            logger.info("No Sec-WebSocket-Key found in headers")
            return

        # Handshake (igual que antes)
        accept_key = base64.b64encode(
            hashlib.sha1(
                key.encode() + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
            ).digest()
        ).decode()

        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_key}\r\n\r\n"
        ).encode()

        writer.write(response)
        await writer.drain()

        # Manejo de mensajes WebSocket
        try:
            while True:
                opcode, message = await self._read_websocket_frame(reader)
                if opcode == 0x8:  # Close frame
                    break

                # Llama al handler (ej: ws_echo) con el mensaje recibido
                async for response in self.websocket_handlers[path](message):
                    await self._write_websocket_frame(writer, response)

        except (ConnectionResetError, asyncio.IncompleteReadError) as e:
            logger.warning(f"WebSocket connection error: {e}")
            logger.info("WebSocket connection closed abruptly")
        finally:
            logger.info("Closing WebSocket connection")
            writer.close()
            await writer.wait_closed()

    async def handle_request(self, reader, writer, request_data: bytes):
        method, path, headers, body = self.request_parser.parse_request(request_data)

        if method is None:
            response = self.response_handler.prepare_response(
                "application/json", 400, {"error": "Invalid request"}
            )
            writer.write(response)
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return

        if method.upper() == "OPTIONS":
            response = self.response_handler.prepare_options_response()
            writer.write(response)
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return

        if headers.get("upgrade") == "websocket":
            logger.info(f"WebSocket connection request to {path}")
            await self.handle_websocket(reader, writer, path, headers)
            return

        response = await self.handle_response(path, method, body)
        writer.write(response)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def _run(self):
        async def client_handler(reader, writer):
            request_data = b""
            while True:
                try:
                    data = await reader.read(4096)
                    if not data:
                        break
                    request_data += data

                    if b"\r\n\r\n" in request_data:
                        break

                except ConnectionResetError:
                    logger.warning("Client connection reset.")
                    break
                except Exception as e:
                    logger.error(f"Error reading from client: {e}")
                    break

            await self.handle_request(reader, writer, request_data)

        server = await asyncio.start_server(
            client_handler,
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
