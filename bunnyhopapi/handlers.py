import json
import inspect
from . import logger
from typing import get_type_hints, get_origin
import asyncio
from pydantic import BaseModel, ValidationError
from bunnyhopapi.models import PathParam, QueryParam
from .models import RouterBase
from dataclasses import dataclass, field


@dataclass
class RouteHandler:
    routes: dict = field(default_factory=dict)
    routes_with_params: dict = field(default_factory=dict)

    def _extract_params(self, path: str, route_path: str):
        if route_path not in self.routes_with_params:
            return None

        compiled_pattern = self.routes_with_params[route_path]
        match = compiled_pattern.match(path)
        if not match:
            return None

        return match.groupdict()

    async def execute_handler(
        self,
        path: str,
        method: str,
        body: str | None = None,
        headers: dict | None = None,
        query_params: dict | None = None,
    ):
        route_info = self._find_route(path, method)
        if not route_info:
            return await self._route_not_found_response(path, method)

        handler_info, params = route_info
        handler_info["params"] = params
        return await self._process_handler(
            handler_info, path, method, body, headers, query_params
        )

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

    async def _route_not_found_response(self, path: str, method: str):
        error_msg = {"error": f"Route {method} {path} not found"}
        return "application/json", 404, error_msg

    async def _process_handler(
        self,
        route_info: dict,
        path: str,
        method: str,
        body: str = None,
        headers: dict = None,
        query_params: dict = None,
    ):
        handler = route_info["handler"]
        content_type = route_info["content_type"]
        middleware = route_info.get("middleware")
        route_params = route_info.get("params", {})

        type_hints = get_type_hints(handler)

        try:
            validated_params = self._validate_params(
                route_params, type_hints, query_params
            )
        except ValueError as e:
            logger.error(f"Validation error for {method} {path}: {str(e)}")
            return {
                "content_type": content_type,
                "status_code": 422,
                "response_data": {"error": str(e)},
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
            result = (middleware or handler)(headers=headers, **validated_params)

            if inspect.isasyncgen(result):
                return {
                    "content_type": RouterBase.CONTENT_TYPE_SSE,
                    "status_code": 200,
                    "response_data": result,
                }

            response = await result if asyncio.iscoroutine(result) else result

            if not isinstance(response, tuple) or len(response) != 2:
                raise ValueError(
                    "Handler must return a tuple of (status_code, response_data)"
                )

            status_code, response_data = response

            return_type = type_hints.get("return", {})
            if isinstance(return_type, dict) and (
                response_model := return_type.get(status_code)
            ):
                try:
                    response_data = response_model.model_validate(
                        response_data
                    ).model_dump()
                except ValidationError as e:
                    logger.error(f"Validation error: {e}", exc_info=True)
                    return {
                        "content_type": content_type,
                        "status_code": 422,
                        "response_data": {
                            "error": "Validation error",
                            "details": e.errors(),
                        },
                    }

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

    def _validate_params(self, params: dict, type_hints: dict, query_params: dict = {}):
        validated_params = {}
        combined_params = {**params, **(query_params or {})}

        for param_name, param_value in combined_params.items():
            if param_name not in type_hints:
                continue

            param_type = type_hints[param_name]
            origin = get_origin(param_type)

            try:
                if origin is PathParam or origin is QueryParam:
                    param_class = param_type.__args__[0]
                    default_value = (
                        param_type.__args__[1] if len(param_type.__args__) > 1 else None
                    )
                    validated_params[param_name] = (
                        param_class(param_value)
                        if param_value is not None
                        else default_value
                    )
                else:
                    validated_params[param_name] = param_value
            except (ValueError, TypeError):
                raise ValueError(
                    f"Invalid value for parameter '{param_name}': '{param_value}' is not a valid {param_class.__name__}."
                )

        return validated_params

    def _validate_body(self, body: str, type_hints: dict):
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
