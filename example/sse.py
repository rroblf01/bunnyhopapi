from bunnyhopapi.server import Server
from bunnyhopapi.models import Endpoint
import asyncio
from bunnyhopapi.templates import (
    serve_static_file,
)


class SseEndpoint(Endpoint):
    path = "/sse/events"

    @Endpoint.GET(content_type=Server.CONTENT_TYPE_SSE)
    async def get(self, headers) -> {200: str}:
        events = ["start", "progress", "complete"]
        for event in events:
            yield f"event: {event}\ndata: Processing {event}\n\n"
            await asyncio.sleep(1.5)
        yield "event: end\ndata: Processing complete\n\n"


class SseTemplateEndpoint(Endpoint):
    path = "/sse"

    @Endpoint.GET(content_type=Server.CONTENT_TYPE_HTML)
    async def get(self, headers):
        return await serve_static_file("example/templates/static_html/sse_index.html")


def main():
    server = Server(cors=True)

    server.include_endpoint_class(SseEndpoint)
    server.include_endpoint_class(SseTemplateEndpoint)

    server.run()


if __name__ == "__main__":
    main()
