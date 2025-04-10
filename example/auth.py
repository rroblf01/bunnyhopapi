from bunnyhopapi.server import Server, Router
from bunnyhopapi.models import Endpoint
import logging

logger = logging.getLogger(__name__)


class AuthEndpoint(Endpoint):
    path = "/auth"

    @Endpoint.GET()
    def get(self, headers):
        return 200, {"message": "GET /auth"}


def auth_middleware(headers, endpoint, *args, **kwargs):
    logger.info("auth_middleware: Before to call the endpoint")
    if "Authorization" not in headers:
        return 401, {"message": "Unauthorized"}
    logger.info("auth_middleware: After to call the endpoint")
    return endpoint(headers=headers, *args, **kwargs)


if __name__ == "__main__":
    server = Server()

    auth_router = Router(middleware=auth_middleware)
    auth_router.include_endpoint_class(AuthEndpoint)
    server.include_router(auth_router)
    server.run()
