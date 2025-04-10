import re
import inspect
from typing import get_type_hints, get_origin
from pydantic import BaseModel
from bunnyhopapi.models import PathParam, QueryParam

SWAGGER_JSON = {
    "openapi": "3.0.0",
    "info": {
        "title": "BunnyHop API",
        "version": "1.0.0",
    },
    "paths": {},
}

TYPE_MAPPING = {
    "int": "integer",
    "float": "number",
    "str": "string",
    "bool": "boolean",
}

SWAGGER_JSON["components"] = SWAGGER_JSON.get("components", {})
SWAGGER_JSON["components"]["schemas"] = SWAGGER_JSON["components"].get("schemas", {})
SWAGGER_JSON["components"]["securitySchemes"] = {
    "Authorization": {"type": "apiKey", "name": "Authorization", "in": "header"}
}

SWAGGER_JSON["security"] = [{"Authorization": []}]


class SwaggerGenerator:
    @staticmethod
    def generate_path_item(path: str, methods: dict):
        swagger_path = re.sub(r"<(\w+)>", r"{\1}", path)

        if not swagger_path.startswith("/"):
            swagger_path = "/" + swagger_path

        swagger_path = re.sub(r"/+", "/", swagger_path)

        SWAGGER_JSON["paths"][swagger_path] = {}

        for method, details in methods.items():
            handler = details.get("handler")
            if not callable(handler):
                raise TypeError(f"{handler} is not a callable object.")

            type_hints = get_type_hints(handler)

            operation = SwaggerGenerator._generate_operation(
                method, path, type_hints, details, handler
            )
            SWAGGER_JSON["paths"][swagger_path][method.lower()] = operation

    @staticmethod
    def _generate_operation(
        method: str, path: str, type_hints: dict, details: dict, handler
    ):
        response_schema = {}
        parameters = []
        request_body = None

        parameters.extend(SwaggerGenerator._process_path_params(type_hints, handler))
        request_body = SwaggerGenerator._process_body_params(type_hints)
        response_schema = SwaggerGenerator._process_response_types(type_hints)

        operation = {
            "summary": f"Handler for {method} {path}",
            "responses": response_schema
            or {
                200: {
                    "description": "Successful response",
                    "content": {"application/json": {"schema": {}}},
                }
            },
        }

        if parameters:
            operation["parameters"] = parameters

        if request_body and method.upper() in ["POST", "PUT", "PATCH"]:
            operation["requestBody"] = request_body

        return operation

    @staticmethod
    def _process_path_params(type_hints: dict, handler):
        parameters = []
        for param_name, param_type in type_hints.items():
            if get_origin(param_type) is PathParam:
                type_name = param_type.__args__[0].__name__
                swagger_type = TYPE_MAPPING.get(type_name, type_name)
                parameters.append(
                    {
                        "name": param_name,
                        "in": "path",
                        "required": True,
                        "schema": {"type": swagger_type},
                    }
                )
            elif get_origin(param_type) is QueryParam:
                type_name = param_type.__args__[0].__name__
                swagger_type = TYPE_MAPPING.get(type_name, type_name)

                signature = inspect.signature(handler)
                parameter = signature.parameters.get(param_name)
                is_required = not bool(
                    parameter is not None
                    and parameter.default is not inspect.Parameter.empty
                )

                parameters.append(
                    {
                        "name": param_name,
                        "in": "query",
                        "required": is_required,
                        "schema": {
                            "type": swagger_type,
                        },
                    }
                )
        return parameters

    @staticmethod
    def _process_body_params(type_hints: dict):
        for param_name, param_type in type_hints.items():
            if (
                inspect.isclass(param_type)
                and issubclass(param_type, BaseModel)
                and not isinstance(param_type, PathParam)
            ):
                if "components" not in SWAGGER_JSON:
                    SWAGGER_JSON["components"] = {"schemas": {}}
                SWAGGER_JSON["components"]["schemas"][param_type.__name__] = (
                    param_type.model_json_schema()
                )

                return {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": param_type.model_json_schema(
                                ref_template="#/components/schemas/{model}"
                            )
                        }
                    },
                }
        return None

    @staticmethod
    def _process_response_types(type_hints: dict):
        response_schema = {}

        if "return" in type_hints:
            return_type = type_hints["return"]

            if isinstance(return_type, dict):
                for status_code, model in return_type.items():
                    if inspect.isclass(model) and issubclass(model, BaseModel):
                        response_schema.update(
                            SwaggerGenerator._add_response_model(status_code, model)
                        )
                    elif model is None:
                        response_schema[status_code] = {
                            "description": f"Response with status {status_code}"
                        }
            elif inspect.isclass(return_type) and issubclass(return_type, BaseModel):
                response_schema.update(
                    SwaggerGenerator._add_response_model(200, return_type)
                )

        return response_schema

    @staticmethod
    def _add_response_model(status_code, model):
        if "components" not in SWAGGER_JSON:
            SWAGGER_JSON["components"] = {"schemas": {}}
        if model.__name__ not in SWAGGER_JSON["components"]["schemas"]:
            SWAGGER_JSON["components"]["schemas"][model.__name__] = (
                model.model_json_schema(ref_template="#/components/schemas/{model}")
            )

        return {
            status_code: {
                "description": f"Response with status {status_code}",
                "content": {
                    "application/json": {
                        "schema": {"$ref": f"#/components/schemas/{model.__name__}"}
                    }
                },
            }
        }

    @staticmethod
    def get_swagger_ui_html():
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Swagger UI</title>
            <link rel="stylesheet" type="text/css" href="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.20.0/swagger-ui.css">
        </head>
        <body>
            <div id="swagger-ui"></div>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.20.0/swagger-ui-bundle.js"></script>
            <script>
                const ui = SwaggerUIBundle({
                    url: '/swagger.json',
                    dom_id: '#swagger-ui',
                });
            </script>
        </body>
        </html>
        """
