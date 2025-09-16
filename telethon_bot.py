import asyncio
import logging
import os
from typing import Optional, List

from dotenv import load_dotenv
from telethon import TelegramClient, events

from windsurf_controller import desktop_controller
from ai_processor import ai_processor


load_dotenv()

# Логирование
_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, _LOG_LEVEL, logging.INFO))
logger = logging.getLogger("telethon_bot")


def _chunk_text(text: str, max_len: int = 4096) -> List[str]:
    chunks: List[str] = []
    remaining = text or ""
    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]
    return chunks


async def send_chunks(event: events.NewMessage.Event, text: str):
    if not text:
        return
    chunks = _chunk_text(text)
    logger.info(f"[send_chunks] sending {len(chunks)} chunk(s), total_len={len(text)}")
    for i, chunk in enumerate(chunks):
        logger.debug(f"[send_chunks] chunk {i+1}/{len(chunks)} len={len(chunk)}")
        await event.respond(chunk)


def _status_text() -> str:
    diag = desktop_controller.get_diagnostics()
    lines = [
        "📊 Статус системы:",
        f"Платформа: {diag.get('platform')}",
        f"Windsurf процессов: {len(diag.get('windsurf_pids', []))} — {diag.get('windsurf_pids')}",
        f"Windows automation: {'✅' if diag.get('windows_automation') else '❌'}",
        f"Успешных отправок: {diag.get('success_sends')}",
        f"Неуспешных отправок: {diag.get('failed_sends')}",
        f"Последняя ошибка: {diag.get('last_error') or '—'}",
        f"last_paste_strategy: {diag.get('last_paste_strategy') or '—'}",
        f"last_copy_method: {diag.get('last_copy_method') or '—'}",
        f"last_copy_length: {diag.get('last_copy_length')}",
        f"last_copy_is_echo: {diag.get('last_copy_is_echo')}",
        f"response_wait_loops: {diag.get('response_wait_loops')}",
        f"response_ready_time: {diag.get('response_ready_time')}s",
        f"response_stabilized: {diag.get('response_stabilized')}",
        f"response_stabilized_by: {diag.get('response_stabilized_by')}",
        f"last_ui_button: {diag.get('last_ui_button')}",
        f"last_ui_avg_color: {diag.get('last_ui_avg_color')}",
        f"last_visual_region: {diag.get('last_visual_region')}",
        f"last_click_xy: {diag.get('last_click_xy')}",
        f"last_ready_pixel: {diag.get('last_ready_pixel')}",
        f"last_model_set: {diag.get('last_model_set')}",
        f"cpu_quiet_seconds: {diag.get('cpu_quiet_seconds')}",
        f"cpu_last_total_percent: {diag.get('cpu_last_total_percent')}",
        "",
        "Параметры:",
        f"RESPONSE_WAIT_SECONDS={diag.get('RESPONSE_WAIT_SECONDS')}",
        f"RESPONSE_MAX_WAIT_SECONDS={diag.get('RESPONSE_MAX_WAIT_SECONDS')}",
        f"RESPONSE_POLL_INTERVAL_SECONDS={diag.get('RESPONSE_POLL_INTERVAL_SECONDS')}",
        f"RESPONSE_STABLE_MIN_SECONDS={diag.get('RESPONSE_STABLE_MIN_SECONDS')}",
        f"PASTE_RETRY_COUNT={diag.get('PASTE_RETRY_COUNT')}",
        f"COPY_RETRY_COUNT={diag.get('COPY_RETRY_COUNT')}",
        f"USE_UI_BUTTON_DETECTION={os.getenv('USE_UI_BUTTON_DETECTION')}",
        f"SEND_BTN_REGION_RIGHT={os.getenv('SEND_BTN_REGION_RIGHT')}",
        f"SEND_BTN_REGION_BOTTOM={os.getenv('SEND_BTN_REGION_BOTTOM')}",
        f"SEND_BTN_REGION_W={os.getenv('SEND_BTN_REGION_W')}",
        f"SEND_BTN_REGION_H={os.getenv('SEND_BTN_REGION_H')}",
        f"SEND_BTN_BLUE_DELTA={os.getenv('SEND_BTN_BLUE_DELTA')}",
        f"SEND_BTN_WHITE_BRIGHT={os.getenv('SEND_BTN_WHITE_BRIGHT')}",
        f"USE_VISUAL_STABILITY={os.getenv('USE_VISUAL_STABILITY')}",
        f"VISUAL_REGION_TOP={os.getenv('VISUAL_REGION_TOP')}",
        f"VISUAL_REGION_BOTTOM={os.getenv('VISUAL_REGION_BOTTOM')}",
        f"VISUAL_SAMPLE_INTERVAL_SECONDS={os.getenv('VISUAL_SAMPLE_INTERVAL_SECONDS')}",
        f"VISUAL_DIFF_THRESHOLD={os.getenv('VISUAL_DIFF_THRESHOLD')}",
        f"VISUAL_STABLE_SECONDS={os.getenv('VISUAL_STABLE_SECONDS')}",
        f"SAVE_VISUAL_DEBUG={os.getenv('SAVE_VISUAL_DEBUG')}",
        f"SAVE_VISUAL_DIR={os.getenv('SAVE_VISUAL_DIR')}",
        f"RIGHT_CLICK_X_FRACTION={os.getenv('RIGHT_CLICK_X_FRACTION')}",
        f"RIGHT_CLICK_Y_OFFSET={os.getenv('RIGHT_CLICK_Y_OFFSET')}",
        f"USE_COPY_SHORT_FALLBACK={os.getenv('USE_COPY_SHORT_FALLBACK')}",
        f"USE_READY_PIXEL={os.getenv('USE_READY_PIXEL')}",
        f"READY_PIXEL_REQUIRED={os.getenv('READY_PIXEL_REQUIRED')}",
        f"READY_PIXEL_SRC={os.getenv('READY_PIXEL_SRC')}",
        f"READY_PIXEL_AVG_K={os.getenv('READY_PIXEL_AVG_K')}",
        f"READY_PIXEL_REQUIRE_TRANSITION={os.getenv('READY_PIXEL_REQUIRE_TRANSITION')}",
        f"READY_PIXEL_STABLE_SECONDS={os.getenv('READY_PIXEL_STABLE_SECONDS')}",
        f"READY_PIXEL_TRANSITION_TIMEOUT_SECONDS={os.getenv('READY_PIXEL_TRANSITION_TIMEOUT_SECONDS')}",
        f"READY_PIXEL=(x={os.getenv('READY_PIXEL_X')}, y={os.getenv('READY_PIXEL_Y')}, rgb=({os.getenv('READY_PIXEL_R')},{os.getenv('READY_PIXEL_G')},{os.getenv('READY_PIXEL_B')}), tol={os.getenv('READY_PIXEL_TOL')}, tol_pct={os.getenv('READY_PIXEL_TOL_PCT')})",
        f"ANSWER_ABS=(x={os.getenv('ANSWER_ABS_X')}, y={os.getenv('ANSWER_ABS_Y')})",
        f"INPUT_ABS=(x={os.getenv('INPUT_ABS_X')}, y={os.getenv('INPUT_ABS_Y')})",
        "",
        "AI:",
        f"Gemini модель: {ai_processor.get_model_name() or '—'}",
    ]
    return "\n".join(lines)


async def handle_start(event: events.NewMessage.Event):
    logger.info("Handling /start")
    text = (
        "🤖 Бот для работы с Windsurf Desktop\n\n"
        "Команды:\n"
        "/status — статус диагностики и параметров\n"
        "/model — управление моделью API (list/set/current)\n"
        "/wsmodel set [#N|@sub] <name> — переключить модель в UI Windsurf (Cmd+/ → ввести → Enter)\n"
        "/whoami — показать ваш Telegram user_id\n"
        "/windows — список окон Windsurf (macOS)\n\n"
        "Просто напишите сообщение, чтобы отправить его в Windsurf!"
    )
    await send_chunks(event, text)


async def handle_status(event: events.NewMessage.Event):
    logger.info("Handling /status")
    await send_chunks(event, _status_text())


async def handle_windows(event: events.NewMessage.Event):
    logger.info("Handling /windows")
    titles = desktop_controller.list_windows()
    if not titles:
        await event.respond("Окон Windsurf не найдено или платформа не поддерживает перечисление.")
        return
    lines = ["🪟 Окна Windsurf:"]
    for i, t in enumerate(titles, start=1):
        lines.append(f"#{i}: {t}")
    lines.append("\nОтправляйте с префиксом: [#N] ваш текст или [@часть_заголовка] ваш текст")
    await send_chunks(event, "\n".join(lines))


async def handle_model(event: events.NewMessage.Event):
    logger.info("Handling /model")
    text = (event.raw_text or "").strip()
    parts = text.split()
    if len(parts) == 1:
        help_text = (
            "⚙️ Управление моделью API (через ai_processor):\n"
            "• /model current — показать текущую модель\n"
            "• /model list — список доступных моделей\n"
            "• /model list pro — список, фильтр по подстроке\n"
            "• /model set <name> — установить модель\n"
            "\nДля переключения модели в UI Windsurf используйте: /wsmodel set [#N|@sub] <name>"
        )
        await send_chunks(event, help_text)
        return

    sub = parts[1].lower()
    if sub == "current":
        logger.debug("/model current")
        await event.respond(f"Текущая модель: {ai_processor.get_model_name() or '—'}")
        return

    if sub == "list":
        logger.debug("/model list")
        models = ai_processor.list_models()
        if len(parts) >= 3:
            filt = " ".join(parts[2:]).lower()
            models = [m for m in models if filt in m.lower()]
        if not models:
            await event.respond("Список моделей пуст")
            return
        lines = ["📚 Доступные модели:"] + [f"• {m}" for m in models[:100]]
        await send_chunks(event, "\n".join(lines))
        return

    if sub == "set" and len(parts) >= 3:
        new_model = " ".join(parts[2:]).strip()
        logger.debug(f"/model set -> {new_model}")
        ok, msg = ai_processor.set_model(new_model)
        prefix = "✅" if ok else "❌"
        await event.respond(f"{prefix} {msg}")
        return

    await event.respond("Неизвестная подкоманда. Используйте /model для помощи.")


def _parse_target_prefix(s: str) -> tuple[Optional[str], str]:
    """Парсинг префикса [#N] или [@substr] в начале строки. Возвращает (target, rest)."""
    import re
    s = s.strip()
    m = re.match(r"^\[(#\d+|@[^\]]+)\]\s*(.*)$", s)
    if not m:
        return None, s
    token = m.group(1)
    rest = m.group(2).strip()
    if token.startswith('#') and token[1:].isdigit():
        return f"index:{int(token[1:])}", rest
    if token.startswith('@'):
        return token[1:], rest
    return None, s


async def handle_wsmodel(event: events.NewMessage.Event):
    logger.info("Handling /wsmodel")
    text = (event.raw_text or "").strip()
    parts = text.split(maxsplit=2)
    if len(parts) < 2:
        await event.respond(
            "⚙️ Переключение модели в UI Windsurf:\n"
            "• /wsmodel set <name> — активное окно\n"
            "• /wsmodel set [#N] <name> — окно по индексу в /windows\n"
            "• /wsmodel set [@часть_заголовка] <name> — окно по части заголовка\n"
            "Принцип: Cmd+/ → ввести <name> → Enter"
        )
        return
    sub = parts[1].lower()
    if sub != 'set':
        await event.respond("Неизвестная подкоманда. Используйте /wsmodel set ...")
        return
    if len(parts) < 3:
        await event.respond("Укажите имя модели: /wsmodel set <name>")
        return
    payload = parts[2]
    target, name = _parse_target_prefix(payload)
    if not name:
        await event.respond("Пустое имя модели")
        return
    ok, msg = desktop_controller.set_model_ui(name, target or "active")
    prefix = "✅" if ok else "❌"
    await event.respond(f"{prefix} {msg}")


async def handle_whoami(event: events.NewMessage.Event):
    logger.info("Handling /whoami")
    try:
        sender = await event.get_sender()
        uid = getattr(sender, 'id', None)
        uname = getattr(sender, 'username', None)
    except Exception:
        sender = None
        uid = event.sender_id
        uname = None
    await event.respond(f"Ваш user_id: {uid}\nusername: @{uname}")


async def main_async():
    api_id = int(os.getenv("TELEGRAM_API_ID", "0"))
    api_hash = os.getenv("TELEGRAM_API_HASH")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    session_name = (os.getenv("TELETHON_SESSION_NAME") or "windsurf_telethon_bot").strip() or "windsurf_telethon_bot"
    if not api_id or not api_hash or not bot_token:
        logger.error("TELEGRAM_API_ID, TELEGRAM_API_HASH или TELEGRAM_BOT_TOKEN не заданы в .env")
        return

    client = TelegramClient(session_name, api_id, api_hash)
    await client.connect()
    try:
        authorized = await client.is_user_authorized()
    except Exception:
        authorized = False
    if not authorized:
        logger.info("Bot session not authorized, signing in with bot token...")
        await client.sign_in(bot_token=bot_token)
    else:
        logger.info("Reusing existing authorized bot session")

    # Регистрация обработчиков
    client.add_event_handler(handle_start, events.NewMessage(pattern=r"^/start(?:@\w+)?$"))
    client.add_event_handler(handle_status, events.NewMessage(pattern=r"^/status(?:@\w+)?$"))
    client.add_event_handler(handle_windows, events.NewMessage(pattern=r"^/windows(?:@\w+)?$"))
    client.add_event_handler(handle_model, events.NewMessage(pattern=r"^/model(?:\b.*)?$"))
    client.add_event_handler(handle_wsmodel, events.NewMessage(pattern=r"^/wsmodel(?:\b.*)?$"))
    client.add_event_handler(handle_whoami, events.NewMessage(pattern=r"^/whoami(?:@\w+)?$"))

    logger.info("Telethon бот запущен. Ожидаю команды…")

    # Опционально авто-стоп через BOT_RUN_SECONDS (для healthcheck 10 сек)
    run_for = 0
    try:
        run_for = int(float(os.getenv("BOT_RUN_SECONDS", "0")))
    except Exception:
        run_for = 0

    if run_for > 0:
        async def _stopper():
            await asyncio.sleep(run_for)
            logger.info(f"Останавливаю Telethon бота по таймеру {run_for}s…")
            await client.disconnect()
        asyncio.create_task(_stopper())

    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass
