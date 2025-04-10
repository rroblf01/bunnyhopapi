import asyncio
import hashlib
import base64
import struct
import uuid
from typing import Callable
import inspect
from . import logger


class WebSocketHandler:
    def __init__(self, websocket_handlers: dict[str, Callable]):
        self.websocket_handlers = websocket_handlers

    async def _read_websocket_frame(self, reader):
        header = await reader.read(2)
        if len(header) < 2:
            raise ConnectionResetError("Incomplete frame header")

        opcode = header[0] & 0x0F
        if opcode == 0x8:  # Close frame
            return opcode, None

        masked = (header[1] & 0x80) != 0
        payload_len = header[1] & 0x7F

        if payload_len == 126:
            payload_len = struct.unpack(">H", await reader.read(2))[0]
        elif payload_len == 127:
            payload_len = struct.unpack(">Q", await reader.read(8))[0]

        mask = await reader.read(4) if masked else None
        data = await reader.read(payload_len)

        if masked:
            decoded = bytearray(data)
            for i in range(len(decoded)):
                decoded[i] ^= mask[i % 4]
            data = decoded

        return opcode, data.decode("utf-8")

    async def _write_websocket_frame(self, writer, message):
        message_bytes = message.encode("utf-8")
        frame = bytearray()
        frame.append(0x81)
        frame.append(len(message_bytes))
        frame.extend(message_bytes)
        writer.write(frame)
        await writer.drain()

    async def handle_websocket(self, reader, writer, path, headers):
        if path not in self.websocket_handlers:
            logger.info(f"No WebSocket handler found for {path}")
            return

        handler_info = self.websocket_handlers[path]
        handler = handler_info["handler"]
        middleware = handler_info.get("middleware")
        connection = handler_info.get("connection")
        disconnect = handler_info.get("disconnect")

        key = headers.get("Sec-WebSocket-Key")
        if not key:
            logger.info("No Sec-WebSocket-Key found in headers")
            return

        if connection:
            is_auth = await connection(headers=headers)
            if not is_auth:
                writer.close()
                await writer.wait_closed()
                return

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

        connection_id = str(uuid.uuid4())

        async def process_message(message):
            if middleware:
                result = middleware(
                    connection_id=connection_id, message=message, headers=headers
                )
            else:
                result = handler(
                    connection_id=connection_id, message=message, headers=headers
                )

            if inspect.isasyncgen(result):
                async for response in result:
                    yield response
            else:
                yield await result

        try:
            while True:
                opcode, message = await self._read_websocket_frame(reader)
                if opcode == 0x8:  # Close frame
                    break

                async for response in process_message(message):
                    await self._write_websocket_frame(writer, response)

        except (ConnectionResetError, asyncio.IncompleteReadError) as e:
            logger.warning(f"WebSocket connection error: {e}")
            logger.info("WebSocket connection closed abruptly")
        finally:
            writer.close()
            await writer.wait_closed()

            if disconnect:
                logger.info("Executing disconnect middleware")
                await disconnect(connection_id=connection_id, headers=headers)
                logger.info("Disconnect middleware executed successfully")
