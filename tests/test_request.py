import pytest
from bunnyhopapi.request import RequestParser
import re


class TestRequestParser:
    @pytest.fixture
    def request_parser(self):
        routes = {}
        routes_with_params = {}
        return RequestParser(routes, routes_with_params)

    @pytest.mark.asyncio
    async def test_parse_request_valid_get(self, request_parser):
        request_data = (
            b"GET /test HTTP/1.1\r\nHost: localhost\r\nContent-Length: 0\r\n\r\n"
        )
        method, path, headers, body, query_params = await request_parser.parse_request(
            request_data
        )

        assert method == "GET"
        assert path == "/test"
        assert headers["Host"] == "localhost"
        assert body is None
        assert query_params == {}

    @pytest.mark.asyncio
    async def test_parse_request_with_query_params(self, request_parser):
        request_data = (
            b"GET /test?param1=value1&param2=value2 HTTP/1.1\r\nHost: localhost\r\n\r\n"
        )
        method, path, headers, body, query_params = await request_parser.parse_request(
            request_data
        )

        assert method == "GET"
        assert path == "/test"
        assert query_params == {"param1": "value1", "param2": "value2"}
        assert headers["Host"] == "localhost"
        assert body is None

    @pytest.mark.asyncio
    async def test_parse_request_with_body(self, request_parser):
        expected_body = '{"key": "value"}'
        request_data = (
            b"POST /test HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: " + str(len(expected_body)).encode("utf-8") + b"\r\n\r\n"
            b"" + expected_body.encode("utf-8")
        )
        method, path, headers, body, query_params = await request_parser.parse_request(
            request_data
        )

        assert method == "POST"
        assert path == "/test"
        assert headers["Content-Type"] == "application/json"
        assert body == expected_body
        assert query_params == {}

    @pytest.mark.asyncio
    async def test_parse_request_invalid_format(self, request_parser):
        request_data = b"INVALID REQUEST"
        method, path, headers, body, query_params = await request_parser.parse_request(
            request_data
        )

        assert method is None
        assert path is None
        assert headers is None
        assert body is None
        assert query_params is None

    @pytest.mark.asyncio
    async def test_parse_request_missing_headers(self, request_parser):
        request_data = b"GET /test HTTP/1.1\r\n\r\n"
        method, path, headers, body, query_params = await request_parser.parse_request(
            request_data
        )

        assert method == "GET"
        assert path == "/test"
        assert headers == {}
        assert body is None
        assert query_params == {}

    @pytest.mark.asyncio
    async def test_parse_request_first_line_too_short(self, request_parser):
        request_data = b"GET\r\nHost: localhost\r\n\r\n"
        method, path, headers, body, query_params = await request_parser.parse_request(
            request_data
        )

        assert method is None
        assert path is None
        assert headers is None
        assert body is None
        assert query_params is None

    @pytest.mark.asyncio
    async def test_parse_request_empty_header_line(self, request_parser):
        request_data = (
            b"GET /test HTTP/1.1\r\nHost: localhost\n\r\n\r\n\r\n\r\n\r\n\r\n\r\n\r\n"
        )
        method, path, headers, body, query_params = await request_parser.parse_request(
            request_data
        )

        assert method == "GET"
        assert path == "/test"
        assert headers == {"Host": "localhost"}
        assert body is None
        assert query_params == {}

    @pytest.mark.asyncio
    async def test_parse_request_binary_body(self, request_parser):
        binary_body = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00"
        request_data = (
            b"POST /upload HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Content-Type: application/octet-stream\r\n"
            b"Content-Length: "
            + str(len(binary_body)).encode("utf-8")
            + b"\r\n\r\n"
            + binary_body
        )
        method, path, headers, body, query_params = await request_parser.parse_request(
            request_data
        )

        assert method == "POST"
        assert path == "/upload"
        assert headers["Content-Type"] == "application/octet-stream"
        assert body == binary_body
        assert query_params == {}

    @pytest.mark.asyncio
    async def test_parse_request_value_error_in_body(self, request_parser):
        request_data = (
            b"POST /test HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: invalid\r\n\r\n"
            b'{"key": "value"}'
        )
        method, path, headers, body, query_params = await request_parser.parse_request(
            request_data
        )

        assert method == "POST"
        assert path == "/test"
        assert headers["Content-Type"] == "application/json"
        assert body is None
        assert query_params == {}

    @pytest.mark.asyncio
    async def test_parse_request_generic_exception(self, request_parser):
        class MockBytes:
            def find(self, _):
                raise Exception("Mocked exception")

        request_data = MockBytes()
        method, path, headers, body, query_params = await request_parser.parse_request(
            request_data
        )

        assert method is None
        assert path is None
        assert headers is None
        assert body is None
        assert query_params is None

    def test_extract_params_route_not_in_routes_with_params(self, request_parser):
        path = "/test/123"
        route_path = "/test/<id>"
        result = request_parser._extract_params(path, route_path)
        assert result is None

    def test_extract_params_no_match(self, request_parser):
        request_parser.routes_with_params = {
            "/test/<id>": re.compile(r"^/test/(?P<id>\d+)$")
        }
        path = "/test/abc"
        route_path = "/test/<id>"
        result = request_parser._extract_params(path, route_path)
        assert result is None

    def test_extract_params_valid_match(self, request_parser):
        request_parser.routes_with_params = {
            "/test/<id>": re.compile(r"^/test/(?P<id>\d+)$")
        }
        path = "/test/123"
        route_path = "/test/<id>"
        result = request_parser._extract_params(path, route_path)
        assert result == {"id": "123"}
