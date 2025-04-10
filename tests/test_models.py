import pytest
from bunnyhopapi.models import PathParam, QueryParam, Endpoint, RouterBase
import re
import asyncio
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
        router = RouterBase()
        pattern = router._compile_route_pattern("/test/<id>")
        assert isinstance(pattern, re.Pattern)
        assert pattern.match("/test/123")
        assert not pattern.match("/test/abc/extra")

    def test_add_route(self):
        router = RouterBase()
        handler = lambda: None
        router.add_route("/test", "GET", handler)
        assert "/test" in router.routes
        assert "GET" in router.routes["/test"]
        assert router.routes["/test"]["GET"]["handler"] == handler

    def test_add_route_with_path_params(self):
        router = RouterBase()
        handler = lambda: None
        router.add_route("/test/<id>", "GET", handler)
        assert "/test/<id>" in router.routes_with_params
        assert isinstance(router.routes_with_params["/test/<id>"], re.Pattern)

    def test_add_route_with_both_middlewares(self):
        async def class_middleware(endpoint, *args, **kwargs):
            return await endpoint(*args, **kwargs)

        async def method_middleware(endpoint, *args, **kwargs):
            return await endpoint(*args, **kwargs)

        async def handler(*args, **kwargs):
            return "handler executed"

        router = RouterBase(middleware=class_middleware)
        router.add_route("/test", "GET", handler, middleware=method_middleware)

        assert "/test" in router.routes
        assert "GET" in router.routes["/test"]
        assert callable(router.routes["/test"]["GET"]["middleware"])

    def test_add_route_with_method_middleware(self):
        async def method_middleware(endpoint, *args, **kwargs):
            return await endpoint(*args, **kwargs)

        async def handler(*args, **kwargs):
            return "handler executed"

        router = RouterBase()
        router.add_route("/test", "GET", handler, middleware=method_middleware)

        assert "/test" in router.routes
        assert "GET" in router.routes["/test"]
        assert callable(router.routes["/test"]["GET"]["middleware"])

    def test_add_route_with_class_middleware(self):
        async def class_middleware(endpoint, *args, **kwargs):
            return await endpoint(*args, **kwargs)

        async def handler(*args, **kwargs):
            return "handler executed"

        router = RouterBase(middleware=class_middleware)
        router.add_route("/test", "GET", handler)

        assert "/test" in router.routes
        assert "GET" in router.routes["/test"]
        assert callable(router.routes["/test"]["GET"]["middleware"])

    def test_add_websocket_route(self):
        router = RouterBase()
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

        router = RouterBase(middleware=class_middleware)
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

        router = RouterBase(middleware=class_middleware)
        router.add_websocket_route("/ws", handler)

        assert "/ws" in router.websocket_handlers
        assert callable(router.websocket_handlers["/ws"]["middleware"])
        assert router.websocket_handlers["/ws"]["middleware"].func == class_middleware

    def test_add_websocket_route_with_method_middleware(self):
        async def method_middleware(endpoint, *args, **kwargs):
            yield await endpoint(*args, **kwargs)

        async def handler(*args, **kwargs):
            return "handler executed"

        router = RouterBase()
        router.add_websocket_route("/ws", handler, middleware=method_middleware)

        assert "/ws" in router.websocket_handlers
        assert callable(router.websocket_handlers["/ws"]["middleware"])
        assert router.websocket_handlers["/ws"]["middleware"].func == method_middleware

    def test_add_websocket_route_with_both_middlewares(self):
        async def class_middleware(endpoint, *args, **kwargs):
            yield await endpoint(*args, **kwargs)

        async def method_middleware(endpoint, *args, **kwargs):
            yield await endpoint(*args, **kwargs)

        async def handler(*args, **kwargs):
            return "handler executed"

        router = RouterBase(middleware=class_middleware)
        router.add_websocket_route("/ws", handler, middleware=method_middleware)

        assert "/ws" in router.websocket_handlers
        assert router.websocket_handlers["/ws"]["middleware"] is not None

        combined_middleware = router.websocket_handlers["/ws"]["middleware"]
        assert callable(combined_middleware)
        assert combined_middleware.func == class_middleware

    def test_include_endpoint_class_with_ws_endpoint(self):
        router = RouterBase()
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

    def test_include_router(self):
        router1 = RouterBase()
        router2 = RouterBase()

        handler1 = lambda: None
        handler2 = lambda: None

        router1.add_route("/test1", "GET", handler1)
        router2.add_route("/test2", "POST", handler2)

        router1.include_router(router2)

        assert "/test1" in router1.routes
        assert "GET" in router1.routes["/test1"]
        assert router1.routes["/test1"]["GET"]["handler"] == handler1

        assert "/test2" in router1.routes
        assert "POST" in router1.routes["/test2"]
        assert router1.routes["/test2"]["POST"]["handler"] == handler2

    def test_include_router_with_prefix(self):
        router1 = RouterBase(prefix="/api")
        router2 = RouterBase()

        handler = lambda: None
        router2.add_route("/test", "GET", handler)

        router1.include_router(router2)

        assert "/api/test" in router1.routes
        assert "GET" in router1.routes["/api/test"]
        assert router1.routes["/api/test"]["GET"]["handler"] == handler

    def test_include_router_with_path_params(self):
        router1 = RouterBase()
        router2 = RouterBase()

        handler = lambda: None
        router2.add_route("/test/<id>", "GET", handler)

        router1.include_router(router2)

        assert "/test/<id>" in router1.routes_with_params
        assert isinstance(router1.routes_with_params["/test/<id>"], re.Pattern)

    def test_include_router_with_both_middlewares(self):
        async def class_middleware(endpoint, *args, **kwargs):
            return await endpoint(*args, **kwargs)

        async def method_middleware(endpoint, *args, **kwargs):
            return await endpoint(*args, **kwargs)

        async def handler(*args, **kwargs):
            return "handler executed"

        router1 = RouterBase(middleware=class_middleware)
        router2 = RouterBase()
        router2.add_route("/test", "GET", handler, middleware=method_middleware)

        router1.include_router(router2)

        assert "/test" in router1.routes
        assert "GET" in router1.routes["/test"]
        assert callable(router1.routes["/test"]["GET"]["middleware"])

    def test_include_router_with_class_middleware(self):
        async def class_middleware(endpoint, *args, **kwargs):
            return await endpoint(*args, **kwargs)

        async def handler(*args, **kwargs):
            return "handler executed"

        router1 = RouterBase(middleware=class_middleware)
        router2 = RouterBase()
        router2.add_route("/test", "GET", handler)

        router1.include_router(router2)

        assert "/test" in router1.routes
        assert "GET" in router1.routes["/test"]
        assert callable(router1.routes["/test"]["GET"]["middleware"])

    def test_include_router_with_only_class_middleware(self):
        async def class_middleware(endpoint, *args, **kwargs):
            return await endpoint(*args, **kwargs)

        async def handler(*args, **kwargs):
            return "handler executed"

        router1 = RouterBase(middleware=class_middleware)
        router2 = RouterBase()
        router2.add_route("/test", "GET", handler)

        router1.include_router(router2)

        assert "/test" in router1.routes
        assert "GET" in router1.routes["/test"]
        assert callable(router1.routes["/test"]["GET"]["middleware"])

    def test_include_router_with_only_method_middleware(self):
        async def method_middleware(endpoint, *args, **kwargs):
            return await endpoint(*args, **kwargs)

        async def handler(*args, **kwargs):
            return "handler executed"

        router1 = RouterBase()
        router2 = RouterBase()
        router2.add_route("/test", "GET", handler, middleware=method_middleware)

        router1.include_router(router2)

        assert "/test" in router1.routes
        assert "GET" in router1.routes["/test"]
        assert callable(router1.routes["/test"]["GET"]["middleware"])

    def test_include_endpoint_class_with_add_route(self):
        class MockEndpoint(Endpoint):
            path = "/mock"

            @Endpoint.GET()
            def get(self):
                return 200, {"message": "GET /mock"}

        router = RouterBase()
        router.include_endpoint_class(MockEndpoint)

        assert "/mock" in router.routes
        assert "GET" in router.routes["/mock"]
        assert callable(router.routes["/mock"]["GET"]["handler"])


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

    def test_get_routes_with_annotations(self):
        class MockEndpointWithAnnotations(Endpoint):
            path = "/annotated"

            @Endpoint.GET()
            def get(self, param: PathParam[int]):
                return 200, {"message": f"GET /annotated with param {param}"}

        endpoint = MockEndpointWithAnnotations()
        routes = endpoint.get_routes()
        assert "/annotated/<param>" in routes
        assert "GET" in routes["/annotated/<param>"]
        assert callable(routes["/annotated/<param>"]["GET"]["handler"])

    def test_get_routes_without_param_names(self):
        class MockEndpointWithoutParams(Endpoint):
            path = "/noparams"

            @Endpoint.GET()
            def get(self):
                return 200, {"message": "GET /noparams"}

        endpoint = MockEndpointWithoutParams()
        routes = endpoint.get_routes()
        assert "/noparams" in routes
        assert "GET" in routes["/noparams"]
        assert callable(routes["/noparams"]["GET"]["handler"])
        assert routes["/noparams"]["GET"]["handler"]() == (
            200,
            {"message": "GET /noparams"},
        )

    def test_get_routes_with_param_names(self):
        class MockEndpointWithParams(Endpoint):
            path = "/params"

            @Endpoint.GET()
            def get(self, db: str):
                return 200, {"message": "GET /params without param"}

        endpoint = MockEndpointWithParams()
        routes = endpoint.get_routes()
        assert "/params" in routes
        assert "GET" in routes["/params"]
        assert callable(routes["/params"]["GET"]["handler"])

    def test_get_routes_with_both_middlewares(self):
        class MockEndpointWithMiddlewares(Endpoint):
            path = "/middlewares"

            @Endpoint.MIDDLEWARE()
            async def class_middleware(self, endpoint, *args, **kwargs):
                return await endpoint(*args, **kwargs)

            @Endpoint.GET(
                middleware=lambda endpoint, *args, **kwargs: endpoint(*args, **kwargs)
            )
            def get(self):
                return 200, {"message": "GET /middlewares"}

        endpoint = MockEndpointWithMiddlewares()
        routes = endpoint.get_routes()
        assert "/middlewares" in routes
        assert "GET" in routes["/middlewares"]
        assert callable(routes["/middlewares"]["GET"]["middleware"])

    def test_get_routes_with_class_middleware(self):
        class MockEndpointWithClassMiddleware(Endpoint):
            path = "/classmiddleware"

            @Endpoint.MIDDLEWARE()
            async def class_middleware(self, endpoint, *args, **kwargs):
                return await endpoint(*args, **kwargs)

            @Endpoint.GET()
            def get(self):
                return 200, {"message": "GET /classmiddleware"}

        endpoint = MockEndpointWithClassMiddleware()
        routes = endpoint.get_routes()
        assert "/classmiddleware" in routes
        assert "GET" in routes["/classmiddleware"]
        assert callable(routes["/classmiddleware"]["GET"]["middleware"])

    def test_get_routes_with_method_middleware(self):
        class MockEndpointWithMethodMiddleware(Endpoint):
            path = "/methodmiddleware"

            @Endpoint.GET(
                middleware=lambda endpoint, *args, **kwargs: endpoint(*args, **kwargs)
            )
            def get(self):
                return 200, {"message": "GET /methodmiddleware"}

        endpoint = MockEndpointWithMethodMiddleware()
        routes = endpoint.get_routes()
        assert "/methodmiddleware" in routes
        assert "GET" in routes["/methodmiddleware"]
        assert callable(routes["/methodmiddleware"]["GET"]["middleware"])


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
