from . import logger


class ClientHandler:
    async def handle_client(self, reader, writer, request_handler):
        try:
            request_data = await reader.read(8192)
            if not request_data:
                await self._close_writer(writer)
                return

            response = await request_handler(request_data)

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
            logger.debug("Client connection reset before request could be read")
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
