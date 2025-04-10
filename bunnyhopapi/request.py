class RequestParser:
    def __init__(self, routes: dict, routes_with_params: dict):
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

    async def parse_request(self, request_data: bytes):
        try:
            header_end = request_data.find(b"\r\n\r\n")
            if header_end == -1:
                return None, None, None, None, None

            header_data = request_data[:header_end]

            headers_text = header_data.decode("latin-1")

            first_line_end = headers_text.find("\r\n")
            if first_line_end == -1:
                first_line = headers_text.split(" ", 2)
            else:
                first_line = headers_text[:first_line_end].split(" ", 2)

            if len(first_line) < 2:
                return None, None, None, None, None

            method = first_line[0]
            raw_path = first_line[1]

            path_end = raw_path.find("?")
            if path_end == -1:
                path = raw_path
                query_params = {}
            else:
                path = raw_path[:path_end]
                query_string = raw_path[path_end + 1 :]
                query_params = {}

                if query_string:
                    for pair in query_string.split("&"):
                        if "=" in pair:
                            key, value = pair.split("=", 1)
                            query_params[key] = value.split(",")[0]

            headers = {}
            if first_line_end != -1:
                header_lines = headers_text[first_line_end + 2 :].split("\r\n")
                for line in header_lines:
                    colon_pos = line.find(":")
                    if colon_pos > 0:
                        key = line[:colon_pos].strip()
                        value = line[colon_pos + 1 :].strip()
                        headers[key] = value

            body = None
            if "Content-Length" in headers:
                try:
                    content_length = int(headers["Content-Length"])
                    body_start = header_end + 4
                    if content_length > 0 and (body_start + content_length) <= len(
                        request_data
                    ):
                        if (
                            headers.get("Content-Type", "").startswith("text/")
                            or headers.get("Content-Type", "") == "application/json"
                        ):
                            body = request_data[
                                body_start : body_start + content_length
                            ].decode("utf-8")
                        else:
                            body = request_data[
                                body_start : body_start + content_length
                            ]
                except (ValueError, UnicodeDecodeError):
                    pass

            return method, path, headers, body, query_params

        except Exception as e:
            return None, None, None, None, None
