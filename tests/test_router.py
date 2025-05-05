import pytest
from bunnyhopapi.models import RouterBase


class TestRouterDecorators:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.router = RouterBase()

    def test_get_decorator(self):
        @self.router.get("/test-get")
        def handler(headers):
            return 200, {"message": "GET success"}

        assert "/test-get" in self.router.routes
        assert "GET" in self.router.routes["/test-get"]
        assert self.router.routes["/test-get"]["GET"]["handler"] == handler

    def test_post_decorator(self):
        @self.router.post("/test-post")
        def handler(headers):
            return 201, {"message": "POST success"}

        assert "/test-post" in self.router.routes
        assert "POST" in self.router.routes["/test-post"]
        assert self.router.routes["/test-post"]["POST"]["handler"] == handler

    def test_put_decorator(self):
        @self.router.put("/test-put")
        def handler(headers):
            return 200, {"message": "PUT success"}

        assert "/test-put" in self.router.routes
        assert "PUT" in self.router.routes["/test-put"]
        assert self.router.routes["/test-put"]["PUT"]["handler"] == handler

    def test_patch_decorator(self):
        @self.router.patch("/test-patch")
        def handler(headers):
            return 200, {"message": "PATCH success"}

        assert "/test-patch" in self.router.routes
        assert "PATCH" in self.router.routes["/test-patch"]
        assert self.router.routes["/test-patch"]["PATCH"]["handler"] == handler

    def test_delete_decorator(self):
        @self.router.delete("/test-delete")
        def handler(headers):
            return 200, {"message": "DELETE success"}

        assert "/test-delete" in self.router.routes
        assert "DELETE" in self.router.routes["/test-delete"]
        assert self.router.routes["/test-delete"]["DELETE"]["handler"] == handler
