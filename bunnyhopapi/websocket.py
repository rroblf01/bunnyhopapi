import asyncio
import hashlib
import base64
import struct
import uuid
from typing import Callable, Dict

from . import logger


class WebSocketHandler:
    def __init__(self, websocket_handlers: Dict[str, Callable]):
        self.websocket_handlers = websocket_handlers

    async def _read_websocket_frame(self, reader):
        """Lee un frame WebSocket y devuelve el mensaje decodificado."""
        header = await reader.read(2)
        if len(header) < 2:
            raise ConnectionResetError("Incomplete frame header")

        opcode = header[0] & 0x0F
        if opcode == 0x8:  # Close frame
            logger.info("Received close frame")
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
        """Envía un mensaje como frame WebSocket."""
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

        key = headers.get("sec-websocket-key")
        if not key:
            logger.info("No Sec-WebSocket-Key found in headers")
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
        logger.info(f"WebSocket connection established with ID: {connection_id}")

        try:
            while True:
                opcode, message = await self._read_websocket_frame(reader)
                if opcode == 0x8:  # Close frame
                    break

                async for response in self.websocket_handlers[path](
                    connection_id, message
                ):
                    await self._write_websocket_frame(writer, response)

        except (ConnectionResetError, asyncio.IncompleteReadError) as e:
            logger.warning(f"WebSocket connection error: {e}")
            logger.info("WebSocket connection closed abruptly")
        finally:
            logger.info(f"Closing WebSocket connection {connection_id}")
            writer.close()
            await writer.wait_closed()
