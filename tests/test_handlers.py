import pytest
from unittest.mock import Mock
from bunnyhopapi.handlers import RouteHandler
from bunnyhopapi.models import PathParam
from pydantic import BaseModel
import inspect


class TestRouteHandler:
    @pytest.fixture
    def route_handler(self):
        return RouteHandler()

    @pytest.mark.asyncio
    async def test_execute_handler_route_not_found(self, route_handler):
        route_handler._find_route = Mock(return_value=None)
        response = await route_handler.execute_handler("/invalid", "GET")
        assert response == (
            "application/json",
            404,
            {"error": "Route GET /invalid not found"},
        )

    @pytest.mark.asyncio
    async def test_execute_handler_success(self, route_handler):
        async def mock_handler(headers, **kwargs):
            return 200, {"message": "Success"}

        route_handler._find_route = Mock(
            return_value=(
                {"handler": mock_handler, "content_type": "application/json"},
                {},
            )
        )
        response = await route_handler.execute_handler("/valid", "GET", query_params={})
        assert response["status_code"] == 200
        assert response["response_data"] == {"message": "Success"}

    def test_find_route_exact_match(self, route_handler):
        route_handler.routes = {"/test": {"GET": {"handler": Mock()}}}
        route, params = route_handler._find_route("/test", "GET")
        assert route is not None
        assert params == {}

    def test_find_route_method_not_in_methods(self, route_handler):
        route_handler.routes = {"/test": {"POST": {"handler": Mock()}}}
        result = route_handler._find_route("/test", "GET")
        assert result is None

    def test_find_route_with_params(self, route_handler):
        route_handler.routes = {"/test/<id>": {"GET": {"handler": Mock()}}}
        route_handler.routes_with_params = {"/test/<id>": Mock()}
        route_handler._extract_params = Mock(return_value={"id": "123"})
        route, params = route_handler._find_route("/test/123", "GET")
        assert route is not None
        assert params == {"id": "123"}

    def test_find_route_no_match(self, route_handler):
        route_handler.routes = {"/test/<id>": {"GET": {"handler": Mock()}}}
        route_handler.routes_with_params = {"/test/<id>": Mock()}
        route_handler._extract_params = Mock(return_value=None)
        result = route_handler._find_route("/test/abc", "GET")
        assert result is None

    def test_find_route_with_params_found(self, route_handler):
        route_handler.routes = {"/test/<id>": {"GET": {"handler": Mock()}}}
        route_handler.routes_with_params = {"/test/<id>": Mock()}
        route_handler._extract_params = Mock(return_value={"id": "123"})

        route, params = route_handler._find_route("/test/123", "GET")
        assert route is not None
        assert params == {"id": "123"}

    def test_validate_params_success(self, route_handler):
        type_hints = {"id": PathParam[int]}
        params = {"id": "123"}
        validated = route_handler._validate_params(params, type_hints, {})
        assert validated["id"] == 123

    def test_validate_params_invalid(self, route_handler):
        type_hints = {"id": PathParam[int]}
        params = {"id": "abc"}
        with pytest.raises(ValueError):
            route_handler._validate_params(params, type_hints, {})

    def test_validate_params_param_not_in_type_hints(self, route_handler):
        type_hints = {"id": PathParam[int]}
        params = {"name": "test"}
        validated = route_handler._validate_params(params, type_hints, {})
        assert "name" not in validated

    def test_validate_params_assign_param_value(self, route_handler):
        type_hints = {"id": PathParam[int], "name": str}
        params = {"name": "test"}
        validated = route_handler._validate_params(params, type_hints, {})
        assert validated["name"] == "test"

    def test_validate_body_success(self, route_handler):
        class BodyModel(BaseModel):
            name: str

        type_hints = {"body": BodyModel}
        body = '{"name": "test"}'
        result = route_handler._validate_body(body, type_hints)
        assert result["status_code"] == 200
        assert result["validated_params"]["body"].name == "test"

    def test_validate_body_invalid_json(self, route_handler):
        class BodyModel(BaseModel):
            name: str

        type_hints = {"body": BodyModel}
        body = '{"name": "test"'
        result = route_handler._validate_body(body, type_hints)
        assert result["status_code"] == 400
        assert "Invalid JSON format" in result["error"]["error"]

    def test_validate_body_validation_error(self, route_handler):
        class BodyModel(BaseModel):
            name: str

        type_hints = {"body": BodyModel}
        body = '{"age": 30}'
        result = route_handler._validate_body(body, type_hints)
        assert result["status_code"] == 422
        assert "Validation error" in result["error"]["error"]

    def test_extract_params_route_not_in_routes_with_params(self, route_handler):
        route_handler.routes_with_params = {}
        result = route_handler._extract_params("/test/123", "/test/<id>")
        assert result is None

    def test_extract_params_no_match(self, route_handler):
        mock_pattern = Mock()
        mock_pattern.match.return_value = None
        route_handler.routes_with_params = {"/test/<id>": mock_pattern}
        result = route_handler._extract_params("/test/abc", "/test/<id>")
        assert result is None

    def test_extract_params_match(self, route_handler):
        mock_match = Mock()
        mock_match.groupdict.return_value = {"id": "123"}
        mock_pattern = Mock()
        mock_pattern.match.return_value = mock_match
        route_handler.routes_with_params = {"/test/<id>": mock_pattern}
        result = route_handler._extract_params("/test/123", "/test/<id>")
        assert result == {"id": "123"}

    @pytest.mark.asyncio
    async def test_process_handler_validation_error(self, route_handler):
        async def mock_handler(headers, **kwargs):
            return 200, {"message": "Success"}

        route_info = {
            "handler": mock_handler,
            "content_type": "application/json",
            "params": {"id": "invalid"},
        }

        route_handler._validate_params = Mock(
            side_effect=ValueError("Invalid parameter")
        )

        response = await route_handler._process_handler(
            route_info, "/test/123", "GET", headers={}
        )

        assert response["content_type"] == "application/json"
        assert response["status_code"] == 422
        assert response["response_data"] == {"error": "Invalid parameter"}

    @pytest.mark.asyncio
    async def test_process_handler_body_validation_error(self, route_handler):
        async def mock_handler(headers, **kwargs):
            return 200, {"message": "Success"}

        route_info = {
            "handler": mock_handler,
            "content_type": "application/json",
        }

        route_handler._validate_body = Mock(
            return_value={
                "status_code": 400,
                "error": {"error": "Invalid JSON format"},
                "validated_params": {},
            }
        )

        response = await route_handler._process_handler(
            route_info, "/test", "POST", body="invalid_json", headers={}
        )

        assert response["content_type"] == "application/json"
        assert response["status_code"] == 400
        assert response["response_data"] == {"error": "Invalid JSON format"}

    @pytest.mark.asyncio
    async def test_process_handler_body_validation_success(self, route_handler):
        async def mock_handler(headers, **kwargs):
            return 200, {"message": "Success"}

        route_info = {
            "handler": mock_handler,
            "content_type": "application/json",
        }

        route_handler._validate_body = Mock(
            return_value={
                "status_code": 200,
                "error": None,
                "validated_params": {"body": {"key": "value"}},
            }
        )

        route_handler._validate_params = Mock(return_value={})

        response = await route_handler._process_handler(
            route_info, "/test", "POST", body='{"key": "value"}', headers={}
        )

        assert response["content_type"] == "application/json"
        assert response["status_code"] == 200
        assert response["response_data"] == {"message": "Success"}

    @pytest.mark.asyncio
    async def test_process_handler_async_generator(self, route_handler):
        async def mock_handler(headers, **kwargs):
            yield "data"

        route_info = {
            "handler": mock_handler,
            "content_type": "text/event-stream",
        }

        route_handler._validate_params = Mock(return_value={})

        response = await route_handler._process_handler(
            route_info, "/test", "GET", headers={}
        )

        assert response["content_type"] == "text/event-stream"
        assert response["status_code"] == 200
        assert inspect.isasyncgen(response["response_data"])

    @pytest.mark.asyncio
    async def test_process_handler_invalid_response_tuple(self, route_handler):
        async def mock_handler(headers, **kwargs):
            return 200  # Invalid response, not a tuple

        route_info = {
            "handler": mock_handler,
            "content_type": "application/json",
        }

        response = await route_handler._process_handler(
            route_info, "/test", "GET", headers={}
        )

        assert response["content_type"] == "application/json"
        assert response["status_code"] == 500
        assert response["response_data"]["error"] == "Internal server error"
        assert (
            "Handler must return a tuple of (status_code, response_data)"
            in response["response_data"]["message"]
        )

    @pytest.mark.asyncio
    async def test_process_handler_response_model_validation_success(
        self, route_handler
    ):
        class ResponseModel(BaseModel):
            message: str

        async def mock_handler(headers, **kwargs):
            return 200, {"message": "Success"}

        route_info = {
            "handler": mock_handler,
            "content_type": "application/json",
        }

        route_handler._validate_params = Mock(return_value={})
        route_handler._validate_body = Mock(
            return_value={"status_code": 200, "error": None, "validated_params": {}}
        )
        route_info["return"] = {200: ResponseModel}

        response = await route_handler._process_handler(
            route_info, "/test", "GET", headers={}
        )

        assert response["content_type"] == "application/json"
        assert response["status_code"] == 200
        assert response["response_data"] == {"message": "Success"}

    @pytest.mark.asyncio
    async def test_process_handler_response_model_validation_error(self, route_handler):
        class ResponseModel(BaseModel):
            message: str

        async def mock_handler(headers, **kwargs) -> {200: ResponseModel}:
            return 200, {"invalid_field": "Error"}

        route_info = {
            "handler": mock_handler,
            "content_type": "application/json",
            "return": {200: ResponseModel},
        }

        route_handler._validate_params = Mock(return_value={})
        route_handler._validate_body = Mock(
            return_value={"status_code": 200, "error": None, "validated_params": {}}
        )

        response = await route_handler._process_handler(
            route_info, "/test", "GET", headers={}
        )

        assert response["content_type"] == "application/json"
        assert response["status_code"] == 422
        assert response["response_data"]["error"] == "Validation error"
        assert "details" in response["response_data"]
