import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bunnyhopapi.server import Server
from bunnyhopapi.templates import serve_static_file


class TestServer:
    @pytest.fixture
    def server_instance(self):
        return Server(cors=True, port=8000)

    def test_add_swagger(self, server_instance):
        server_instance.add_swagger()
        assert "/swagger.json" in server_instance.routes
        assert "/docs" in server_instance.routes

    @pytest.mark.asyncio
    async def test_include_static_folder(self, server_instance, tmp_path):
        content_file = "Hello, world!"
        static_folder = tmp_path / "static"
        static_folder.mkdir()
        (static_folder / "test.txt").write_text(content_file)

        server_instance.include_static_folder(str(static_folder))

        route = "/static/test.txt"
        assert route in server_instance.routes
        handler = server_instance.routes[route]["GET"]["handler"]
        assert handler is not None

        response = await serve_static_file(static_folder / "test.txt")
        status_code, content = response
        assert status_code == 200
        assert content == content_file

    @pytest.mark.asyncio
    async def test_include_static_folder_not_exists(self, server_instance):
        non_existent_path = "/path/does/not/exist"

        with patch("bunnyhopapi.server.logger.error") as mock_logger:
            server_instance.include_static_folder(non_existent_path)

            mock_logger.assert_called_once_with(
                f"Static folder does not exist: {non_existent_path}"
            )

    @pytest.mark.asyncio
    async def test_include_static_folder_not_directory(self, server_instance, tmp_path):
        not_a_directory = tmp_path / "file.txt"
        not_a_directory.write_text("This is a file, not a directory.")

        with patch("bunnyhopapi.server.logger.error") as mock_logger:
            server_instance.include_static_folder(str(not_a_directory))

            mock_logger.assert_called_once_with(
                f"Provided path is not a directory: {not_a_directory}"
            )

    @pytest.mark.asyncio
    async def test_run_server(self):
        with patch(
            "bunnyhopapi.server.asyncio.start_server", new_callable=AsyncMock
        ) as mock_start_server:
            server_instance = Server(cors=True, port=8000)
            mock_server = AsyncMock()
            mock_start_server.return_value = mock_server

            with patch("bunnyhopapi.server.uvloop.install"):
                await server_instance._run()

            mock_start_server.assert_called_once()
            mock_server.serve_forever.assert_called_once()

    def test_run(self):
        with (
            patch("bunnyhopapi.server.uvloop.install") as mock_uvloop_install,
            patch("bunnyhopapi.server.Process") as mock_process,
            patch("bunnyhopapi.server.Server._run", return_value=None) as mock_run,
        ):
            mock_process_instance = MagicMock()
            mock_process.return_value = mock_process_instance

            server_instance = Server(cors=True, port=8000)
            server_instance.run(workers=2)

            mock_uvloop_install.assert_called_once()

            assert mock_process.call_count == 2
            mock_process_instance.start.assert_called()
            mock_process_instance.join.assert_called()

            for call_args in mock_process.call_args_list:
                assert "target" in call_args.kwargs
                assert callable(call_args.kwargs["target"])

    def test_run_keyboard_interrupt(self):
        with (
            patch("bunnyhopapi.server.uvloop.install") as mock_uvloop_install,
            patch("bunnyhopapi.server.Process") as mock_process,
            patch("bunnyhopapi.server.logger.info") as mock_logger,
        ):
            mock_process_instance = MagicMock()
            mock_process.return_value = mock_process_instance

            server_instance = Server(cors=True, port=8000)

            mock_process_instance.join.side_effect = KeyboardInterrupt

            server_instance.run(workers=2)

            mock_uvloop_install.assert_called_once()

            mock_logger.assert_any_call("Server stopped by user")

            mock_process_instance.terminate.assert_called()
            mock_logger.assert_any_call("Server stopped")

    def test_handle_exit(self):
        with patch("os._exit") as mock_exit:
            with patch("bunnyhopapi.server.logger.info") as mock_logger:
                from signal import SIGINT
                from bunnyhopapi.server import handle_exit

                handle_exit(SIGINT, None)
                mock_logger.assert_called_with("Shutting down server...")
                mock_exit.assert_called_once_with(0)

    @pytest.mark.asyncio
    async def test_generate_swagger_json(self, server_instance):
        server_instance.add_swagger()
        server_instance.add_route("/test", "GET", lambda: None)
        status_code, swagger_json = await server_instance.generate_swagger_json()

        assert status_code == 200

        assert "/test" in swagger_json["paths"]
        assert "/docs" not in swagger_json["paths"]
        assert "/swagger.json" not in swagger_json["paths"]

    @pytest.mark.asyncio
    async def test_swagger_ui_handler(self, server_instance):
        status_code, response = await server_instance.swagger_ui_handler()

        assert status_code == 200

        assert "<!DOCTYPE html>" in response
        assert "<title>Swagger UI</title>" in response

    @pytest.mark.asyncio
    async def test_start_worker_run(self):
        with patch(
            "bunnyhopapi.server.Server._run", new_callable=AsyncMock
        ) as mock_run:
            server_instance = Server(cors=True, port=8000)
            server_instance._start_worker()

            mock_run.assert_called_once()

    def test_start_worker_keyboard_interrupt(self):
        with (
            patch(
                "bunnyhopapi.server.Server._run", side_effect=KeyboardInterrupt
            ) as mock_run,
            patch("bunnyhopapi.server.logger.info") as mock_logger,
        ):
            server_instance = Server(cors=True, port=8000)
            server_instance._start_worker()

            mock_run.assert_called_once()
            mock_logger.assert_called_with("Worker received stop signal")
