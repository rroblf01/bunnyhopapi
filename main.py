from server.bunnyhopapi import Server, PathParam
from pydantic import BaseModel


class HelloResponse(BaseModel):
    message: str


class HealthCheckResponse(BaseModel):
    status: str


async def hello() -> {200: HelloResponse, 202: HelloResponse}:
    return 200, {"message": "Hello, World!"}


async def room_handler(room_id: PathParam(int)) -> {200: HelloResponse}:
    return 200, {"message": f"Room ID is {room_id}"}


async def helthcheck() -> {200: HealthCheckResponse}:
    return 200, {"status": "OK"}


def main():
    server = Server()
    server.add_route("/", "GET", hello)
    server.add_route("/", "POST", hello)
    server.add_route("/test", "GET", helthcheck)
    server.add_route("/room/<room_id>", "GET", room_handler)
    server.run()


if __name__ == "__main__":
    main()
