from bunnyhopapi.server import Server, Router
from bunnyhopapi import logger
from bunnyhopapi.models import Endpoint, PathParam
from pydantic import BaseModel
import os
import asyncio
from bunnyhopapi.templates import (
    render_template,
    serve_static_html,
    create_template_env,
)


class MessageModel(BaseModel):
    message: str


class UserEndpoint(Endpoint):
    path = "/user"

    def get(self, headers) -> {200: MessageModel}:
        return 200, {"message": "GET /user"}

    def get_with_params(self, user_id: PathParam[int], headers) -> {200: MessageModel}:
        return 200, {"message": f"GET /user/{user_id}"}

    def post(self, headers) -> {201: MessageModel}:
        return 201, {"message": "POST /user"}


def main():
    server = Server(cors=True, middleware=None, port=int(os.getenv("PORT", "8000")))

    server.include_endpoint_class(UserEndpoint)
    server.run()


if __name__ == "__main__":
    main()
