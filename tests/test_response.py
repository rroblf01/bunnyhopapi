import pytest
from bunnyhopapi.models import RouterBase
from bunnyhopapi.response import ResponseHandler
import inspect


class TestResponseHandler:
    @pytest.mark.parametrize(
        "cors, expected_headers",
        [
            (
                True,
                b"Access-Control-Allow-Origin: *\r\n"
                b"Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
                b"Access-Control-Allow-Headers: Content-Type\r\n",
            ),
            (False, b""),
        ],
    )
    def test_get_cors_headers(self, cors, expected_headers):
        response_handler = ResponseHandler(cors=cors)
        headers = response_handler._get_cors_headers()
        assert headers == expected_headers

    @pytest.mark.asyncio
    async def test_prepare_response_sse(self):
        async def async_generator():
            yield b"data: test\n\n"

        response_handler = ResponseHandler(cors=True)
        content_type = RouterBase.CONTENT_TYPE_SSE
        status_code = 200
        response_data = async_generator()

        response, generator = response_handler.prepare_response(
            content_type, status_code, response_data
        )

        assert response.startswith(b"HTTP/1.1 200 OK\r\n")
        assert b"Content-Type: text/event-stream\r\n" in response
        assert b"Access-Control-Allow-Origin: *\r\n" in response
        assert inspect.isasyncgen(generator)

    @pytest.mark.asyncio
    async def test_prepare_response_with_string(self):
        response_handler = ResponseHandler(cors=False)
        content_type = "text/plain"
        status_code = 200
        response_data = "Hello, world!"

        response = response_handler.prepare_response(
            content_type, status_code, response_data
        )

        assert response.startswith(b"HTTP/1.1 200 OK\r\n")
        assert b"Content-Type: text/plain\r\n" in response
        assert b"Content-Length: 13\r\n" in response
        assert b"Hello, world!" in response

    def test_prepare_options_response(self):
        response_handler = ResponseHandler(cors=True)
        response = response_handler.prepare_options_response()

        assert response.startswith(b"HTTP/1.1 204 No Content\r\n")
        assert b"Access-Control-Allow-Origin: *\r\n" in response
        assert b"Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n" in response
        assert b"Access-Control-Allow-Headers: Content-Type\r\n" in response
        assert b"Content-Length: 0\r\n" in response
        assert b"Connection: close\r\n" in response

    def test_prepare_error_response_with_dict(self):
        response_handler = ResponseHandler(cors=False)
        status_code = 404
        response_data = {"error": "Not Found"}

        response = response_handler._prepare_error_response(status_code, response_data)

        assert response.startswith(b"HTTP/1.1 404 \r\n")
        assert b"Content-Type: application/json\r\n" in response
        assert b"Content-Length: 22\r\n" in response
        assert b'{"error": "Not Found"}' in response

    def test_prepare_normal_response_with_html_string(self):
        response_handler = ResponseHandler(cors=False)
        content_type = "text/html"
        status_code = 200
        response_data = "<html><body>Hello, world!</body></html>"

        response = response_handler._prepare_normal_response(
            content_type, status_code, response_data
        )

        assert response.startswith(b"HTTP/1.1 200 OK\r\n")
        assert b"Content-Type: text/html\r\n" in response
        assert b"Content-Length: 39\r\n" in response
        assert b"<html><body>Hello, world!</body></html>" in response

    def test_prepare_normal_response_with_json_dict(self):
        response_handler = ResponseHandler(cors=False)
        content_type = "application/json"
        status_code = 200
        response_data = {"message": "Hello, world!"}
        response_data_length = len(str(response_data).encode("utf-8"))

        response = response_handler._prepare_normal_response(
            content_type, status_code, response_data
        )

        assert response.startswith(b"HTTP/1.1 200 OK\r\n")
        assert b"Content-Type: application/json\r\n" in response
        assert f"Content-Length: {response_data_length}\r\n".encode("utf-8") in response
        assert b'{"message": "Hello, world!"}' in response
