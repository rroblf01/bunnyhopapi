import json
from typing import Union, AsyncGenerator, Tuple
import inspect


class ResponseHandler:
    def __init__(self, cors: bool = False):
        self.cors = cors

    def _get_cors_headers(self):
        if not self.cors:
            return b""

        return (
            b"Access-Control-Allow-Origin: *\r\n"
            b"Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
            b"Access-Control-Allow-Headers: Content-Type\r\n"
        )

    def prepare_response(
        self,
        content_type: str,
        status_code: int,
        response_data: Union[dict, str, bytes, AsyncGenerator],
    ) -> Union[Tuple[bytes, AsyncGenerator], bytes]:
        if content_type == "text/event-stream" and inspect.isasyncgen(response_data):
            return self._prepare_sse_response(response_data)

        if isinstance(response_data, dict):
            response_data = json.dumps(response_data).encode("utf-8")
        elif isinstance(response_data, str):
            response_data = response_data.encode("utf-8")

        # Handle error responses
        if status_code >= 400:
            return self._prepare_error_response(status_code, response_data)

        # Normal response
        return self._prepare_normal_response(content_type, status_code, response_data)

    def _prepare_sse_response(self, generator: AsyncGenerator):
        response = (
            (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/event-stream\r\n"
                b"Cache-Control: no-cache\r\n"
                b"Connection: keep-alive\r\n"
            )
            + self._get_cors_headers()
            + b"\r\n"
        )

        return response, generator

    def _prepare_error_response(
        self, status_code: int, response_data: Union[dict, str]
    ):
        content_type = "application/json"
        if isinstance(response_data, dict):
            response_data = json.dumps(response_data).encode("utf-8")
        else:
            response_data = json.dumps({"error": str(response_data)}).encode("utf-8")

        return self._build_response(content_type, status_code, response_data)

    def _prepare_normal_response(
        self,
        content_type: str,
        status_code: int,
        response_data: Union[dict, str, bytes],
    ):
        if content_type == "text/html" and isinstance(response_data, str):
            response_data = response_data.encode("utf-8")
        elif content_type == "application/json" and isinstance(response_data, dict):
            response_data = json.dumps(response_data).encode("utf-8")

        return self._build_response(content_type, status_code, response_data)

    def _build_response(
        self, content_type: str, status_code: int, response_data: bytes
    ):
        content_length = len(response_data)

        return (
            (
                b"HTTP/1.1 " + str(status_code).encode("utf-8") + b"\r\n"
                b"Content-Type: " + content_type.encode("utf-8") + b"\r\n"
                b"Content-Length: " + str(content_length).encode("utf-8") + b"\r\n"
            )
            + self._get_cors_headers()
            + b"Connection: close\r\n\r\n"
            + response_data
        )

    def prepare_options_response(self):
        return (
            b"HTTP/1.1 204 No Content\r\n"
            b"Access-Control-Allow-Origin: *\r\n"
            b"Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
            b"Access-Control-Allow-Headers: Content-Type\r\n"
            b"Content-Length: 0\r\n"
            b"Connection: close\r\n"
            b"\r\n"
        )
