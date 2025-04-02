from jinja2 import Environment, FileSystemLoader
from . import logger


def create_template_env(path: str):
    """
    Crea un entorno de Jinja2 para renderizar plantillas.
    """
    return Environment(loader=FileSystemLoader(path))


async def render_jinja_template(
    template_name: str, template_env: Environment, **context
):
    """
    Renderiza una plantilla Jinja2 con el contexto proporcionado.
    """
    try:
        template = template_env.get_template(template_name)
        return 200, template.render(**context)
    except FileNotFoundError:
        return 404, "Template not found"
    except Exception as e:
        return 500, f"Internal server error: {e}"


async def serve_static_html(file_path: str, *args, **kwargs):
    """
    Sirve un archivo HTML estático desde el sistema de archivos.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as html_file:
            return 200, html_file.read()
    except FileNotFoundError:
        logger.error(f"HTML file not found: {file_path}")
        return 404, "File not found"
    except Exception as e:
        logger.error(f"Error reading HTML file {file_path}: {e}")
        return 500, "Internal server error"
