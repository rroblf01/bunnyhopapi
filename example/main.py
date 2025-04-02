from bunnyhopapi.server import Server
from bunnyhopapi.router import Router
from bunnyhopapi import logger
from pydantic import BaseModel
import os
import asyncio


class MessageModel(BaseModel):
    message: str


async def greet_user(*args, **kwargs) -> {200: MessageModel}:
    logger.info("greet_user")
    return 200, MessageModel(
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


async def health_check(*args, **kwargs):
    return 200, {"status": "ok"}


async def sse_events(*args, **kwargs):
    events = ["start", "progress", "complete"]
    for event in events:
        yield f"event: {event}\ndata: Processing {event}\n\n"
        await asyncio.sleep(1.5)
    yield "event: end\ndata: All done!\n\n"


async def ws_echo(connection_id, message):
    for i in range(10):
        yield f"event: message\ndata: {i}\n\n"
        await asyncio.sleep(0.2)


def main():
    server = Server(cors=True, middleware=None, port=int(os.getenv("PORT", "8000")))

    nested_router = Router(prefix="/nested", middleware=nested_middleware)
    nested_router.add_route(
        "/greet", "GET", greet_user, middleware=auxiliary_middleware
    )

    greeting_router = Router(prefix="/greetings", middleware=log_request_middleware)
    greeting_router.include_router(nested_router)

    server.include_router(greeting_router)

    server.add_route(
        path="/",
        method="GET",
        handler=health_check,
    )
    server.add_route(
        path="/sse/events",
        method="GET",
        handler=sse_events,
    )

    server.add_websocket_route(
        path="/ws/chat",
        handler=ws_echo,
    )
    server.run()


if __name__ == "__main__":
    main()
