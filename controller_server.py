import asyncio
import json
import logging
import os
from aiohttp import web
from dotenv import load_dotenv

from windsurf_controller import desktop_controller
import pyperclip

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("controller_server")


async def windows(request: web.Request) -> web.Response:
    titles = desktop_controller.list_windows()
    return web.json_response({"windows": titles})


async def send(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    message = data.get("message")
    target = data.get("target")
    if not isinstance(message, str) or not message.strip():
        return web.json_response({"ok": False, "error": "message_required"}, status=400)

    ok = await desktop_controller.send_message_to(target, message) if target else await desktop_controller.send_message(message)
    diag = desktop_controller.get_diagnostics()

    # Помощник для детекции эхо
    def _looks_like_echo(original: str, copied: str) -> bool:
        try:
            o = (original or "").strip()
            c = (copied or "").strip()
            if not o or not c:
                return False
            prefix = o[: min(24, len(o))]
            if c.startswith(prefix):
                if len(c) <= max(len(o) + 32, int(len(o) * 1.2)):
                    return True
            return False
        except Exception:
            return False

    # Пытаемся вернуть текст из буфера обмена (ответ ИИ) — best-effort
    response_text = None
    try:
        clip = pyperclip.paste()
        if isinstance(clip, str) and clip.strip():
            # Фильтрация эхо, если это копия вопроса
            if _looks_like_echo(str(message), clip):
                diag["response_is_echo"] = True
                response_text = None
            else:
                diag["response_is_echo"] = False
                response_text = clip
    except Exception:
        response_text = None
    return web.json_response({"ok": bool(ok), "diag": diag, "response": response_text})


async def health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def app_factory() -> web.Application:
    app = web.Application()
    app.add_routes([
        web.get("/health", health),
        web.get("/windows", windows),
        web.post("/send", send),
    ])
    return app


def main():
    host = os.getenv("CONTROLLER_HOST", "127.0.0.1")
    port = int(os.getenv("CONTROLLER_PORT", "8089"))
    logger.info(f"Starting controller server on http://{host}:{port}")
    web.run_app(asyncio.run(app_factory()), host=host, port=port)


if __name__ == "__main__":
    main()
