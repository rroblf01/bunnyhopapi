from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from . import logger


def create_template_env(path: str):
    return Environment(loader=FileSystemLoader(path))


async def render_jinja_template(
    template_name: str, template_env: Environment, **context
):
    try:
        template = template_env.get_template(template_name)
        return 200, template.render(**context)
    except TemplateNotFound:
        return 404, "Template not found"
    except Exception as e:
        logger.info(f"Error rendering template {template_name}: {e}")
        logger.info(f"error type: {type(e)}")
        return 500, f"Internal server error: {e}"


async def serve_static_file(file_path: str, *args, **kwargs):
    try:
        with open(file_path, "r", encoding="utf-8") as static_file:
            return 200, static_file.read()
    except FileNotFoundError:
        logger.error(f"file not found: {file_path}")
        return 404, "File not found"
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return 500, "Internal server error"
