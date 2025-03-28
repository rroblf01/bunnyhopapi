from bunnyhopapi.server import Server
from bunnyhopapi.router import Router
from bunnyhopapi import logger
from bunnyhopapi.models import PathParam
from pydantic import BaseModel
import asyncio
import os


class HelloResponse(BaseModel):
    message: str


class HealthCheckResponse(BaseModel):
    status: str


class Room(BaseModel):
    name: str
    capacity: int


async def index() -> {200: HelloResponse}:
    return 200, {"message": "Works"}


async def hello() -> {200: HelloResponse, 202: HelloResponse}:
    return 200, {"message": "Hello, World!"}


async def hello_name(name: PathParam(str)) -> {200: HelloResponse, 202: HelloResponse}:
    return 200, {"message": f"Hello, {name}!"}


async def hello_full_name(
    name: PathParam(str), last_name: PathParam(str)
) -> {200: HelloResponse, 202: HelloResponse}:
    return 200, {"message": f"Name {name}, last name {last_name}!"}


def sync_hello() -> {200: HelloResponse, 202: HelloResponse}:
    return 200, {"message": "Hello, World!"}


async def room_handler(room_id: PathParam(int)) -> {200: HelloResponse}:
    return 200, {"message": f"Room ID is {room_id}"}


async def helthcheck() -> {200: HealthCheckResponse}:
    return 200, {"status": "OK"}


async def create_room(room: Room) -> {200: HealthCheckResponse}:
    name = room.name
    capacity = room.capacity
    return 200, {"message": f"Room {name} with capacity {capacity} created"}


async def sse_events():
    events = ["start", "progress", "complete"]
    for event in events:
        yield f"event: {event}\ndata: Processing {event}\n\n"
        await asyncio.sleep(1.5)

    yield "event: end\ndata: All done\n\n"


async def ws_echo(connection_id, message):
    logger.info(f"connection: {connection_id}, message: {message}")

    for i in range(10):
        yield f"event: message\ndata: {i}\n\n"
        await asyncio.sleep(0.2)


async def endpoint_with_middleware(*args, **kwags) -> {200: HelloResponse}:
    return 200, {"message": f"middleware: {kwags.get('fake_client')}"}


async def endpoint_middleware(endpoint, *args, **kwargs):
    logger.info("before endpoint")
    fake_client = {"middleware": "fake_client"}
    response = await endpoint(fake_client=fake_client, *args, **kwargs)
    logger.info("after endpoint")
    return response


def main():
    server = Server(cors=True, port=int(os.getenv("PORT", "8000")))
    hello_router = Router(prefix="/hello")
    hello_router.add_route("/<name>", "GET", hello_name)
    hello_router.add_route("/<name>/last_name/<last_name>", "GET", hello_full_name)

    other_router = Router(prefix="/other", middleware=endpoint_middleware)
    other_router.add_route("/endpoint_with_middleware", "GET", endpoint_with_middleware)

    server.include_router(hello_router)
    server.include_router(other_router)

    server.add_route("/", "GET", index)
    server.add_route("/sync_hello", "GET", sync_hello)
    server.add_route("/test", "GET", helthcheck)
    server.add_route("/room/", "POST", create_room)
    server.add_route("/room/<room_id>", "GET", room_handler)
    server.add_route("/sse/events", "GET", sse_events, content_type="text/event-stream")

    server.add_websocket_route("/ws/chat", ws_echo)
    server.run()


if __name__ == "__main__":
    main()
