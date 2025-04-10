from bunnyhopapi.server import Server
from bunnyhopapi.models import Endpoint
import os
from bunnyhopapi.templates import (
    render_jinja_template,
    create_template_env,
)


class JinjaTemplateEndpoint(Endpoint):
    path = "/"

    def __init__(self):
        super().__init__()
        self.template_env = create_template_env("example/templates/jinja/")

    @Endpoint.GET(content_type=Server.CONTENT_TYPE_HTML)
    async def get(self, headers):
        return await render_jinja_template("index.html", self.template_env)


def main():
    server = Server(cors=True)

    static_folder = os.path.join(os.path.dirname(__file__), "static")
    server.include_static_folder(static_folder)

    server.include_endpoint_class(JinjaTemplateEndpoint)
    server.run()


if __name__ == "__main__":
    main()
