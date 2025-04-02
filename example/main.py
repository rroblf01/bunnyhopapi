from bunnyhopapi.server import Server, Router
from bunnyhopapi import logger
from bunnyhopapi.models import Endpoint, PathParam, QueryParam
from pydantic import BaseModel
import os
import asyncio
from bunnyhopapi.templates import (
    render_jinja_template,
    serve_static_html,
    create_template_env,
)


class MessageModel(BaseModel):
    message: str


class BodyModel(BaseModel):
    name: str
    age: int


class HealthEndpoint(Endpoint):
    path = "/health"

    def get(self, headers):
        return 200, {"message": "GET /health"}


class UserEndpoint(Endpoint):
    path = "/user"

    def get(
        self, headers, age: QueryParam[int], name: QueryParam[str] = "Alice"
    ) -> {200: MessageModel}:
        return 200, {"message": f"GET /user/ pathparams: age {age}, name {name}"}

    def get_with_params(self, user_id: PathParam[int], headers) -> {200: MessageModel}:
        """
        Obtiene un usuario por ID.
        """
        logger.info(f"header: {headers}")
        return 200, {"message": f"GET /user/{user_id}"}

    def post(self, headers, body: BodyModel) -> {201: MessageModel}:
        return 201, {"message": f"POST /user/ - {body.name} - {body.age}"}


class SseEndpoint(Endpoint):
    path = "/sse/events"

    @Endpoint.with_content_type(Router.CONTENT_TYPE_SSE)
    async def get(self, headers) -> {200: str}:
        events = ["start", "progress", "complete"]
        for event in events:
            yield f"event: {event}\ndata: Processing {event}\n\n"
            await asyncio.sleep(1.5)
        yield "event: end\ndata: Processing complete\n\n"


class SseTemplateEndpoint(Endpoint):
    path = "/sse"

    @Endpoint.with_content_type(Router.CONTENT_TYPE_HTML)
    async def get(self, headers):
        return await serve_static_html("example/templates/static_html/sse_index.html")


class WSEndpoint(Endpoint):
    path = "/ws/chat"

    async def connection(self, headers):
        logger.info("Client connected")
        logger.info(f"Headers: {headers}")

        return False

    async def disconnect(self, connection_id, headers):
        logger.info(f"Client {connection_id} disconnected")

    async def ws(self, connection_id, message, headers):
        logger.info(f"Received message from {connection_id}: {message}")
        for i in range(10):
            yield f"event: message\ndata: {i}\n\n"
            await asyncio.sleep(0.2)


class WSTemplateEndpoint(Endpoint):
    path = "/ws"

    @Endpoint.with_content_type(Router.CONTENT_TYPE_HTML)
    async def get(self, headers):
        return await serve_static_html("example/templates/static_html/ws_index.html")


class JinjaTemplateEndpoint(Endpoint):
    path = "/"

    def __init__(self):
        super().__init__()
        self.template_env = create_template_env("example/templates/jinja/")

    @Endpoint.with_content_type(Router.CONTENT_TYPE_HTML)
    async def get(self, headers):
        return await render_jinja_template("index.html", self.template_env)


def main():
    server = Server(cors=True, middleware=None, port=int(os.getenv("PORT", "8000")))

    user_router = Router()
    user_router.include_endpoint_class(UserEndpoint)

    server.include_router(user_router)
    server.include_endpoint_class(SseEndpoint)
    server.include_endpoint_class(SseTemplateEndpoint)
    server.include_endpoint_class(WSEndpoint)
    server.include_endpoint_class(WSTemplateEndpoint)
    server.include_endpoint_class(JinjaTemplateEndpoint)
    server.include_endpoint_class(HealthEndpoint)
    server.run()


if __name__ == "__main__":
    main()
