import pytest
from bunnyhopapi.swagger import SwaggerGenerator, SWAGGER_JSON
from bunnyhopapi.models import PathParam, QueryParam
from pydantic import BaseModel


class ExampleModel(BaseModel):
    name: str
    age: int


@pytest.fixture
def reset_swagger_json():
    SWAGGER_JSON["paths"] = {}
    SWAGGER_JSON["components"]["schemas"] = {}
    yield
    SWAGGER_JSON["paths"] = {}
    SWAGGER_JSON["components"]["schemas"] = {}


class TestSwaggerGenerator:
    def test_generate_path_item(self, reset_swagger_json):
        methods = {
            "GET": {
                "handler": lambda: None,
            }
        }
        SwaggerGenerator.generate_path_item("/test", methods)
        assert "/test" in SWAGGER_JSON["paths"]
        assert "get" in SWAGGER_JSON["paths"]["/test"]

    def test_generate_path_item_without_leading_slash(self, reset_swagger_json):
        methods = {
            "GET": {
                "handler": lambda: None,
            }
        }
        SwaggerGenerator.generate_path_item("test", methods)
        assert "/test" in SWAGGER_JSON["paths"]
        assert "get" in SWAGGER_JSON["paths"]["/test"]

    def test_process_path_params(self, reset_swagger_json):
        def handler(param: PathParam[int]):
            pass

        methods = {
            "GET": {
                "handler": handler,
            }
        }
        SwaggerGenerator.generate_path_item("/test/<param>", methods)
        assert "/test/{param}" in SWAGGER_JSON["paths"]
        parameters = SWAGGER_JSON["paths"]["/test/{param}"]["get"]["parameters"]
        assert len(parameters) == 1
        assert parameters[0]["name"] == "param"
        assert parameters[0]["in"] == "path"
        assert parameters[0]["schema"]["type"] == "integer"

    def test_process_query_params(self, reset_swagger_json):
        def handler(param: QueryParam[str] = "default"):
            pass

        methods = {
            "GET": {
                "handler": handler,
            }
        }
        SwaggerGenerator.generate_path_item("/test", methods)
        parameters = SWAGGER_JSON["paths"]["/test"]["get"]["parameters"]
        assert len(parameters) == 1
        assert parameters[0]["name"] == "param"
        assert parameters[0]["in"] == "query"
        assert parameters[0]["schema"]["type"] == "string"
        assert not parameters[0]["required"]

    def test_process_body_params(self, reset_swagger_json):
        def handler(body: ExampleModel):  # Actualización del nombre de la clase
            pass

        methods = {
            "POST": {
                "handler": handler,
            }
        }
        SwaggerGenerator.generate_path_item("/test", methods)
        request_body = SWAGGER_JSON["paths"]["/test"]["post"]["requestBody"]
        schema = request_body["content"]["application/json"]["schema"]
        assert "ExampleModel" in SWAGGER_JSON["components"]["schemas"]
        assert schema.get("title") == "ExampleModel"
        assert schema.get("type") == "object"
        assert "properties" in schema
        assert "name" in schema["properties"]
        assert "age" in schema["properties"]

    def test_process_body_params_without_components(self, reset_swagger_json):
        del SWAGGER_JSON["components"]

        class ExampleModel(BaseModel):  # Renombrado de TestModel a ExampleModel
            name: str
            age: int

        def handler(body: ExampleModel):  # Actualización del nombre de la clase
            pass

        methods = {
            "POST": {
                "handler": handler,
            }
        }

        SwaggerGenerator.generate_path_item("/test", methods)

        assert "components" in SWAGGER_JSON
        assert "schemas" in SWAGGER_JSON["components"]
        assert "ExampleModel" in SWAGGER_JSON["components"]["schemas"]

    def test_process_response_types(self, reset_swagger_json):
        def handler() -> {200: ExampleModel}:  # Actualización del nombre de la clase
            pass

        methods = {
            "GET": {
                "handler": handler,
            }
        }
        SwaggerGenerator.generate_path_item("/test", methods)
        responses = SWAGGER_JSON["paths"]["/test"]["get"]["responses"]
        assert 200 in responses
        assert (
            responses[200]["content"]["application/json"]["schema"]["$ref"]
            == "#/components/schemas/ExampleModel"
        )
        assert "ExampleModel" in SWAGGER_JSON["components"]["schemas"]

    def test_generate_path_item_with_non_callable_handler(self, reset_swagger_json):
        methods = {
            "GET": {
                "handler": "not_a_function",
            }
        }
        with pytest.raises(TypeError, match="not_a_function is not a callable object."):
            SwaggerGenerator.generate_path_item("/test", methods)

    def test_process_response_types_with_none_model(self, reset_swagger_json):
        def handler() -> {204: None}:
            pass

        methods = {
            "GET": {
                "handler": handler,
            }
        }
        SwaggerGenerator.generate_path_item("/test", methods)
        responses = SWAGGER_JSON["paths"]["/test"]["get"]["responses"]
        assert 204 in responses
        assert responses[204]["description"] == "Response with status 204"

    def test_process_response_types_with_base_model(self, reset_swagger_json):
        class ExampleModel(BaseModel):  # Renombrado de TestModel a ExampleModel
            name: str
            age: int

        def handler() -> ExampleModel:  # Actualización del nombre de la clase
            pass

        methods = {
            "GET": {
                "handler": handler,
            }
        }
        SwaggerGenerator.generate_path_item("/test", methods)
        responses = SWAGGER_JSON["paths"]["/test"]["get"]["responses"]
        assert 200 in responses
        assert (
            responses[200]["content"]["application/json"]["schema"]["$ref"]
            == "#/components/schemas/ExampleModel"
        )
        assert "ExampleModel" in SWAGGER_JSON["components"]["schemas"]

    def test_add_response_model_without_components(self, reset_swagger_json):
        del SWAGGER_JSON["components"]

        class ExampleModel(BaseModel):  # Renombrado de TestModel a ExampleModel
            name: str
            age: int

        response = SwaggerGenerator._add_response_model(
            200, ExampleModel
        )  # Actualización del nombre de la clase

        assert "components" in SWAGGER_JSON
        assert "schemas" in SWAGGER_JSON["components"]
        assert "ExampleModel" in SWAGGER_JSON["components"]["schemas"]

        assert 200 in response
        assert response[200]["description"] == "Response with status 200"
        assert (
            response[200]["content"]["application/json"]["schema"]["$ref"]
            == "#/components/schemas/ExampleModel"
        )

    def test_get_swagger_ui_html(self):
        html = SwaggerGenerator.get_swagger_ui_html()

        assert "<!DOCTYPE html>" in html
        assert "<html>" in html
        assert "<head>" in html
        assert "<body>" in html
        assert "</html>" in html

        assert '<div id="swagger-ui"></div>' in html

        assert "swagger-ui.css" in html
        assert "swagger-ui-bundle.js" in html
