import inspect
from . import logger
from .request import RequestParser
from .response import ResponseHandler
from .handlers import RouteHandler
from .websocket import WebSocketHandler
from .models import RouterBase


class ClientHandler:
    def __init__(
        self,
        routes: dict,
        routes_with_params: dict,
        websocket_handlers: dict,
        cors: bool = False,
    ):
        self.request_parser = RequestParser(routes, routes_with_params)
        self.response_handler = ResponseHandler(cors)
        self.route_handler = RouteHandler(routes, routes_with_params)
        self.websocket_handler = WebSocketHandler(websocket_handlers)

    async def handle_client(self, reader, writer):
        request_data = await self._read_request(reader)
        if request_data is None:
            await self._send_error_response(writer, 400, "Invalid request")
            return

        (
            method,
            path,
            headers,
            body,
            query_params,
        ) = await self.request_parser.parse_request(request_data)

        if method is None:
            await self._send_error_response(writer, 400, "Invalid request")
            return

        if method.upper() == "OPTIONS":
            await self._handle_options(writer)
            return

        if (
            headers.get("Connection", "").lower() == "upgrade"
            and headers.get("Upgrade", "").lower() == "websocket"
        ):
            await self.websocket_handler.handle_websocket(reader, writer, path, headers)
            return

        response = await self.route_handler.execute_handler(
            path, method, body, headers, query_params
        )
        await self._send_response(writer, response)

    async def _read_request(self, reader) -> bytes | None:
        try:
            request_data = b""
            while True:
                chunk = await reader.read(8192)
                if not chunk:
                    break
                request_data += chunk
                if b"\r\n\r\n" in request_data:
                    break
            return request_data
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
        try:
            if (
                isinstance(response, dict)
                and response.get("content_type") == RouterBase.CONTENT_TYPE_SSE
                and inspect.isasyncgen(response.get("response_data"))
            ):
                prepared, generator = self.response_handler.prepare_response(
                    response["content_type"],
                    response["status_code"],
                    response["response_data"],
                )

                writer.write(prepared)
                await writer.drain()

                try:
                    async for chunk in generator:
                        if isinstance(chunk, str):
                            chunk = chunk.encode("utf-8")
                        writer.write(chunk)
                        await writer.drain()
                finally:
                    writer.close()
                    await writer.wait_closed()
                return

            if isinstance(response, tuple) and len(response) == 3:
                content_type, status_code, response_data = response
            elif isinstance(response, dict):
                content_type = response["content_type"]
                status_code = response["status_code"]
                response_data = response["response_data"]
            else:
                content_type = "application/json"
                status_code = 500
                response_data = {
                    "error": "Internal server error",
                    "message": "Unknown response format",
                }

            prepared = self.response_handler.prepare_response(
                content_type, status_code, response_data
            )

            writer.write(prepared)
            await writer.drain()

        except Exception as e:
            logger.error(f"Error sending response: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
