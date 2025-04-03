import asyncio
import os
from .models import ServerConfig, RouterBase
from .swagger import SwaggerGenerator, SWAGGER_JSON
from .client_handler import ClientHandler
from . import logger
import uvloop
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Router(RouterBase):
    pass


@dataclass(frozen=True, slots=True)
class Server(ServerConfig, RouterBase):
    async def generate_swagger_json(self, *args, **kwargs):
        if not SWAGGER_JSON["paths"]:
            for path, methods in self.routes.items():
                if path in {"/docs", "/swagger.json"}:
                    continue
                SwaggerGenerator.generate_path_item(path, methods)
        return 200, SWAGGER_JSON

    async def swagger_ui_handler(self, *args, **kwargs):
        return 200, SwaggerGenerator.get_swagger_ui_html()

    def add_swagger(self):
        self.add_route(
            path="/swagger.json",
            method="GET",
            handler=self.generate_swagger_json,
            content_type="application/json",
        )
        self.add_route(
            path="/docs",
            method="GET",
            handler=self.swagger_ui_handler,
            content_type="text/html",
        )

    async def _run(self):
        client_handler = ClientHandler(
            self.routes, self.routes_with_params, self.websocket_handlers, self.cors
        )

        server = await asyncio.start_server(
            client_handler.handle_client,
            self.host,
            self.port,
            reuse_address=True,
            reuse_port=True,
        )

        addr = server.sockets[0].getsockname()
        logger.info(f"HTTP server listening on {addr}")

        async with server:
            await server.serve_forever()

    def run(self, workers: int = os.cpu_count() or 1):
        self.add_swagger()

        uvloop.install()
        processes = []
        try:
            for _ in range(workers):
                pid = os.fork()
                if pid == 0:  # Proceso hijo
                    loop = asyncio.get_event_loop()
                    loop.run_until_complete(self._run())
                    os._exit(0)
                else:  # Proceso padre
                    processes.append(pid)

            for pid in processes:
                os.waitpid(pid, 0)
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        finally:
            logger.info("Server stopped")
