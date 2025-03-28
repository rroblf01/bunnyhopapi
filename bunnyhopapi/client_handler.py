import asyncio
from typing import Optional, Dict
import inspect
from . import logger
from .request import RequestParser
from .response import ResponseHandler
from .handlers import RouteHandler
from .websocket import WebSocketHandler


class ClientHandler:
    def __init__(
        self,
        routes: Dict,
        routes_with_params: Dict,
        websocket_handlers: Dict,
        cors: bool = False,
    ):
        self.request_parser = RequestParser(routes, routes_with_params)
        self.response_handler = ResponseHandler(cors)
        self.route_handler = RouteHandler(routes, routes_with_params)
        self.websocket_handler = WebSocketHandler(websocket_handlers)

    async def handle_client(self, reader, writer):
        request_data = await self._read_request(reader)
        if request_data is None:
            return

        method, path, headers, body = self.request_parser.parse_request(request_data)

        if method is None:
            await self._send_error_response(writer, 400, "Invalid request")
            return

        if method.upper() == "OPTIONS":
            await self._handle_options(writer)
            return

        if headers.get("upgrade") == "websocket":
            logger.info(f"WebSocket connection request to {path}")
            await self.websocket_handler.handle_websocket(reader, writer, path, headers)
            return

        response = await self.route_handler.execute_handler(path, method, body)
        await self._send_response(writer, response)

    async def _read_request(self, reader) -> Optional[bytes]:
        request_data = b""
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                request_data += data
                if b"\r\n\r\n" in request_data:
                    break
            return request_data
        except ConnectionResetError:
            logger.warning("Client connection reset.")
            return None
        except Exception as e:
            logger.error(f"Error reading from client: {e}")
            return None

    async def _send_error_response(self, writer, status_code: int, message: str):
        response = self.response_handler.prepare_response(
            "application/json", status_code, {"error": message}
        )
        writer.write(response)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def _handle_options(self, writer):
        response = self.response_handler.prepare_options_response()
        writer.write(response)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def _send_response(self, writer, response):
        if isinstance(response, tuple) and len(response) == 3:
            content_type, status_code, response_data = response
            prepared = self.response_handler.prepare_response(
                content_type, status_code, response_data
            )
        elif isinstance(response, dict):
            if response.get(
                "content_type"
            ) == "text/event-stream" and inspect.isasyncgen(response["response_data"]):
                prepared, generator = self.response_handler.prepare_response(
                    response["content_type"],
                    response["status_code"],
                    response["response_data"],
                )
                writer.write(prepared)
                await writer.drain()

                try:
                    async for chunk in generator:
                        writer.write(chunk.encode("utf-8"))
                        await writer.drain()
                finally:
                    writer.close()
                    await writer.wait_closed()
                return
            prepared = self.response_handler.prepare_response(
                response["content_type"],
                response["status_code"],
                response["response_data"],
            )
        else:
            prepared = self.response_handler.prepare_response(
                "application/json",
                500,
                {
                    "error": "Internal server error",
                    "message": "Unknown response format",
                },
            )

        writer.write(prepared)
        await writer.drain()
        writer.close()
        await writer.wait_closed()
