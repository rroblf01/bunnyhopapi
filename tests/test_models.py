import pytest
from bunnyhopapi.models import PathParam, QueryParam, Endpoint
from bunnyhopapi.server import Router
import re
import asyncio
from unittest.mock import patch
from bunnyhopapi import logger


class TestPathParam:
    def test_validate_valid_value(self):
        param = PathParam(int)
        assert param.validate("123") == 123

    def test_validate_invalid_value(self):
        param = PathParam(int)
        with pytest.raises(
            ValueError, match="Invalid value for type <class 'int'>: abc"
        ):
            param.validate("abc")


class TestQueryParam:
    def test_validate_valid_value(self):
        param = QueryParam(str)
        assert param.validate("test") == "test"

    def test_validate_invalid_value(self):
        param = QueryParam(int)
        with pytest.raises(
            ValueError, match="Invalid value for type <class 'int'>: test"
        ):
            param.validate("test")


class TestRouter:
    def test_compile_route_pattern(self):
        router = Router()
        pattern = router._compile_route_pattern("/test/<id>")
        assert isinstance(pattern, re.Pattern)
        assert pattern.match("/test/123")
        assert not pattern.match("/test/abc/extra")

    def test_add_route(self):
        router = Router()
        handler = lambda: None
        router.add_route("/test", "GET", handler)
        assert "/test" in router.routes
        assert "GET" in router.routes["/test"]
        assert router.routes["/test"]["GET"]["handler"] == handler

    def test_add_websocket_route(self):
        router = Router()
        handler = lambda: None
        router.add_websocket_route("/ws", handler)
        assert "/ws" in router.websocket_handlers
        assert router.websocket_handlers["/ws"]["handler"] == handler

    def test_add_websocket_route_with_class_and_method_middleware(self):
        async def class_middleware(endpoint, *args, **kwargs):
            return await endpoint(*args, **kwargs)

        async def method_middleware(endpoint, *args, **kwargs):
            yield await endpoint(*args, **kwargs)

        async def handler(*args, **kwargs):
            return "handler executed"

        router = Router(middleware=class_middleware)
        router.add_websocket_route("/ws", handler, middleware=method_middleware)

        assert "/ws" in router.websocket_handlers
        assert router.websocket_handlers["/ws"]["middleware"] is not None

        combined_middleware = router.websocket_handlers["/ws"]["middleware"]
        assert callable(combined_middleware)

    def test_add_websocket_route_with_class_middleware(self):
        async def class_middleware(endpoint, *args, **kwargs):
            yield await endpoint(*args, **kwargs)

        async def handler(*args, **kwargs):
            return "handler executed"

        router = Router(middleware=class_middleware)
        router.add_websocket_route("/ws", handler)

        assert "/ws" in router.websocket_handlers
        assert callable(router.websocket_handlers["/ws"]["middleware"])
        assert router.websocket_handlers["/ws"]["middleware"].func == class_middleware

    def test_add_websocket_route_with_method_middleware(self):
        async def method_middleware(endpoint, *args, **kwargs):
            yield await endpoint(*args, **kwargs)

        async def handler(*args, **kwargs):
            return "handler executed"

        router = Router()
        router.add_websocket_route("/ws", handler, middleware=method_middleware)

        assert "/ws" in router.websocket_handlers
        assert callable(router.websocket_handlers["/ws"]["middleware"])
        assert router.websocket_handlers["/ws"]["middleware"].func == method_middleware

    def test_include_endpoint_class_with_ws_endpoint(self):
        router = Router()
        router.include_endpoint_class(WSEndpoint)

        assert "/ws/chat" in router.websocket_handlers
        ws_handler = router.websocket_handlers["/ws/chat"]

        assert "handler" in ws_handler
        assert callable(ws_handler["handler"])

        assert "connection" in ws_handler
        assert callable(ws_handler["connection"])

        assert "disconnect" in ws_handler
        assert callable(ws_handler["disconnect"])

        assert "middleware" in ws_handler
        assert callable(ws_handler["middleware"])


class WSEndpoint(Endpoint):
    path = "/ws/chat"

    @Endpoint.MIDDLEWARE()
    async def ws_middleware(self, endpoint, headers, **kwargs):
        logger.info("middleware: Before to call the endpoint")
        yield await endpoint(headers=headers, **kwargs)
        logger.info("middleware: After to call the endpoint")

    async def connection(self, headers):
        logger.info("Client connected")
        return True

    async def disconnect(self, connection_id, headers):
        logger.info(f"Client {connection_id} disconnected")

    async def ws(self, connection_id, message, headers):
        logger.info(f"Received message from {connection_id}: {message}")
        for i in range(10):
            yield f"event: message\ndata: {i}\n\n"
            await asyncio.sleep(0.2)


class TestEndpoint:
    class MockEndpoint(Endpoint):
        path = "/mock"

        @Endpoint.GET()
        def get(self):
            return 200, {"message": "GET /mock"}

        @Endpoint.POST()
        def post(self):
            return 201, {"message": "POST /mock"}

        @Endpoint.PUT()
        def put(self):
            return 200, {"message": "PUT /mock"}

        @Endpoint.DELETE()
        def delete(self):
            return 200, {"message": "DELETE /mock"}

        @Endpoint.PATCH()
        def patch(self):
            return 200, {"message": "PATCH /mock"}

    def test_all_routes(self):
        endpoint = self.MockEndpoint()
        routes = endpoint.get_routes()
        assert "/mock" in routes
        assert "GET" in routes["/mock"]
        assert "POST" in routes["/mock"]
        assert "PUT" in routes["/mock"]
        assert "DELETE" in routes["/mock"]
        assert "PATCH" in routes["/mock"]

    def test_get_routes(self):
        endpoint = self.MockEndpoint()
        routes = endpoint.get_routes()
        assert "/mock" in routes
        assert "GET" in routes["/mock"]
        assert callable(routes["/mock"]["GET"]["handler"])

    def test_post_routes(self):
        endpoint = self.MockEndpoint()
        routes = endpoint.get_routes()
        assert "/mock" in routes
        assert "POST" in routes["/mock"]
        assert callable(routes["/mock"]["POST"]["handler"])

    def test_put_routes(self):
        endpoint = self.MockEndpoint()
        routes = endpoint.get_routes()
        assert "/mock" in routes
        assert "PUT" in routes["/mock"]
        assert callable(routes["/mock"]["PUT"]["handler"])

    def test_delete_routes(self):
        endpoint = self.MockEndpoint()
        routes = endpoint.get_routes()
        assert "/mock" in routes
        assert "DELETE" in routes["/mock"]
        assert callable(routes["/mock"]["DELETE"]["handler"])

    def test_patch_routes(self):
        endpoint = self.MockEndpoint()
        routes = endpoint.get_routes()
        assert "/mock" in routes
        assert "PATCH" in routes["/mock"]
        assert callable(routes["/mock"]["PATCH"]["handler"])

    class MockWsEndpoint(Endpoint):
        path = "/ws"

        async def connection(self, headers):
            return True

        async def disconnect(self, connection_id, headers):
            pass

        async def ws(self, connection_id, message, headers):
            return f"Echo: {message}"

    def test_get_ws_routes(self):
        endpoint = self.MockWsEndpoint()
        ws_routes = endpoint.get_ws_routes()
        assert "/ws" in ws_routes
        assert "handler" in ws_routes["/ws"]
        assert callable(ws_routes["/ws"]["handler"])
        assert "connection" in ws_routes["/ws"]
        assert callable(ws_routes["/ws"]["connection"])
        assert "disconnect" in ws_routes["/ws"]
        assert callable(ws_routes["/ws"]["disconnect"])


class TestBaseEndpoint:
    def test_middleware_decorator(self):
        class MockEndpoint(Endpoint):
            @Endpoint.MIDDLEWARE()
            def custom_middleware(cls, *args, **kwargs):
                return "middleware executed"

        endpoint = MockEndpoint()
        endpoint.get_routes()
        assert endpoint.middleware is not None
        assert endpoint.middleware() == "middleware executed"
