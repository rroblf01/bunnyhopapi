from bunnyhopapi.server import Server, Router
from bunnyhopapi.models import CookieOptions



router = Router(prefix="/api/v1")


@router.get("/cookies/read")
def read_cookies(headers, cookies: dict):
    """Lee todas las cookies enviadas por el cliente."""
    visit_count = int(cookies.get("visits", 0))
    lang = cookies.get("lang", "not set")
    user_agent = headers.get("User-Agent", "unknown")
    return 200, {
        "received_cookies": cookies,
        "visits": visit_count,
        "lang": lang,
        "user_agent": user_agent,
    }


@router.get("/cookies/set")
def set_cookies(headers, cookies: dict):
    """Añade una cookie nueva y modifica una existente."""
    # Leer cookie existente y modificarla
    visit_count = int(cookies.get("visits", 0)) + 1

    response_cookies = {
        # Modificar cookie existente (mismo nombre, nuevo valor)
        "visits": CookieOptions(
            value=str(visit_count),
            path="/",
            max_age=60 * 60 * 24 * 7,  # 7 días
        ),
        # Añadir cookie nueva con atributos de seguridad
        "lang": CookieOptions(
            value="es",
            path="/",
            max_age=60 * 60 * 24 * 365,  # 1 año
            samesite="Lax",
        ),
    }
    return 200, {"message": f"Visit #{visit_count}", "lang": "es"}, response_cookies


@router.get("/cookies/delete")
def delete_cookies(headers):
    """Elimina una cookie estableciendo Max-Age=0."""
    response_cookies = {
        "visits": CookieOptions(value="", max_age=0, path="/"),
    }
    return 200, {"message": "Cookie 'visits' deleted"}, response_cookies


if __name__ == "__main__":
    server = Server(auto_reload=True)
    server.include_router(router)
    server.run(workers=1)
