import sys
import time
from unittest.mock import MagicMock, patch
from threading import Timer
from watchdog.events import FileModifiedEvent
from bunnyhopapi.server import ReloadEventHandler, Server


class TestReloadEventHandler:
    def setup_method(self):
        self.server_mock = MagicMock(spec=Server)
        self.server_mock.debounce_timer = None
        self.event_handler = ReloadEventHandler(self.server_mock)

    def teardown_method(self):
        if (
            self.server_mock.debounce_timer
            and self.server_mock.debounce_timer.is_alive()
        ):
            self.server_mock.debounce_timer.cancel()

    @patch("os.path.abspath")
    @patch("os.path.commonpath")
    def test_on_any_event_ignores_non_python_files(self, mock_commonpath, mock_abspath):
        mock_abspath.return_value = "/path/to/file.txt"
        mock_commonpath.return_value = self.event_handler.main_script_dir
        event = FileModifiedEvent("/path/to/file.txt")

        self.event_handler.on_any_event(event)
        assert self.server_mock.debounce_timer is None

    @patch("os.path.abspath")
    @patch("os.path.commonpath")
    def test_on_any_event_triggers_restart(self, mock_commonpath, mock_abspath):
        mock_abspath.return_value = "/path/to/file.py"
        mock_commonpath.return_value = self.event_handler.main_script_dir
        event = FileModifiedEvent("/path/to/file.py")

        self.event_handler.on_any_event(event)
        assert self.server_mock.debounce_timer is not None
        assert self.server_mock.debounce_timer.is_alive()

    @patch("os.execv")
    def test_restart_server(self, mock_execv):
        self.server_mock.processes = [MagicMock(), MagicMock()]
        self.server_mock.observer = MagicMock()

        self.event_handler.restart_server()

        self.server_mock.observer.stop.assert_called_once()
        for process in self.server_mock.processes:
            process.terminate.assert_called_once()
            process.join.assert_called_once()
        mock_execv.assert_called_once_with(sys.executable, ["python"] + sys.argv)
