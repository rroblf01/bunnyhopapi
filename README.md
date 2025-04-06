# BunnyHopApi

BunnyHopApi is a lightweight and fast web framework designed to handle modern web development needs. It provides full support for:

- **HTTP Requests**: Easily handle all HTTP methods.
- **SSE (Server-Sent Events)**: Support for server-sent events.
- **WebSockets**: Real-time bidirectional communication.
- **Middlewares**: 
  - At the global level.
  - At the route level.
  - At the endpoint level.
- **CORS**: Simple configuration to enable CORS.
- **Web Page Rendering**:
  - Static pages.
  - Dynamic pages with Jinja2.
- **Type Validation**: Automatic validation for query parameters, path parameters, and request bodies.
- **Swagger Documentation**: Automatically generated Swagger documentation for all endpoints.
- **Exceptional Performance**: Designed to be fast and efficient.

## Key Features

### 1. HTTP, SSE, and WebSocket Support
BunnyHopApi allows handling standard HTTP requests, SSE for real-time updates, and WebSockets for bidirectional communication.

#### Example: HTTP Endpoint
```python
class HealthEndpoint(Endpoint):
    path = "/health"

    @Endpoint.GET()
    def get(self, headers):
        return 200, {"message": "GET /health"}
```

#### Example: SSE Endpoint
```python
class SseEndpoint(Endpoint):
    path = "/sse/events"

    @Endpoint.GET(content_type=Router.CONTENT_TYPE_SSE)
    async def get(self, headers) -> {200: str}:
        events = ["start", "progress", "complete"]

        for event in events:
            yield f"event: {event}\ndata: Processing {event}\n\n"
            await asyncio.sleep(1.5)

        yield "event: end\ndata: Processing complete\n\n"
```

#### Example: WebSocket Endpoint
```python
class WSEndpoint(Endpoint):
    path = "/ws/chat"

    async def connection(self, headers):
        logger.info("Client connected")
        logger.info(f"Headers: {headers}")

        return True

    async def disconnect(self, connection_id, headers):
        logger.info(f"Client {connection_id} disconnected")

    async def ws(self, connection_id, message, headers):
        logger.info(f"Received message from {connection_id}: {message}")
        for i in range(10):
            yield f"event: message\ndata: {i}\n\n"
            await asyncio.sleep(0.2)
```

### 2. Flexible Middlewares
Define middlewares at different levels:
- **Global**: Applied to all routes and endpoints.
- **Route-specific**: Applied to a specific set of endpoints.
- **Endpoint-specific**: Applied to an individual endpoint.

#### Example: Global Middleware
```python
async def global_middleware(endpoint, headers, **kwargs):
    logger.info("global_middleware: Before calling the endpoint")
    result = endpoint(headers=headers, **kwargs)
    response = await result if asyncio.iscoroutine(result) else result
    logger.info("global_middleware: After calling the endpoint")
    return response
```

#### Example: Database-Specific Middleware
```python
class UserEndpoint(Endpoint):
    path: str = "/users"

    @Endpoint.MIDDLEWARE()
    def db_middleware(self, endpoint, headers, *args, **kwargs):
        logger.info("db_middleware: Before calling the endpoint")
        db = Database()
        return endpoint(headers=headers, db=db, *args, **kwargs)
```

### 3. CRUD with SQLite
BunnyHopApi makes it easy to implement CRUD operations with support for databases like SQLite.

#### Example: CRUD Operations
```python
class UserEndpoint(Endpoint):
    path: str = "/users"

    @Endpoint.MIDDLEWARE()
    def db_middleware(self, endpoint, headers, *args, **kwargs):
        logger.info("db_middleware: Before calling the endpoint")
        db = Database()
        return endpoint(headers=headers, db=db, *args, **kwargs)

    @Endpoint.GET()
    def get(self, headers, db: Database, *args, **kwargs) -> {200: UserList}:
        users = db.get_users()
        return 200, {"users": users}

    @Endpoint.POST()
    def post(self, user: UserInput, headers, db, *args, **kwargs) -> {201: UserOutput}:
        new_user = db.add_user(user)
        return 201, new_user

    @Endpoint.PUT()
    def put(
        self, db, user_id: PathParam[str], user: UserInput, headers, *args, **kwargs
    ) -> {200: UserOutput, 404: Message}:
        updated_user = db.update_user(user_id, user)

        if updated_user is None:
            return 404, {"message": "User not found"}

        return 200, updated_user

    @Endpoint.DELETE()
    def delete(
        self, db, user_id: PathParam[str], headers, *args, **kwargs
    ) -> {200: Message, 404: Message}:
        if db.delete_user(user_id):
            return 200, {"message": "User deleted"}
        else:
            return 404, {"message": "User not found"}
```

### 4. Swagger Documentation
BunnyHopApi automatically generates Swagger documentation for all endpoints, making it easy to explore and test your API.

#### Example: Access Swagger
Once the server is running, visit `/docs` in your browser to view the Swagger UI.

### 5. Installation

You can install BunnyHopApi directly from PyPI:

```bash
pip install bunnyhopapi
```

### 6. Example Project

Check the [`example/crud.py`](https://github.com/rroblf01/bunnyhopapi/blob/main/example/crud.py) file for an example of how to generate a CRUD using BunnyHopApi.
or
Check the [`example/main.py`](https://github.com/rroblf01/bunnyhopapi/blob/main/example/main.py) file for a complete example of how to use BunnyHopApi.

### 7. License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.