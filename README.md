Here's the updated README.md incorporating the Router functionality while maintaining all the existing information:

```markdown
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
- � Router support for modular API design

## Installation

```bash
pip install bunnyhopapi
```

## Quick Start

```python
from bunnyhopapi.server import Server
from bunnyhopapi.router import Router
from bunnyhopapi.models import PathParam
from pydantic import BaseModel
import asyncio

# Define your models
class HelloResponse(BaseModel):
    message: str

# Create a router
hello_router = Router(prefix="/hello")

# Add routes to the router
@hello_router.route("/world", "GET")
async def hello() -> {200: HelloResponse}:
    return 200, {"message": "Hello, World!"}

@hello_router.route("/<name>", "GET")
async def hello_name(name: PathParam(str)) -> {200: HelloResponse}:
    return 200, {"message": f"Hello, {name}!"}

# Create and configure server
def main():
    server = Server(cors=True)
    server.include_router(hello_router)  # Include the router
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

## Router Usage

Routers allow you to organize your API endpoints modularly:

```python
from bunnyhopapi.router import Router

# Create router with prefix
user_router = Router(prefix="/users")

# Add routes to router (decorator style)
@user_router.route("/", "GET")
async def get_users() -> {200: UserListResponse}:
    return 200, {"users": [...]}

# Or traditional style
user_router.add_route("/<user_id>", "GET", get_user)

# Include router in main server
server.include_router(user_router)
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

### Directly to server
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

### Via Router
```python
router = Router(prefix="/api")
router.add_route("/test", "GET", test_handler)
server.include_router(router)
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

See the example in the Quick Start section or check the full example below:

```python
from bunnyhopapi.server import Server
from bunnyhopapi.router import Router
from bunnyhopapi.models import PathParam
from pydantic import BaseModel
import asyncio

class HelloResponse(BaseModel):
    message: str

class HealthCheckResponse(BaseModel):
    status: str

class Room(BaseModel):
    name: str
    capacity: int

# Create routers
api_router = Router(prefix="/api")
hello_router = Router(prefix="/hello")

# Add routes to routers
@hello_router.route("/world", "GET")
async def hello() -> {200: HelloResponse}:
    return 200, {"message": "Hello, World!"}

@api_router.route("/health", "GET")
async def healthcheck() -> {200: HealthCheckResponse}:
    return 200, {"status": "OK"}

# Create and configure server
def main():
    server = Server(cors=True)
    server.include_router(hello_router)
    server.include_router(api_router)
    server.run()

if __name__ == "__main__":
    main()
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
```