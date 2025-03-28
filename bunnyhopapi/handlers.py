import json
import inspect
from . import logger
from typing import Dict, Optional, get_type_hints
import asyncio
from pydantic import BaseModel
from bunnyhopapi.models import PathParam


class RouteHandler:
    def __init__(self, routes: Dict, routes_with_params: Dict):
        self.routes = routes
        self.routes_with_params = routes_with_params

    def _extract_params(self, path: str, route_path: str):
        if route_path not in self.routes_with_params:
            return None

        compiled_pattern = self.routes_with_params[route_path]
        match = compiled_pattern.match(path)
        if not match:
            return None

        return match.groupdict()

    async def execute_handler(self, path: str, method: str, body: Optional[str] = None):
        route_info = self._find_route(path, method)
        if not route_info:
            return {
                "content_type": "application/json",
                "status_code": 404,
                "response_data": {"error": f"Route {method} {path} not found"},
            }

        handler_info, params = route_info
        handler_info["params"] = params
        return await self._process_handler(handler_info, path, method, body)

    def _find_route(self, path: str, method: str):
        if path in self.routes and method in self.routes[path]:
            return self.routes[path][method], {}

        for route_path, methods in self.routes.items():
            if method not in methods:
                continue

            params = self._extract_params(path, route_path)
            if params is not None:
                return methods[method], params

        return None

    def _route_not_found_response(self, path: str, method: str):
        error_msg = f"Route {method} {path} not found"
        return "application/json", 404, {"error": error_msg}

    async def _process_handler(
        self, route_info: Dict, path: str, method: str, body: Optional[str]
    ):
        handler = route_info["handler"]
        content_type = route_info["content_type"]
        type_hints = get_type_hints(handler)
        validated_params = self._validate_params(
            route_info.get("params", {}), type_hints
        )

        if validated_params is None:
            return {
                "content_type": content_type,
                "status_code": 422,
                "response_data": {"error": "Invalid path parameters"},
            }

        if body:
            body_validation = self._validate_body(body, type_hints)
            if body_validation.get("error"):
                return {
                    "content_type": content_type,
                    "status_code": body_validation["status_code"],
                    "response_data": body_validation["error"],
                }
            validated_params.update(body_validation["validated_params"])

        try:
            result = handler(**validated_params)

            if inspect.isasyncgen(result):
                return {
                    "content_type": "text/event-stream",
                    "status_code": 200,
                    "response_data": result,
                }

            response = await result if asyncio.iscoroutine(result) else result
            status_code, response_data = response
            return {
                "content_type": content_type,
                "status_code": status_code,
                "response_data": response_data,
            }

        except Exception as e:
            logger.error(f"Handler error for {method} {path}: {str(e)}", exc_info=True)
            return {
                "content_type": content_type,
                "status_code": 500,
                "response_data": {"error": "Internal server error", "message": str(e)},
            }

    def _validate_params(self, params: Dict, type_hints: Dict):
        validated_params = {}
        for param_name, param_value in params.items():
            if param_name not in type_hints:
                validated_params[param_name] = param_value
                continue

            param_type = type_hints[param_name]
            if isinstance(param_type, PathParam):
                try:
                    validated_params[param_name] = param_type.validate(param_value)
                except ValueError as e:
                    return None
            else:
                validated_params[param_name] = param_value
        return validated_params

    def _validate_body(self, body: str, type_hints: Dict):
        try:
            body_data = json.loads(body)
        except json.JSONDecodeError:
            return {
                "status_code": 400,
                "error": {"error": "Invalid JSON format in request body"},
                "validated_params": {},
            }

        validated_params = {}
        for param_name, param_type in type_hints.items():
            if (
                inspect.isclass(param_type)
                and issubclass(param_type, BaseModel)
                and param_name not in validated_params
            ):
                try:
                    validated_params[param_name] = param_type(**body_data)
                except ValueError as e:
                    errors = e.errors()
                    error_details = [
                        {
                            "field": "->".join(str(loc) for loc in error["loc"]),
                            "message": error["msg"],
                            "type": error["type"],
                        }
                        for error in errors
                    ]
                    return {
                        "status_code": 422,
                        "error": {
                            "error": "Validation error",
                            "details": error_details,
                        },
                        "validated_params": {},
                    }

        return {"status_code": 200, "error": None, "validated_params": validated_params}
