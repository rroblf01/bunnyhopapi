import pytest
from unittest.mock import Mock
from bunnyhopapi.request import RequestParser
from bunnyhopapi.response import ResponseHandler
from bunnyhopapi.handlers import RouteHandler
from bunnyhopapi.models import CookieOptions


class TestCookieParsing:
    @pytest.fixture
    def request_parser(self):
        return RequestParser({}, {})

    def test_parse_cookies_multiple(self, request_parser):
        headers = {"Cookie": "session=abc123; user=john; lang=es"}
        cookies = request_parser._parse_cookies(headers)
        assert cookies == {"session": "abc123", "user": "john", "lang": "es"}

    def test_parse_cookies_single(self, request_parser):
        headers = {"Cookie": "token=xyz"}
        cookies = request_parser._parse_cookies(headers)
        assert cookies == {"token": "xyz"}

    def test_parse_cookies_empty_header(self, request_parser):
        headers = {"Cookie": ""}
        cookies = request_parser._parse_cookies(headers)
        assert cookies == {}

    def test_parse_cookies_no_cookie_header(self, request_parser):
        cookies = request_parser._parse_cookies({})
        assert cookies == {}

    def test_parse_cookies_value_with_equals(self, request_parser):
        headers = {"Cookie": "token=abc=def=ghi"}
        cookies = request_parser._parse_cookies(headers)
        assert cookies == {"token": "abc=def=ghi"}

    @pytest.mark.asyncio
    async def test_parse_request_returns_cookies(self, request_parser):
        request_data = (
            b"GET /test HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Cookie: session=abc123; user=john\r\n"
            b"\r\n"
        )
        method, path, headers, body, query_params, cookies = (
            await request_parser.parse_request(request_data)
        )

        assert method == "GET"
        assert cookies == {"session": "abc123", "user": "john"}

    @pytest.mark.asyncio
    async def test_parse_request_no_cookie_header_returns_empty_dict(
        self, request_parser
    ):
        request_data = b"GET /test HTTP/1.1\r\nHost: localhost\r\n\r\n"
        method, path, headers, body, query_params, cookies = (
            await request_parser.parse_request(request_data)
        )

        assert method == "GET"
        assert cookies == {}


class TestSetCookieHeaders:
    @pytest.fixture
    def response_handler(self):
        return ResponseHandler(cors=False)

    def test_set_cookie_simple_string(self, response_handler):
        headers = response_handler._build_set_cookie_headers({"session": "abc123"})
        assert headers == b"Set-Cookie: session=abc123\r\n"

    def test_set_cookie_multiple(self, response_handler):
        headers = response_handler._build_set_cookie_headers(
            {"session": "abc", "lang": "es"}
        )
        assert b"Set-Cookie: session=abc\r\n" in headers
        assert b"Set-Cookie: lang=es\r\n" in headers

    def test_set_cookie_empty(self, response_handler):
        headers = response_handler._build_set_cookie_headers({})
        assert headers == b""

    def test_set_cookie_options_httponly_secure(self, response_handler):
        cookie = CookieOptions("abc123", httponly=True, secure=True)
        headers = response_handler._build_set_cookie_headers({"session": cookie})
        assert b"Set-Cookie: session=abc123" in headers
        assert b"HttpOnly" in headers
        assert b"Secure" in headers

    def test_set_cookie_options_max_age(self, response_handler):
        cookie = CookieOptions("abc123", max_age=3600)
        headers = response_handler._build_set_cookie_headers({"session": cookie})
        assert b"Max-Age=3600" in headers

    def test_set_cookie_options_path(self, response_handler):
        cookie = CookieOptions("abc123", path="/api")
        headers = response_handler._build_set_cookie_headers({"session": cookie})
        assert b"Path=/api" in headers

    def test_set_cookie_options_domain(self, response_handler):
        cookie = CookieOptions("abc123", domain="example.com")
        headers = response_handler._build_set_cookie_headers({"session": cookie})
        assert b"Domain=example.com" in headers

    def test_set_cookie_options_samesite(self, response_handler):
        cookie = CookieOptions("abc123", samesite="Lax")
        headers = response_handler._build_set_cookie_headers({"session": cookie})
        assert b"SameSite=Lax" in headers

    def test_set_cookie_options_expires(self, response_handler):
        cookie = CookieOptions("abc123", expires="Wed, 21 Oct 2026 07:28:00 GMT")
        headers = response_handler._build_set_cookie_headers({"session": cookie})
        assert b"Expires=Wed, 21 Oct 2026 07:28:00 GMT" in headers

    def test_set_cookie_options_all_attributes(self, response_handler):
        cookie = CookieOptions(
            value="token123",
            path="/",
            max_age=7200,
            domain="example.com",
            httponly=True,
            secure=True,
            samesite="Strict",
        )
        headers = response_handler._build_set_cookie_headers({"auth": cookie})
        assert b"Set-Cookie: auth=token123" in headers
        assert b"Max-Age=7200" in headers
        assert b"Path=/" in headers
        assert b"Domain=example.com" in headers
        assert b"HttpOnly" in headers
        assert b"Secure" in headers
        assert b"SameSite=Strict" in headers

    def test_prepare_response_includes_set_cookie(self, response_handler):
        response = response_handler.prepare_response(
            "application/json",
            200,
            {"ok": True},
            {"session": "abc123"},
        )
        assert b"Set-Cookie: session=abc123" in response

    def test_prepare_response_no_cookies(self, response_handler):
        response = response_handler.prepare_response(
            "application/json", 200, {"ok": True}
        )
        assert b"Set-Cookie" not in response

    def test_prepare_error_response_includes_set_cookie(self, response_handler):
        response = response_handler.prepare_response(
            "application/json",
            401,
            {"error": "Unauthorized"},
            {"cleared": ""},
        )
        assert b"Set-Cookie: cleared=" in response


class TestHandlerCookieInjection:
    @pytest.fixture
    def route_handler(self):
        return RouteHandler()

    @pytest.mark.asyncio
    async def test_handler_receives_cookies(self, route_handler):
        received = {}

        async def mock_handler(headers, cookies: dict, **kwargs):
            received["cookies"] = cookies
            return 200, {"ok": True}

        route_handler._find_route = Mock(
            return_value=(
                {"handler": mock_handler, "content_type": "application/json"},
                {},
            )
        )

        await route_handler.execute_handler(
            "/test", "GET", cookies={"session": "abc123"}
        )

        assert received["cookies"] == {"session": "abc123"}

    @pytest.mark.asyncio
    async def test_handler_without_cookies_param_not_injected(self, route_handler):
        async def mock_handler(headers, **kwargs):
            return 200, {"ok": True}

        route_handler._find_route = Mock(
            return_value=(
                {"handler": mock_handler, "content_type": "application/json"},
                {},
            )
        )

        response = await route_handler.execute_handler(
            "/test", "GET", cookies={"session": "abc123"}
        )
        assert response["status_code"] == 200

    @pytest.mark.asyncio
    async def test_handler_returns_cookies_in_response(self, route_handler):
        async def mock_handler(headers, **kwargs):
            return 200, {"ok": True}, {"session": "new_token"}

        route_handler._find_route = Mock(
            return_value=(
                {"handler": mock_handler, "content_type": "application/json"},
                {},
            )
        )

        response = await route_handler.execute_handler("/test", "GET")

        assert response["status_code"] == 200
        assert response["cookies"] == {"session": "new_token"}

    @pytest.mark.asyncio
    async def test_handler_two_tuple_returns_empty_cookies(self, route_handler):
        async def mock_handler(headers, **kwargs):
            return 200, {"ok": True}

        route_handler._find_route = Mock(
            return_value=(
                {"handler": mock_handler, "content_type": "application/json"},
                {},
            )
        )

        response = await route_handler.execute_handler("/test", "GET")

        assert response["status_code"] == 200
        assert response["cookies"] == {}

    @pytest.mark.asyncio
    async def test_handler_returns_cookie_options(self, route_handler):
        async def mock_handler(headers, **kwargs):
            return 200, {"ok": True}, {
                "session": CookieOptions("token", httponly=True, max_age=3600)
            }

        route_handler._find_route = Mock(
            return_value=(
                {"handler": mock_handler, "content_type": "application/json"},
                {},
            )
        )

        response = await route_handler.execute_handler("/test", "GET")

        assert response["status_code"] == 200
        cookie = response["cookies"]["session"]
        assert isinstance(cookie, CookieOptions)
        assert cookie.value == "token"
        assert cookie.httponly is True
        assert cookie.max_age == 3600
