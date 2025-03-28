import re
from typing import Dict


class RequestParser:
    def __init__(self, routes: Dict, routes_with_params: Dict):
        self.routes = routes
        self.routes_with_params = routes_with_params

    def _parse_path(self, path: str):
        param_pattern = re.compile(r"<(\w+)>")
        regex_pattern = re.sub(param_pattern, r"(?P<\1>[^/]+)", path)
        return re.compile(regex_pattern)

    def _extract_params(self, path: str, route_path: str):
        if route_path not in self.routes_with_params:
            return None

        compiled_pattern = self.routes_with_params[route_path]
        match = compiled_pattern.match(path)
        if not match:
            return None

        return match.groupdict()

    def parse_request(self, request_data: bytes):
        request_lines = request_data.decode().split("\r\n")
        if not request_lines:
            return None, None, None, None

        first_line = request_lines[0].split(" ", 2)
        if len(first_line) < 2:
            return None, None, None, None

        method, path = first_line[0], first_line[1]
        headers = {}
        body = None

        for line in request_lines[1:]:
            if not line.strip():
                break
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()

        if "content-length" in headers:
            try:
                content_length = int(headers["content-length"])
                body_start = request_data.find(b"\r\n\r\n") + 4
                if body_start > 0 and body_start + content_length <= len(request_data):
                    body = request_data[
                        body_start : body_start + content_length
                    ].decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                pass

        return method, path, headers, body
