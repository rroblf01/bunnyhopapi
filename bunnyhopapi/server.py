import asyncio
import os
import mimetypes
from .templates import serve_static_file
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

    def include_static_folder(self, folder_path: str, route_prefix: str = "/static"):
        folder_path = os.path.abspath(folder_path)

        if not os.path.exists(folder_path):
            logger.error(f"Static folder does not exist: {folder_path}")
            return

        if not os.path.isdir(folder_path):
            logger.error(f"Provided path is not a directory: {folder_path}")
            return

        def static_file_handler(file_path: str):
            try:
                with open(file_path, "rb") as file:
                    content = file.read()
                return (200, content)
            except FileNotFoundError:
                return 404, "File not found"
            except Exception as e:
                logger.error(f"Error serving static file {file_path}: {e}")
                return 500, "Internal server error"

        for root, _, files in os.walk(folder_path):
            logger.debug(f"Walking through: {root}")
            for file_name in files:
                file_path = os.path.join(root, file_name)
                relative_path = os.path.relpath(file_path, folder_path)
                route = f"{route_prefix}/{relative_path}".replace("\\", "/")
                logger.info(f"Serving static file: {file_path} -> {route}")
                content_type, _ = mimetypes.guess_type(file_path)
                logger.info(f"Content type for {file_path}: {content_type}")

                self.add_route(
                    path=route,
                    method="GET",
                    content_type=content_type,
                    handler=lambda headers, file_path=file_path: serve_static_file(
                        file_path
                    ),
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
