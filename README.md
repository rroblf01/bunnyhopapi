# BunnyHop API - HTTP Server Framework

BunnyHop is a lightweight asynchronous HTTP server framework built with Python's asyncio. It provides a simple way to create RESTful APIs with support for WebSockets and Server-Sent Events (SSE).

## Features

- 🚀 Asynchronous request handling
- 📡 WebSocket support
- 🔄 Server-Sent Events (SSE) support
- 📝 Automatic Swagger/OpenAPI documentation
- 🛡️ CORS support
- 🏗️ Pydantic model validation
- 📌 Path parameter handling
- 🔄 Sync and async handler support

## Installation

```bash
pip install bunnyhopapi
```

## Quick Start

```python
from bunnyhopapi.server import Server
from bunnyhopapi.models import PathParam
from pydantic import BaseModel
import asyncio

# Define your models
class HelloResponse(BaseModel):
    message: str

# Define your handlers
async def hello() -> {200: HelloResponse}:
    return 200, {"message": "Hello, World!"}

async def room_handler(room_id: PathParam(int)) -> {200: HelloResponse}:
    return 200, {"message": f"Room ID is {room_id}"}

# Create and configure server
def main():
    server = Server(cors=True)
    server.add_route("/hello", "GET", hello)
    server.add_route("/room/<room_id>", "GET", room_handler)
    server.run()

if __name__ == "__main__":
    main()
```

## API Documentation

By default, the server provides Swagger UI documentation at `/docs` and the OpenAPI spec at `/swagger.json`.

## Handler Types

### Basic HTTP Handler

```python
async def hello() -> {200: HelloResponse}:
    return 200, {"message": "Hello, World!"}
```

### Path Parameters

```python
async def room_handler(room_id: PathParam(int)) -> {200: HelloResponse}:
    return 200, {"message": f"Room ID is {room_id}"}
```

### Request Body Validation

```python
class Room(BaseModel):
    name: str
    capacity: int

async def create_room(room: Room) -> {200: HelloResponse}:
    return 200, {"message": f"Room {room.name} created"}
```

### Server-Sent Events (SSE)

```python
async def sse_events() -> {200: str}:
    events = ["start", "progress", "complete"]
    for event in events:
        yield f"event: {event}\ndata: Processing {event}\n\n"
        await asyncio.sleep(1.5)
```

### WebSocket Handler

```python
async def ws_echo(connection_id, message):
    for i in range(10):
        yield f"event: message\ndata: {i}\n\n"
        await asyncio.sleep(0.2)
```

## Server Configuration

```python
server = Server(
    port=8000,         # default: 8000
    host="0.0.0.0",    # default: "0.0.0.0"
    cors=True          # default: False
)
```

## Adding Routes

```python
server.add_route(
    path="/hello",
    method="GET",
    handler=hello,
    content_type="application/json"  # default
)

server.add_websocket_route(
    path="/ws/chat",
    handler=ws_echo
)
```

## Response Types

Handlers can specify their response types using Python type hints:

```python
async def hello() -> {200: HelloResponse, 404: ErrorResponse}:
    if condition:
        return 200, HelloResponse(message="Hello")
    else:
        return 404, ErrorResponse(error="Not found")
```

## Performance

The BunnyHop API server is highly efficient and can handle a large number of requests per second. Below is an example of a performance test using `wrk`:

```bash
wrk -t12 -c400 -d30s http://127.0.0.1:8000/
```

Results:

```
Running 30s test @ http://127.0.0.1:8000/
  12 threads and 400 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency    16.62ms   32.06ms 864.88ms   98.20%
    Req/Sec   808.15    479.60     3.45k    67.91%
  286177 requests in 30.10s, 63.59MB read
Requests/sec:   9508.94
Transfer/sec:      2.11MB
```

This demonstrates that the server can handle approximately **9508.94 requests per second** under the specified test conditions.

## Examples

See the example in the Quick Start section or check the full example in the repository.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.