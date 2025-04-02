from typing import Dict
from urllib.parse import urlparse, parse_qs


class RequestParser:
    def __init__(self, routes: Dict, routes_with_params: Dict):
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
            # Optimización: Buscar el fin de headers directamente en bytes
            header_end = request_data.find(b"\r\n\r\n")
            if header_end == -1:
                return None, None, None, None, None

            # Dividir solo la parte de headers (evita decodificar el body innecesariamente)
            header_data = request_data[:header_end]

            # Decodificación optimizada solo de los headers
            try:
                headers_text = header_data.decode("latin-1")
            except UnicodeDecodeError:
                return None, None, None, None, None

            # Procesar primera línea
            first_line_end = headers_text.find("\r\n")
            if first_line_end == -1:
                return None, None, None, None, None

            first_line = headers_text[:first_line_end].split(" ", 2)
            if len(first_line) < 2:
                return None, None, None, None, None

            method = first_line[0]
            raw_path = first_line[1]

            # Optimización: Parseo manual de URL (más rápido que urlparse para casos simples)
            path_end = raw_path.find("?")
            if path_end == -1:
                path = raw_path
                query_params = {}
            else:
                path = raw_path[:path_end]
                query_string = raw_path[path_end + 1 :]
                query_params = {}

                # Parseo manual de query string (optimizado)
                if query_string:
                    for pair in query_string.split("&"):
                        if "=" in pair:
                            key, value = pair.split("=", 1)
                            query_params[key] = value.split(",")[0]  # Solo primer valor

            # Parseo de headers optimizado
            headers = {}
            header_lines = headers_text[first_line_end + 2 :].split("\r\n")
            for line in header_lines:
                if not line:
                    continue
                colon_pos = line.find(":")
                if colon_pos > 0:
                    key = line[:colon_pos].strip().lower()
                    value = line[colon_pos + 1 :].strip()
                    headers[key] = value

            # Procesamiento del body (solo si es necesario)
            body = None
            if "content-length" in headers:
                try:
                    content_length = int(headers["content-length"])
                    body_start = header_end + 4
                    if content_length > 0 and (body_start + content_length) <= len(
                        request_data
                    ):
                        # Decodificar solo si es texto (verificar content-type)
                        if headers.get("content-type", "").startswith(
                            "text/"
                        ) or "application/json" in headers.get("content-type", ""):
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
