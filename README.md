# BunnyHopApi

BunnyHopApi is a lightweight and fast web framework designed to handle modern web development needs. It provides full support for:

- **HTTP Requests**: Easily handle all HTTP methods.
- **SSE (Server-Sent Events)**: Support for server-sent events.
- **WebSockets**: Real-time bidirectional communication.
- **Middlewares**: 
  - At the server level.
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

    def get(self, headers):
        return 200, {"message": "GET /health"}
```

#### Example: SSE Endpoint
```python
class SseEndpoint(Endpoint):
    path = "/sse/events"

    @Endpoint.with_content_type(Router.CONTENT_TYPE_SSE)
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

#### Example: Middleware
```python
async def global_middleware(endpoint, headers, **kwargs):
    logger.info("global_middleware: Before calling the endpoint")
    response = await endpoint(headers=headers, **kwargs)
    logger.info("global_middleware: After calling the endpoint")
    return response
```

### 3. Type Validation
BunnyHopApi provides automatic type validation for query parameters, path parameters, and request bodies using Pydantic models.

#### Example: Query Parameters
```python
class UserEndpoint(Endpoint):
    path = "/user"

    def get(
        self, headers, age: QueryParam[int], name: QueryParam[str] = "Alice"
    ) -> {200: MessageModel}:
        return 200, {"message": f"GET /user/ pathparams: age {age}, name {name}"}
```

#### Example: Path Parameters
```python
    def get_with_params(self, user_id: PathParam[int], headers) -> {200: MessageModel}:
        return 200, {"message": f"GET /user/{user_id}"}
```

#### Example: Request Body
```python
class BodyModel(BaseModel):
    name: str
    age: int

    def post(self, headers, body: BodyModel) -> {201: MessageModel}:
        return 201, {"message": f"POST /user/ - {body.name} - {body.age}"}
```

### 4. Swagger Documentation
BunnyHopApi automatically generates Swagger documentation for all endpoints, making it easy to explore and test your API.

#### Example: Access Swagger
Once the server is running, visit `/docs` in your browser to view the Swagger UI.

### 5. Web Page Rendering
- **Static Pages**: Serve HTML files directly.
- **Dynamic Pages**: Use Jinja2 for dynamic template rendering.

#### Example: Static Page
```python
class SseTemplateEndpoint(Endpoint):
    path = "/sse"

    @Endpoint.with_content_type(Router.CONTENT_TYPE_HTML)
    async def get(self, headers):
        return await serve_static_html("example/templates/static_html/sse_index.html")
```

#### Example: Dynamic Page
```python
class JinjaTemplateEndpoint(Endpoint):
    path = "/"

    def __init__(self):
        super().__init__()
        self.template_env = create_template_env("example/templates/jinja/")

    @Endpoint.with_content_type(Router.CONTENT_TYPE_HTML)
    async def get(self, headers):
        return await render_jinja_template("index.html", self.template_env)
```

### 6. Performance
BunnyHopApi is extremely fast. Here's a benchmark that demonstrates its performance:

```bash
wrk -t12 -c400 -d30s --timeout 1m http://127.0.0.1:8000/health
```

**Results:**
```
Running 30s test @ http://127.0.0.1:8000/health
  12 threads and 400 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency    87.17ms  660.53ms  13.33s    97.86%
    Req/Sec     0.91k   526.28     2.51k    63.28%
  325639 requests in 30.08s, 74.22MB read
  Socket errors: connect 0, read 62, write 0, timeout 0
Requests/sec:  10824.54
Transfer/sec:      2.47MB
```

## Installation

You can install BunnyHopApi directly from PyPI:

```bash
pip install bunnyhopapi
```

## Usage

1. Create a new Python file and import BunnyHopApi:
   ```python
   from bunnyhopapi.server import Server
   from bunnyhopapi.models import Endpoint
   ```

2. Define your endpoints and middlewares.

    ```python
    class HealthEndpoint(Endpoint):
        path = "/health"

        def get(self, headers):
            return 200, {"message": "GET /health"}
    ```

3. Start the server:
   ```python
   server = Server(cors=True, middleware=global_middleware, port=8000)
   server.include_endpoint_class(HealthEndpoint)
   server.run()
   ```

## Example Project

Check the [`example/main.py`](example/main.py) file for a complete example of how to use BunnyHopApi.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.