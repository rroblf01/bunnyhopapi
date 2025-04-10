from bunnyhopapi.server import Server
from bunnyhopapi import logger
from bunnyhopapi.models import Endpoint
import asyncio
from bunnyhopapi.templates import (
    serve_static_file,
)


class WSEndpoint(Endpoint):
    path = "/ws/chat"

    @Endpoint.MIDDLEWARE()
    async def class_middleware(self, endpoint, headers, **kwargs):
        logger.info("middleware: Before to call the endpoint")
        async for response in endpoint(headers=headers, **kwargs):
            yield response
        logger.info("middleware: After to call the endpoint")

    async def connection(self, headers):
        logger.info("Client connected")
        return True

    async def disconnect(self, connection_id, headers):
        logger.info(f"Client {connection_id} disconnected")

    async def ws(self, connection_id, message, headers):
        logger.info(f"Received message from {connection_id}: {message}")
        for i in range(10):
            yield f"event: message\ndata: {i}\n\n"
            await asyncio.sleep(0.2)


class WSTemplateEndpoint(Endpoint):
    path = "/ws"

    @Endpoint.GET(content_type=Server.CONTENT_TYPE_HTML)
    async def get(self, headers):
        return await serve_static_file("example/templates/static_html/ws_index.html")


def main():
    server = Server(cors=True)

    server.include_endpoint_class(WSEndpoint)
    server.include_endpoint_class(WSTemplateEndpoint)
    server.run()


if __name__ == "__main__":
    main()
