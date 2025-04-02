from bunnyhopapi.server import Server
from bunnyhopapi.router import Router
from bunnyhopapi import logger
from pydantic import BaseModel
import os
import asyncio
from bunnyhopapi.templates import (
    render_template,
    serve_static_html,
    create_template_env,
)


class GreetingResponseModel(BaseModel):
    message: str


async def handle_greeting_request(*args, **kwargs) -> {200: GreetingResponseModel}:
    logger.info("handle_greeting_request")
    return 200, GreetingResponseModel(
        message="Hello, welcome to our API!",
        origin="Hello, welcome to our API!",
    )


async def log_request_middleware(endpoint, *args, **kwargs):
    logger.info(f"START log_request_middleware {endpoint}")
    response = await endpoint(
        *args, **kwargs, origin="Middleware: log_request_middleware"
    )
    logger.info("END log_request_middleware")
    return response


async def auxiliary_middleware(endpoint, *args, **kwargs):
    logger.info("START auxiliary_middleware")
    parent_origin = kwargs.pop("origin")
    logger.info(f"auxiliary_middleware parent_origin: {parent_origin}")
    response = await endpoint(
        *args, **kwargs, origin="Middleware: auxiliary_middleware"
    )
    logger.info("END auxiliary_middleware")
    return response


async def nested_middleware(endpoint, *args, **kwargs):
    logger.info(f"START nested_middleware {endpoint}")
    parent_origin = kwargs.pop("origin")
    response = await endpoint(
        origin="Middleware: nested_middleware",
        parent_origin=parent_origin,
        *args,
        **kwargs,
    )
    logger.info("END nested_middleware")
    return response


async def global_middleware(endpoint, *args, **kwargs):
    logger.info("START global_middleware")
    response = await endpoint(*args, **kwargs)
    logger.info("END global_middleware")
    return response


async def custom_middleware(endpoint, *args, **kwargs):
    logger.info("START custom_middleware")
    response = await endpoint(*args, **kwargs)
    return response


async def health_check_handler(*args, **kwargs):
    return 200, {"status": "ok"}


async def stream_server_sent_events(*args, **kwargs):
    events = ["start", "progress", "complete"]
    for event in events:
        yield f"event: {event}\ndata: Processing {event}\n\n"
        await asyncio.sleep(1.5)
    yield "event: end\ndata: All done!\n\n"


async def websocket_echo_handler(connection_id, message):
    for i in range(10):
        yield f"event: message\ndata: {i}\n\n"
        await asyncio.sleep(0.2)


async def sse_index_handler(*args, **kwargs):
    return await serve_static_html("./example/templates/static_html/sse_index.html")


async def ws_index_handler(*args, **kwargs):
    return await serve_static_html("./example/templates/static_html/ws_index.html")


async def index_handler(*args, **kwargs):
    return await serve_static_html("./example/templates/static_html/index.html")


async def test_template_handler(*args, **kwargs):
    template_env = await create_template_env("./example/templates/jinja")
    return await render_template("test.html", template_env)


def main():
    server = Server(cors=True, middleware=None, port=int(os.getenv("PORT", "8000")))

    nested_router = Router(prefix="/nested", middleware=nested_middleware)
    nested_router.add_route(
        "/greet", "GET", handle_greeting_request, middleware=auxiliary_middleware
    )

    greeting_router = Router(prefix="/greetings", middleware=log_request_middleware)
    greeting_router.include_router(nested_router)

    server.include_router(greeting_router)

    server.add_route(
        path="/health",
        method="GET",
        handler=health_check_handler,
    )
    server.add_route(
        path="/sse/events",
        method="GET",
        handler=stream_server_sent_events,
    )

    server.add_websocket_route(
        path="/ws/chat",
        handler=websocket_echo_handler,
    )

    server.add_route(
        path="/sse",
        method="GET",
        handler=sse_index_handler,
        content_type="text/html",
    )

    server.add_route(
        path="/",
        method="GET",
        handler=index_handler,
        content_type="text/html",
    )

    server.add_route(
        path="/test",
        method="GET",
        handler=test_template_handler,
        content_type="text/html",
    )

    server.add_route(
        path="/ws",
        method="GET",
        handler=ws_index_handler,
        content_type="text/html",
    )

    server.run()


if __name__ == "__main__":
    main()
