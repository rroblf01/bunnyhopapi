import pytest
from jinja2 import Environment
from bunnyhopapi.templates import (
    create_template_env,
    render_jinja_template,
    serve_static_file,
)
import os
import tempfile


class TestTemplates:
    def test_create_template_env(self):
        env = create_template_env("example/templates/jinja")
        assert isinstance(env, Environment)

    @pytest.mark.asyncio
    async def test_render_jinja_template_success(self):
        env = create_template_env("example/templates/jinja")
        status, content = await render_jinja_template("index.html", env, title="Test")
        assert status == 200
        assert "Test Page" in content

    @pytest.mark.asyncio
    async def test_render_jinja_template_not_found(self):
        env_path = "/"
        template_name = "nonexistent.html"
        env = create_template_env(env_path)
        status, content = await render_jinja_template(template_name, env)
        assert status == 404
        assert "Template not found" == content

    @pytest.mark.asyncio
    async def test_render_jinja_template_error(self):
        env = create_template_env("example/templates/jinja")
        status, content = await render_jinja_template(None, env)
        assert status == 500
        assert (
            "Internal server error: 'NoneType' object has no attribute 'split'"
            == content
        )

    @pytest.mark.asyncio
    async def test_serve_static_file_success(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(b"Test content")
            tmp_file_path = tmp_file.name

        try:
            status, content = await serve_static_file(tmp_file_path)
            assert status == 200
            assert content == "Test content"
        finally:
            os.remove(tmp_file_path)

    @pytest.mark.asyncio
    async def test_serve_static_file_not_found(self):
        status, content = await serve_static_file("nonexistent_file.txt")
        assert status == 404
        assert content == "File not found"

    @pytest.mark.asyncio
    async def test_serve_static_file_internal_error(self):
        status, content = await serve_static_file(None)
        assert status == 500
        assert content == "Internal server error"
