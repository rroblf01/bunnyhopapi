import os
import signal
import sys
import mimetypes

from multiprocessing import Process
from watchdog.observers import Observer
from threading import Timer
from dataclasses import dataclass, field
from watchdog.events import FileSystemEventHandler
import uvloop
import asyncio

from .templates import serve_static_file
from .models import ServerConfig, RouterBase
from .swagger import SwaggerGenerator, SWAGGER_JSON
from .client_handler import ClientHandler
from . import logger


@dataclass(slots=True)
class Router(RouterBase):
    pass


@dataclass(slots=True)
class Server(ServerConfig, RouterBase):
    auto_reload: bool = False
    observer: Observer = field(init=False, default=Observer())
    processes: list = field(init=False, default_factory=list)
    debounce_timer: Timer = field(init=False, default=None)

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

    def _start_worker(self):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._run())
            else:
                asyncio.run(self._run())
        except KeyboardInterrupt:
            logger.info("Worker received stop signal")

    def run(self, workers: int = os.cpu_count() or 1):
        self.add_swagger()

        uvloop.install()

        if self.auto_reload:
            event_handler = ReloadEventHandler(self)
            self.observer.schedule(event_handler, path=".", recursive=True)
            self.observer.start()

        try:
            for _ in range(workers):
                p = Process(target=self._start_worker)
                p.start()
                self.processes.append(p)

            for p in self.processes:
                p.join()
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        finally:
            for p in self.processes:
                p.terminate()
            if self.observer:
                self.observer.stop()
            logger.info("Server stopped")


class ReloadEventHandler(FileSystemEventHandler):
    def __init__(self, server):
        self.server = server
        self.main_script_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
        self.debounce_delay = 2
        self.last_restart_time = 0

    def on_any_event(self, event):
        logger.debug(f"Detected event: {event}")

        if (
            event.is_directory
            or event.event_type != "modified"
            or not event.src_path.endswith(".py")
        ):
            return

        if event.src_path.endswith("~") or event.src_path == ".":
            return

        event_src_path = os.path.abspath(event.src_path)

        if (
            not os.path.commonpath([self.main_script_dir, event_src_path])
            == self.main_script_dir
        ):
            return

        if any(
            part in event_src_path
            for part in [".git", "__pycache__", "venv", "build", "dist"]
        ):
            return

        logger.info(f"Detected change in {event.src_path}, restarting server...")
        if self.server.debounce_timer is not None:
            self.server.debounce_timer.cancel()

        self.server.debounce_timer = Timer(self.debounce_delay, self.restart_server)
        self.server.debounce_timer.daemon = True
        self.server.debounce_timer.start()

    def restart_server(self):
        if self.server.observer:
            self.server.observer.stop()

        for p in self.server.processes:
            p.terminate()

        for p in self.server.processes:
            p.join()

        os.execv(sys.executable, ["python"] + sys.argv)


def handle_exit(signal, frame):
    logger.info("Shutting down server...")
    os._exit(0)


signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)
