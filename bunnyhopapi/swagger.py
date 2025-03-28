import re
import inspect
from typing import get_type_hints
from pydantic import BaseModel
from bunnyhopapi.models import PathParam

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


class SwaggerGenerator:
    @staticmethod
    def generate_path_item(path: str, methods: dict):
        swagger_path = re.sub(r"<(\w+)>", r"{\1}", path)
        SWAGGER_JSON["paths"][swagger_path] = {}

        for method, details in methods.items():
            handler = details["handler"]
            type_hints = get_type_hints(handler)

            operation = SwaggerGenerator._generate_operation(
                method, path, type_hints, details
            )
            SWAGGER_JSON["paths"][swagger_path][method.lower()] = operation

    @staticmethod
    def _generate_operation(method: str, path: str, type_hints: dict, details: dict):
        response_schema = {}
        parameters = []
        request_body = None

        # Process path parameters
        parameters.extend(SwaggerGenerator._process_path_params(type_hints))

        # Process body parameters
        request_body = SwaggerGenerator._process_body_params(type_hints)

        # Process response types
        response_schema = SwaggerGenerator._process_response_types(type_hints)

        # Build operation
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
    def _process_path_params(type_hints: dict):
        parameters = []
        for param_name, param_type in type_hints.items():
            if isinstance(param_type, PathParam):
                inner_type = param_type.param_type
                type_name = inner_type.__name__.lower()
                swagger_type = TYPE_MAPPING.get(type_name, type_name)
                parameters.append(
                    {
                        "name": param_name,
                        "in": "path",
                        "required": True,
                        "schema": {"type": swagger_type},
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
                # Add model to components if not already there
                if "components" not in SWAGGER_JSON:
                    SWAGGER_JSON["components"] = {"schemas": {}}
                SWAGGER_JSON["components"]["schemas"][param_type.__name__] = (
                    param_type.schema()
                )

                return {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": param_type.schema(
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
            elif inspect.isclass(return_type) and issubclass(return_type, BaseModel):
                response_schema.update(
                    SwaggerGenerator._add_response_model(200, return_type)
                )

        return response_schema

    @staticmethod
    def _add_response_model(status_code, model):
        if "components" not in SWAGGER_JSON:
            SWAGGER_JSON["components"] = {"schemas": {}}
        SWAGGER_JSON["components"]["schemas"][model.__name__] = model.schema()

        return {
            status_code: {
                "description": f"Response with status {status_code}",
                "content": {"application/json": {"schema": model.schema()}},
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
