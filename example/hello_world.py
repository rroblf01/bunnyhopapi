from bunnyhopapi.server import Server, Router
from bunnyhopapi.models import PathParam
from pydantic import BaseModel


class HelloWorldResponse(BaseModel):
    message: str


router = Router(prefix="/api/v1")


@router.get("/hello")
def hello_world(headers):
    return 200, {"message": "Hello, World!"}


@router.post("/goodbye")
def goodbye_world(headers) -> {200: HelloWorldResponse}:
    return 200, {"message": "Goodbye, World!"}


def middleware(headers, endpoint, *args, **kwargs):
    headers["X-Custom-Header"] = "CustomValue"
    return endpoint(headers=headers, *args, **kwargs)


@router.get("/hello/<name>", middleware=middleware)
def hello_world_with_params(name: PathParam[str], headers):
    return 200, {"message": f"Hello, {name}!"}


if __name__ == "__main__":
    server = Server(auto_reload=True)
    server.include_router(router)
    server.run(workers=1)
