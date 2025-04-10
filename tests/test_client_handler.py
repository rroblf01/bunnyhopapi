import pytest
from unittest.mock import AsyncMock, Mock, patch
from bunnyhopapi.client_handler import ClientHandler
from bunnyhopapi.models import RouterBase


class TestClientHandler:
    @pytest.fixture
    def client_handler(self):
        routes = {}
        routes_with_params = {}
        websocket_handlers = {}
        return ClientHandler(routes, routes_with_params, websocket_handlers, cors=True)

    @pytest.mark.asyncio
    async def test_handle_client_invalid_request(self, client_handler):
        reader = AsyncMock()
        writer = AsyncMock()
        reader.read = AsyncMock(return_value=b"")
        writer.write = Mock()
        writer.close = Mock()

        await client_handler.handle_client(reader, writer)

        writer.write.assert_called_once()
        assert b"400" in writer.write.call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_client_websocket_request(self, client_handler):
        reader = AsyncMock()
        writer = AsyncMock()
        reader.read = AsyncMock(
            return_value=b"GET /ws HTTP/1.1\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\r\n"
        )
        writer.write = Mock()

        with patch.object(
            client_handler.websocket_handler, "handle_websocket", new=AsyncMock()
        ) as mock_ws_handler:
            await client_handler.handle_client(reader, writer)

        mock_ws_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_response(self, client_handler):
        writer = AsyncMock()
        writer.write = Mock()
        writer.drain = AsyncMock()
        writer.close = Mock()
        writer.wait_closed = AsyncMock()

        response = {
            "content_type": "application/json",
            "status_code": 200,
            "response_data": {"message": "Success"},
        }

        with patch.object(
            client_handler.response_handler,
            "prepare_response",
            return_value=b"HTTP/1.1 200 OK\r\n\r\n",
        ) as mock_prepare_response:
            await client_handler._send_response(writer, response)

        mock_prepare_response.assert_called_once_with(
            "application/json", 200, {"message": "Success"}
        )
        writer.write.assert_called_once_with(b"HTTP/1.1 200 OK\r\n\r\n")
        writer.drain.assert_called_once()
        writer.close.assert_called_once()
        writer.wait_closed.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_response_sse(self, client_handler):
        writer = AsyncMock()
        writer.write = Mock()
        writer.drain = AsyncMock()
        writer.close = Mock()
        writer.wait_closed = AsyncMock()

        async def async_gen():
            yield "data: message1\n\n"
            yield "data: message2\n\n"

        response = {
            "content_type": RouterBase.CONTENT_TYPE_SSE,
            "status_code": 200,
            "response_data": async_gen(),
        }

        with patch.object(
            client_handler.response_handler,
            "prepare_response",
            return_value=(
                b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\r\n",
                async_gen(),
            ),
        ) as mock_prepare_response:
            await client_handler._send_response(writer, response)

        mock_prepare_response.assert_called_once_with(
            RouterBase.CONTENT_TYPE_SSE, 200, response["response_data"]
        )
        writer.write.assert_any_call(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\r\n"
        )
        writer.write.assert_any_call(b"data: message1\n\n")
        writer.write.assert_any_call(b"data: message2\n\n")
        writer.drain.assert_called()
        writer.close.call_count == 2
        writer.wait_closed.call_count == 2

    @pytest.mark.asyncio
    async def test_handle_options(self, client_handler):
        writer = AsyncMock()
        writer.write = Mock()
        writer.drain = AsyncMock()
        writer.close = Mock()
        writer.wait_closed = AsyncMock()

        with patch.object(
            client_handler.response_handler,
            "prepare_options_response",
            return_value=b"HTTP/1.1 204 No Content\r\n\r\n",
        ) as mock_prepare_options_response:
            await client_handler._handle_options(writer)

        mock_prepare_options_response.assert_called_once()
        writer.write.assert_called_once_with(b"HTTP/1.1 204 No Content\r\n\r\n")
        writer.drain.assert_called_once()
        writer.close.assert_called_once()
        writer.wait_closed.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_response_tuple(self, client_handler):
        writer = AsyncMock()
        writer.write = Mock()
        writer.drain = AsyncMock()
        writer.close = Mock()
        writer.wait_closed = AsyncMock()

        response = ("application/json", 201, {"message": "Created"})

        with patch.object(
            client_handler.response_handler,
            "prepare_response",
            return_value=b"HTTP/1.1 201 Created\r\n\r\n",
        ) as mock_prepare_response:
            await client_handler._send_response(writer, response)

        mock_prepare_response.assert_called_once_with(
            "application/json", 201, {"message": "Created"}
        )
        writer.write.assert_called_once_with(b"HTTP/1.1 201 Created\r\n\r\n")
        writer.drain.assert_called_once()
        writer.close.assert_called_once()
        writer.wait_closed.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_response_else_case(self, client_handler):
        writer = AsyncMock()
        writer.write = Mock()
        writer.drain = AsyncMock()
        writer.close = Mock()
        writer.wait_closed = AsyncMock()

        response = "invalid_response_format"

        with patch.object(
            client_handler.response_handler,
            "prepare_response",
            return_value=b"HTTP/1.1 500 Internal Server Error\r\n\r\n",
        ) as mock_prepare_response:
            await client_handler._send_response(writer, response)

        mock_prepare_response.assert_called_once_with(
            "application/json",
            500,
            {
                "error": "Internal server error",
                "message": "Unknown response format",
            },
        )
        writer.write.assert_called_once_with(
            b"HTTP/1.1 500 Internal Server Error\r\n\r\n"
        )
        writer.drain.assert_called_once()
        writer.close.assert_called_once()
        writer.wait_closed.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_response_exception_handling(self, client_handler):
        writer = AsyncMock()
        writer.write = Mock(side_effect=Exception("Mocked write exception"))
        writer.drain = AsyncMock()
        writer.close = Mock()
        writer.wait_closed = AsyncMock()

        response = {
            "content_type": "application/json",
            "status_code": 200,
            "response_data": {"message": "Success"},
        }

        with patch("bunnyhopapi.client_handler.logger.error") as mock_logger_error:
            await client_handler._send_response(writer, response)

        mock_logger_error.assert_called_once_with(
            "Error sending response: Mocked write exception"
        )
        writer.close.assert_called_once()
        writer.wait_closed.assert_called_once()

    @pytest.mark.asyncio
    async def test_read_request_exception_handling(self, client_handler):
        reader = AsyncMock()
        reader.read = AsyncMock(side_effect=Exception("Mocked read exception"))

        with patch("bunnyhopapi.client_handler.logger.error") as mock_logger_error:
            result = await client_handler._read_request(reader)

        mock_logger_error.assert_called_once_with(
            "Error reading from client: Mocked read exception"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_client_request_data_none(self, client_handler):
        reader = AsyncMock()
        writer = AsyncMock()
        reader.read = AsyncMock(return_value=None)
        writer.write = Mock()
        writer.close = Mock()

        with (
            patch.object(
                client_handler, "_read_request", return_value=None
            ) as mock_read_request,
            patch.object(
                client_handler, "_send_error_response", new=AsyncMock()
            ) as mock_send_error_response,
        ):
            await client_handler.handle_client(reader, writer)

        mock_read_request.assert_called_once_with(reader)
        mock_send_error_response.assert_called_once_with(writer, 400, "Invalid request")

    @pytest.mark.asyncio
    async def test_handle_client_options_method(self, client_handler):
        reader = AsyncMock()
        writer = AsyncMock()
        reader.read = AsyncMock(return_value=b"OPTIONS / HTTP/1.1\r\n\r\n")
        writer.write = Mock()
        writer.close = Mock()

        with (
            patch.object(
                client_handler.request_parser,
                "parse_request",
                return_value=("OPTIONS", "/", {}, None, {}),
            ) as mock_parse_request,
            patch.object(
                client_handler, "_handle_options", new=AsyncMock()
            ) as mock_handle_options,
        ):
            await client_handler.handle_client(reader, writer)

        mock_parse_request.assert_called_once_with(b"OPTIONS / HTTP/1.1\r\n\r\n")
        mock_handle_options.assert_called_once_with(writer)

    @pytest.mark.asyncio
    async def test_handle_client_execute_handler(self, client_handler):
        reader = AsyncMock()
        writer = AsyncMock()
        reader.read = AsyncMock(return_value=b"GET /test HTTP/1.1\r\n\r\n")
        writer.write = Mock()
        writer.close = Mock()

        with (
            patch.object(
                client_handler.request_parser,
                "parse_request",
                return_value=("GET", "/test", {}, None, {}),
            ) as mock_parse_request,
            patch.object(
                client_handler.route_handler,
                "execute_handler",
                new=AsyncMock(
                    return_value={
                        "content_type": "application/json",
                        "status_code": 200,
                        "response_data": {"message": "OK"},
                    }
                ),
            ) as mock_execute_handler,
            patch.object(
                client_handler, "_send_response", new=AsyncMock()
            ) as mock_send_response,
        ):
            await client_handler.handle_client(reader, writer)

        mock_parse_request.assert_called_once_with(b"GET /test HTTP/1.1\r\n\r\n")
        mock_execute_handler.assert_called_once_with("/test", "GET", None, {}, {})
        mock_send_response.assert_called_once_with(
            writer,
            {
                "content_type": "application/json",
                "status_code": 200,
                "response_data": {"message": "OK"},
            },
        )
