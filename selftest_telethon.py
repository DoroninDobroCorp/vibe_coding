import asyncio
import logging
import os
import time
from types import SimpleNamespace

from dotenv import load_dotenv

# Настроим детальный лог
load_dotenv()
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger("selftest")

# Безопасный режим переключения модели в UI (не трогаем клавиатуру/окна)
os.environ.setdefault('WSMODEL_DRY_RUN', '1')

# Импортируем наш бот и контроллер
import telethon_bot as tb  # type: ignore
from windsurf_controller import desktop_controller


class DummySender:
    def __init__(self, id: int, username: str | None = None):
        self.id = id
        self.username = username


class DummyEvent:
    def __init__(self, raw_text: str, sender_id: int = 123456789, username: str | None = "tester"):
        self.raw_text = raw_text
        self.sender_id = sender_id
        self._sender = DummySender(sender_id, username)
        self._responses: list[str] = []

    async def respond(self, text: str):
        logger.info(f"[respond] {text[:1200]}")
        self._responses.append(text)

    async def get_sender(self):
        return self._sender

    @property
    def responses(self):
        return self._responses


async def run_once():
    ok = True

    # /whoami
    ev = DummyEvent("/whoami", sender_id=111222333, username="selftest")
    await tb.handle_whoami(ev)
    if not ev.responses or "Ваш user_id: 111222333" not in ev.responses[0]:
        logger.error("whoami: unexpected response")
        ok = False

    # /status
    ev = DummyEvent("/status")
    await tb.handle_status(ev)
    s = "\n".join(ev.responses)
    if "Статус системы:" not in s or "last_ready_pixel" not in s:
        logger.error("status: missing key sections")
        ok = False

    # /windows
    ev = DummyEvent("/windows")
    await tb.handle_windows(ev)
    s = "\n".join(ev.responses)
    if not ("Окна Windsurf:" in s or "Окон Windsurf не найдено" in s):
        logger.error("windows: unexpected response")
        ok = False

    # /model current
    ev = DummyEvent("/model current")
    await tb.handle_model(ev)
    s = "\n".join(ev.responses)
    if "Текущая модель:" not in s:
        logger.error("model current: unexpected response")
        ok = False

    # /model list
    ev = DummyEvent("/model list")
    await tb.handle_model(ev)
    s = "\n".join(ev.responses)
    if not ("Доступные модели:" in s or "Список моделей пуст" in s):
        logger.error("model list: unexpected response")
        ok = False

    # /model set <same as current> (чтобы не падать)
    current = tb.ai_processor.get_model_name() or "gemini-2.5-flash"
    ev = DummyEvent(f"/model set {current}")
    await tb.handle_model(ev)
    s = "\n".join(ev.responses)
    if not ("✅" in s or "Модель установлена" in s or "Ошибка" in s or "GEMINI_API_KEY" in s):
        logger.error("model set: unexpected response")
        ok = False

    # /wsmodel set <name> (dry-run)
    ev = DummyEvent("/wsmodel set DeepSeek R1")
    await tb.handle_wsmodel(ev)
    s = "\n".join(ev.responses)
    if not ("✅" in s or "(dry-run)" in s or "Модель переключена" in s):
        logger.error("wsmodel set (active): unexpected response")
        ok = False

    # /wsmodel set [#1] <name> (dry-run, с таргетом)
    ev = DummyEvent("/wsmodel set [#1] Gemini 2.5 Pro")
    await tb.handle_wsmodel(ev)
    s = "\n".join(ev.responses)
    if not ("✅" in s or "(dry-run)" in s or "Модель переключена" in s):
        logger.error("wsmodel set [#1]: unexpected response")
        ok = False

    return ok


def main():
    logger.info("Starting Telethon-bot selftest...")
    t0 = time.time()
    try:
        ok = asyncio.run(run_once())
    except Exception as e:
        logger.exception(f"selftest raised: {e}")
        ok = False
    # Держим процесс ~10 сек для наблюдения за логами, если требуется
    rest = 10 - (time.time() - t0)
    if rest > 0:
        logger.info(f"Sleeping {rest:.1f}s to observe logs...")
        time.sleep(rest)
    if ok:
        logger.info("Selftest: OK")
        return 0
    logger.error("Selftest: FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
