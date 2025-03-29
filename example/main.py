from bunnyhopapi.server import Server
from bunnyhopapi.router import Router
from bunnyhopapi import logger
import os


async def greet_user(*args, **kwargs):
    logger.info(f"greet_user: {args}, {kwargs}")
    return 200, {"message": "Hello, welcome to our API!"}


async def log_request_middleware(endpoint, *args, **kwargs):
    logger.info(f"START log_request_middleware {endpoint}")
    response = await endpoint(
        *args, **kwargs, origin="Middleware: log_request_middleware"
    )
    logger.info("END log_request_middleware")
    return response


async def auxiliary_middleware(endpoint, *args, **kwargs):
    logger.info("START auxiliary_middleware")
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
    logger.info(f"global_middleware: {args}, {kwargs}")
    response = await endpoint(*args, **kwargs)
    return response


def main():
    server = Server(cors=True, port=int(os.getenv("PORT", "8000")))

    nested_router = Router(prefix="/nested", middleware=nested_middleware)
    nested_router.add_route("/greet", "GET", greet_user)

    greeting_router = Router(prefix="/greetings", middleware=log_request_middleware)
    greeting_router.include_router(nested_router)

    server.include_router(greeting_router)

    server.run()


if __name__ == "__main__":
    main()
