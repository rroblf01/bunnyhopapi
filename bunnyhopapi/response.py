import json
from typing import Union, AsyncGenerator, Tuple
import inspect
from . import logger
from .models import RouterBase, CookieOptions


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

    def _build_set_cookie_headers(self, cookies: dict) -> bytes:
        result = b""
        for name, value in cookies.items():
            if isinstance(value, CookieOptions):
                cookie_str = f"{name}={value.value}"
                if value.max_age is not None:
                    cookie_str += f"; Max-Age={value.max_age}"
                if value.path:
                    cookie_str += f"; Path={value.path}"
                if value.domain:
                    cookie_str += f"; Domain={value.domain}"
                if value.expires:
                    cookie_str += f"; Expires={value.expires}"
                if value.httponly:
                    cookie_str += "; HttpOnly"
                if value.secure:
                    cookie_str += "; Secure"
                if value.samesite:
                    cookie_str += f"; SameSite={value.samesite}"
            else:
                cookie_str = f"{name}={value}"
            result += f"Set-Cookie: {cookie_str}\r\n".encode("utf-8")
        return result

    def prepare_response(
        self,
        content_type: str,
        status_code: int,
        response_data: Union[dict, str, bytes, AsyncGenerator],
        cookies: dict = None,
    ) -> Union[Tuple[bytes, AsyncGenerator], bytes]:
        if content_type == RouterBase.CONTENT_TYPE_SSE and inspect.isasyncgen(
            response_data
        ):
            return self._prepare_sse_response(response_data, cookies or {})

        if isinstance(response_data, dict):
            response_data = json.dumps(response_data).encode("utf-8")
        elif isinstance(response_data, str):
            response_data = response_data.encode("utf-8")

        if status_code >= 400:
            return self._prepare_error_response(status_code, response_data, cookies or {})

        return self._prepare_normal_response(content_type, status_code, response_data, cookies or {})

    def _prepare_sse_response(self, generator: AsyncGenerator, cookies: dict = None):
        response = (
            (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/event-stream\r\n"
                b"Cache-Control: no-cache\r\n"
                b"Connection: keep-alive\r\n"
            )
            + self._get_cors_headers()
            + self._build_set_cookie_headers(cookies or {})
            + b"\r\n"
        )

        return response, generator

    def _prepare_error_response(
        self, status_code: int, response_data: Union[dict, str], cookies: dict = None
    ):
        content_type = "application/json"
        if isinstance(response_data, dict):
            response_data = json.dumps(response_data).encode("utf-8")

        return self._build_response(content_type, status_code, response_data, cookies or {})

    def _prepare_normal_response(
        self,
        content_type: str,
        status_code: int,
        response_data: Union[dict, str, bytes],
        cookies: dict = None,
    ):
        if content_type == "text/html" and isinstance(response_data, str):
            response_data = response_data.encode("utf-8")
        elif content_type == "application/json" and isinstance(response_data, dict):
            response_data = json.dumps(response_data).encode("utf-8")

        return self._build_response(content_type, status_code, response_data, cookies or {})

    def _build_response(
        self, content_type: str, status_code: int, response_data: bytes, cookies: dict = None
    ):
        content_length = len(response_data) if response_data else 0
        status_text = "OK" if status_code == 200 else ""

        return (
            (
                b"HTTP/1.1 "
                + str(status_code).encode("utf-8")
                + b" "
                + status_text.encode("utf-8")
                + b"\r\n"
                b"Content-Type: " + content_type.encode("utf-8") + b"\r\n"
                b"Content-Length: " + str(content_length).encode("utf-8") + b"\r\n"
            )
            + self._get_cors_headers()
            + self._build_set_cookie_headers(cookies or {})
            + b"Connection: close\r\n\r\n"
            + (response_data if response_data else b"")
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
