import pytest
from unittest.mock import AsyncMock, Mock, patch, ANY
import struct
from bunnyhopapi.websocket import WebSocketHandler


@pytest.fixture
def websocket_handler():
    handlers = {
        "/ws/test": {
            "handler": AsyncMock(return_value="response"),
            "middleware": None,
            "connection": AsyncMock(return_value=True),
            "disconnect": AsyncMock(),
        }
    }
    return WebSocketHandler(handlers)


@pytest.mark.asyncio
class TestWebSocketHandler:
    async def test_handle_websocket_connection_success(self, websocket_handler):
        reader = AsyncMock()
        writer = AsyncMock()
        writer.write = Mock()
        writer.close = Mock()
        headers = {"Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ=="}

        await websocket_handler.handle_websocket(reader, writer, "/ws/test", headers)

        websocket_handler.websocket_handlers["/ws/test"][
            "connection"
        ].assert_called_once()
        writer.write.assert_called()
        writer.drain.assert_called()

    async def test_handle_websocket_no_handler(self, websocket_handler):
        reader = AsyncMock()
        writer = AsyncMock()
        writer.write = Mock()
        headers = {"Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ=="}

        await websocket_handler.handle_websocket(reader, writer, "/ws/unknown", headers)

        writer.write.assert_not_called()

    async def test_handle_websocket_no_key(self, websocket_handler):
        reader = AsyncMock()
        writer = AsyncMock()
        writer.write = AsyncMock()
        headers = {}

        await websocket_handler.handle_websocket(reader, writer, "/ws/test", headers)

        websocket_handler.websocket_handlers["/ws/test"][
            "connection"
        ].assert_not_called()
        writer.write.assert_not_called()

    async def test_handle_websocket_message_processing(self, websocket_handler):
        reader = AsyncMock()
        writer = AsyncMock()
        writer.write = Mock()
        writer.close = Mock()
        headers = {"Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ=="}
        reader.read.side_effect = [
            b"\x81\x05",  # Frame header
            b"hello",  # Frame payload
            b"\x88\x00",  # Close frame
        ]

        mock_uuid = "mocked-uuid"
        with patch("uuid.uuid4", return_value=mock_uuid):
            await websocket_handler.handle_websocket(
                reader, writer, "/ws/test", headers
            )

        websocket_handler.websocket_handlers["/ws/test"][
            "handler"
        ].assert_called_once_with(
            connection_id=mock_uuid, message="hello", headers=headers
        )
        writer.write.assert_called()

    async def test_handle_websocket_disconnect(self, websocket_handler):
        reader = AsyncMock()
        writer = AsyncMock()
        writer.write = Mock()
        writer.close = Mock()
        headers = {"Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ=="}
        reader.read.side_effect = [
            b"\x88\x00",  # Close frame
        ]

        mock_uuid = "mocked-uuid"
        with patch("uuid.uuid4", return_value=mock_uuid):
            await websocket_handler.handle_websocket(
                reader, writer, "/ws/test", headers
            )

        websocket_handler.websocket_handlers["/ws/test"][
            "disconnect"
        ].assert_called_once_with(connection_id=mock_uuid, headers=headers)
        writer.close.assert_called()

    async def test_handle_websocket_payload_length_126(self, websocket_handler):
        reader = AsyncMock()
        writer = AsyncMock()
        writer.write = Mock()
        writer.close = Mock()
        headers = {"Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ=="}
        reader.read.side_effect = [
            b"\x81\x7e",  # Frame header with payload length 126
            struct.pack(">H", 5),  # Extended payload length
            b"hello",  # Frame payload
            b"\x88\x00",  # Close frame
        ]

        await websocket_handler.handle_websocket(reader, writer, "/ws/test", headers)

        websocket_handler.websocket_handlers["/ws/test"][
            "handler"
        ].assert_called_once_with(connection_id=ANY, message="hello", headers=headers)
        writer.write.assert_called()

    async def test_handle_websocket_payload_length_127(self, websocket_handler):
        reader = AsyncMock()
        writer = AsyncMock()
        writer.write = Mock()
        writer.close = Mock()
        headers = {"Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ=="}
        reader.read.side_effect = [
            b"\x81\x7f",  # Frame header with payload length 127
            struct.pack(">Q", 5),  # Extended payload length
            b"hello",  # Frame payload
            b"\x88\x00",  # Close frame
        ]

        await websocket_handler.handle_websocket(reader, writer, "/ws/test", headers)

        websocket_handler.websocket_handlers["/ws/test"][
            "handler"
        ].assert_called_once_with(connection_id=ANY, message="hello", headers=headers)
        writer.write.assert_called()

    async def test_handle_websocket_no_mask(self, websocket_handler):
        reader = AsyncMock()
        writer = AsyncMock()
        writer.write = Mock()
        writer.close = Mock()
        headers = {"Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ=="}
        reader.read.side_effect = [
            b"\x81\x05",  # Frame header without masking
            b"hello",  # Frame payload
            b"\x88\x00",  # Close frame
        ]

        await websocket_handler.handle_websocket(reader, writer, "/ws/test", headers)

        websocket_handler.websocket_handlers["/ws/test"][
            "handler"
        ].assert_called_once_with(connection_id=ANY, message="hello", headers=headers)
        writer.write.assert_called()

    async def test_handle_websocket_no_sec_websocket_key(self, websocket_handler):
        reader = AsyncMock()
        writer = AsyncMock()
        writer.write = Mock()
        headers = {}  # Missing Sec-WebSocket-Key

        await websocket_handler.handle_websocket(reader, writer, "/ws/test", headers)

        websocket_handler.websocket_handlers["/ws/test"][
            "connection"
        ].assert_not_called()
        writer.write.assert_not_called()

    async def test_handle_websocket_connection_auth_failure(self, websocket_handler):
        reader = AsyncMock()
        writer = AsyncMock()
        writer.write = Mock()
        writer.close = Mock()
        headers = {"Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ=="}
        websocket_handler.websocket_handlers["/ws/test"][
            "connection"
        ].return_value = False

        await websocket_handler.handle_websocket(reader, writer, "/ws/test", headers)

        writer.close.assert_called_once()
        websocket_handler.websocket_handlers["/ws/test"]["handler"].assert_not_called()

    async def test_handle_websocket_masked_payload(self, websocket_handler):
        reader = AsyncMock()
        writer = AsyncMock()
        writer.write = Mock()
        writer.close = Mock()
        headers = {"Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ=="}

        # Masking key: [0x37, 0xfa, 0x21, 0x3d]
        # Original payload: "hello" -> [0x68, 0x65, 0x6c, 0x6c, 0x6f]
        # Masked payload: [0x5f, 0x9f, 0x4d, 0x51, 0x58]
        reader.read.side_effect = [
            b"\x81\x85",  # Frame header with masking and payload length 5
            b"\x37\xfa\x21\x3d",  # Masking key
            b"\x5f\x9f\x4d\x51\x58",  # Masked payload
            b"\x88\x00",  # Close frame
        ]

        await websocket_handler.handle_websocket(reader, writer, "/ws/test", headers)

        websocket_handler.websocket_handlers["/ws/test"][
            "handler"
        ].assert_called_once_with(connection_id=ANY, message="hello", headers=headers)
        writer.write.assert_called()

    async def test_handle_websocket_async_generator_response(self, websocket_handler):
        async def async_generator_response(*args, **kwargs):
            yield "response1"
            yield "response2"

        websocket_handler.websocket_handlers["/ws/test"]["handler"] = (
            async_generator_response
        )

        reader = AsyncMock()
        writer = AsyncMock()
        writer.write = Mock()
        writer.close = Mock()
        headers = {"Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ=="}
        reader.read.side_effect = [
            b"\x81\x05",  # Frame header
            b"hello",  # Frame payload
            b"\x88\x00",  # Close frame
        ]

        await websocket_handler.handle_websocket(reader, writer, "/ws/test", headers)

        writer.write.assert_any_call(bytearray(b"\x81\tresponse1"))
        writer.write.assert_any_call(bytearray(b"\x81\tresponse2"))

    async def test_handle_websocket_with_middleware(self, websocket_handler):
        middleware_mock = AsyncMock(return_value="middleware_response")
        websocket_handler.websocket_handlers["/ws/test"]["middleware"] = middleware_mock

        reader = AsyncMock()
        writer = AsyncMock()
        writer.write = Mock()
        writer.close = Mock()
        headers = {"Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ=="}
        reader.read.side_effect = [
            b"\x81\x05",  # Frame header
            b"hello",  # Frame payload
            b"\x88\x00",  # Close frame
        ]

        mock_uuid = "mocked-uuid"
        with patch("uuid.uuid4", return_value=mock_uuid):
            await websocket_handler.handle_websocket(
                reader, writer, "/ws/test", headers
            )

        middleware_mock.assert_called_once_with(
            connection_id=mock_uuid, message="hello", headers=headers
        )
        writer.write.assert_called_with(bytearray(b"\x81\x13middleware_response"))
