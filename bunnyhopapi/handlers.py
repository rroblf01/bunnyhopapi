import json
import inspect
from . import logger
from typing import Dict, Optional, get_type_hints, get_origin
import asyncio
from pydantic import BaseModel, ValidationError
from bunnyhopapi.models import PathParam, QueryParam
from .models import RouterBase


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

    async def execute_handler(
        self,
        path: str,
        method: str,
        body: Optional[str] = None,
        headers: Optional[Dict] = None,
        query_params: Optional[Dict] = None,
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
        route_info: Dict,
        path: str,
        method: str,
        body: Optional[str],
        headers: Optional[Dict] = None,
        query_params: Optional[Dict] = None,
    ):
        handler = route_info["handler"]
        content_type = route_info["content_type"]
        middleware = route_info.get("middleware")

        type_hints = get_type_hints(handler)
        try:
            validated_params = self._validate_params(
                route_info.get("params", {}), type_hints, query_params
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
            if not middleware:
                result = handler(headers=headers, **validated_params)
            else:
                result = middleware(headers=headers, **validated_params)

            if inspect.isasyncgen(result):
                return {
                    "content_type": RouterBase.CONTENT_TYPE_SSE,
                    "status_code": 200,
                    "response_data": result,
                }

            response = await result if asyncio.iscoroutine(result) else result

            if isinstance(response, tuple) and len(response) == 2:
                status_code, response_data = response
            else:
                raise ValueError(
                    "Handler must return a tuple of (status_code, response_data)"
                )

            if response_model := type_hints.get("return") and type_hints.get(
                "return", {}
            ).get(status_code):
                try:
                    validated_data = response_model.validate(response_data)

                    response_data = validated_data.model_dump()
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

    def _validate_params(self, params: Dict, type_hints: Dict, query_params: Dict):
        validated_params = {}
        for param_name, param_value in {**params, **query_params}.items():
            if param_name not in type_hints:
                continue

            param_type = type_hints[param_name]
            if get_origin(param_type) is PathParam:
                try:
                    validated_params[param_name] = param_type.__args__[0](param_value)
                except ValueError:
                    raise ValueError(
                        f"Invalid value for parameter '{param_name}': '{param_value}' is not a valid {param_type.__args__[0].__name__}."
                    )
                except TypeError:
                    raise ValueError(
                        f"Type error for parameter '{param_name}': Expected type {param_type.__args__[0].__name__}, but got value '{param_value}'."
                    )
            elif get_origin(param_type) is QueryParam:
                try:
                    validated_params[param_name] = param_type.__args__[0](param_value)
                except ValueError:
                    raise ValueError(
                        f"Invalid value for query parameter '{param_name}': '{param_value}' is not a valid {param_type.__args__[0].__name__}."
                    )
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
