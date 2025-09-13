import asyncio
import os
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
from typing import Optional, List

from windsurf_controller import desktop_controller
from ai_processor import ai_processor
import aiohttp

# Используйте для запуска в терминале taskkill /f /im python.exe; Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'z:\Dev\vibe\vibe_coding'; python bot.py"

load_dotenv()


async def remote_list_windows(session: aiohttp.ClientSession) -> List[str]:
    """Получить список окон с удалённого контроллера"""
    if not REMOTE_CONTROLLER_URL:
        return []
    async with session.get(f"{REMOTE_CONTROLLER_URL}/windows", timeout=10) as resp:
        data = await resp.json()
        return data.get("windows", [])


async def remote_send(session: aiohttp.ClientSession, message: str, target: Optional[str] = None) -> tuple[bool, Optional[str]]:
    """Отправить сообщение через удалённый контроллер. Возвращает (ok, response_text)."""
    if not REMOTE_CONTROLLER_URL:
        return False, None
    payload = {"message": message}
    if target:
        payload["target"] = target
    async with session.post(f"{REMOTE_CONTROLLER_URL}/send", json=payload, timeout=20) as resp:
        data = await resp.json()
        return bool(data.get("ok")), data.get("response")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
dp = Dispatcher(bot=bot)

# URL удаленного контроллера (опционально). Если не задан, управление локальное
REMOTE_CONTROLLER_URL = (os.getenv("REMOTE_CONTROLLER_URL") or "").strip()
if REMOTE_CONTROLLER_URL.endswith("/"):
    REMOTE_CONTROLLER_URL = REMOTE_CONTROLLER_URL[:-1]

# Глобальное хранилище состояний
user_states = (
    {}
)  # Формат: {user_id: {'last_full_response': str, 'last_updated': datetime}}

# Клавиатура для быстрых команд
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        # [
        #     KeyboardButton(text="/calibrate_input"),
        #     KeyboardButton(text="/calibrate_button"),
        # ],
        # [
        #     KeyboardButton(text="/calibrate_response"),
        #     KeyboardButton(text="/calibrate_confirm"),
        # ],
        [KeyboardButton(text="/status"), KeyboardButton(text="/windows")],
        # [KeyboardButton(text="/full")],
    ],
    resize_keyboard=True,
)


@dp.message(CommandStart())
async def start_command(message: types.Message):
    await message.answer(
        "🤖 Бот для работы с Windsurf Desktop\n\n"
        "Команды:\n"
        "/status — статус диагностики и параметров\n"
        "/model — управление моделью Gemini (list/set/current)\n\n"
        "Просто напишите сообщение, чтобы отправить его в Windsurf!",
        reply_markup=main_keyboard,
    )



@dp.message(Command(commands=["status"]))
async def status(message: types.Message):
    diag = desktop_controller.get_diagnostics()
    status_lines = [
        "📊 Статус системы:",
        f"Платформа: {diag.get('platform')}",
        f"Windsurf процессов: {len(diag.get('windsurf_pids', []))} — {diag.get('windsurf_pids')}",
        f"Windows automation: {'✅' if diag.get('windows_automation') else '❌'}",
        f"Успешных отправок: {diag.get('success_sends')}",
        f"Неуспешных отправок: {diag.get('failed_sends')}",
        f"Последняя ошибка: {diag.get('last_error') or '—'}",
        "",
        "Параметры:",
        f"RESPONSE_WAIT_SECONDS={diag.get('RESPONSE_WAIT_SECONDS')}",
        f"PASTE_RETRY_COUNT={diag.get('PASTE_RETRY_COUNT')}",
        f"COPY_RETRY_COUNT={diag.get('COPY_RETRY_COUNT')}",
        "",
        "AI:",
        f"Gemini модель: {ai_processor.get_model_name() or '—'}",
        f"REMOTE_CONTROLLER_URL: {'вкл' if REMOTE_CONTROLLER_URL else '—'}",
    ]
    await message.answer("\n".join(status_lines), reply_markup=main_keyboard)


@dp.message(Command(commands=["windows"]))
async def windows(message: types.Message):
    if REMOTE_CONTROLLER_URL:
        try:
            async with aiohttp.ClientSession() as session:
                titles = await remote_list_windows(session)
        except Exception as e:
            await message.answer(f"Ошибка запроса удаленного контроллера: {e}")
            return
    else:
        titles = desktop_controller.list_windows()
    if not titles:
        await message.answer("Окон Windsurf не найдено или платформа не поддерживает перечисление.", reply_markup=main_keyboard)
        return
    lines = ["🪟 Окна Windsurf:"]
    for i, t in enumerate(titles, start=1):
        lines.append(f"#{i}: {t}")
    lines.append("\nОтправляйте с префиксом: [#N] ваш текст или [@часть_заголовка] ваш текст")
    await message.answer("\n".join(lines), reply_markup=main_keyboard)


@dp.message(Command(commands=["model"]))
async def cmd_model(message: types.Message):
    """Управление моделью Gemini через Telegram
    Примеры:
    /model -> помощь
    /model current
    /model list [filter]
    /model set gemini-2.5-pro
    """
    text = (message.text or "").strip()
    parts = text.split()
    if len(parts) == 1:
        help_text = (
            "⚙️ Управление моделью Gemini:\n"
            "• /model current — показать текущую модель\n"
            "• /model list — список доступных моделей\n"
            "• /model list pro — список, фильтр по подстроке\n"
            "• /model set <name> — установить модель\n"
        )
        await message.answer(help_text, reply_markup=main_keyboard)
        return

    sub = parts[1].lower()

    if sub == "current":
        await message.answer(f"Текущая модель: {ai_processor.get_model_name() or '—'}", reply_markup=main_keyboard)
        return

    if sub == "list":
        models = ai_processor.list_models()
        if len(parts) >= 3:
            filt = " ".join(parts[2:]).lower()
            models = [m for m in models if filt in m.lower()]
        if not models:
            await message.answer("Список моделей пуст", reply_markup=main_keyboard)
            return
        lines = ["📚 Доступные модели:"] + [f"• {m}" for m in models[:100]]
        await message.answer("\n".join(lines), reply_markup=main_keyboard)
        return

    if sub == "set" and len(parts) >= 3:
        new_model = " ".join(parts[2:]).strip()
        ok, msg = ai_processor.set_model(new_model)
        prefix = "✅" if ok else "❌"
        await message.answer(f"{prefix} {msg}", reply_markup=main_keyboard)
        return

    await message.answer("Неизвестная подкоманда. Используйте /model для помощи.", reply_markup=main_keyboard)


@dp.message()
async def handle_message(message: types.Message):
    user_input = message.text.strip()

    # Пропускаем команды
    if user_input.startswith("/"):
        return

    # if not desktop_controller.is_calibrated():
    #     await message.answer(
    #         "⚠️ Система не откалибрована. Используйте команды калибровки"
    #     )
    #     return

    try:
        # Парсинг таргета окна: [#N] или [@title]
        target = None
        text = user_input
        if user_input.startswith("[#"):
            try:
                close = user_input.find("]")
                num = int(user_input[2:close])
                target = f"index:{num}"
                text = user_input[close + 1 :].strip()
            except Exception:
                pass
        elif user_input.startswith("[@"):
            try:
                close = user_input.find("]")
                title = user_input[2:close]
                target = title.strip()
                text = user_input[close + 1 :].strip()
            except Exception:
                pass

        # Отправляем сообщение в Windsurf
        await message.answer("🔄 Отправляю запрос в Windsurf...")
        copied_response = None
        if REMOTE_CONTROLLER_URL:
            try:
                async with aiohttp.ClientSession() as session:
                    success, copied_response = await remote_send(session, text, target)
            except Exception as e:
                success = False
                copied_response = None
        else:
            if target:
                success = await desktop_controller.send_message_to(target, text)
            else:
                success = await desktop_controller.send_message(text)

        if not success:
            diag = desktop_controller.get_diagnostics()
            reason = diag.get("last_error") or "Неизвестно"
            await message.answer(
                "❌ Ошибка при отправке сообщения\n"
                f"Причина: {reason}\n"
                f"Платформа: {diag.get('platform')}\n"
                f"Windsurf процессов: {len(diag.get('windsurf_pids', []))}",
                reply_markup=main_keyboard,
            )
            return

        # Получаем скопированный ответ из буфера обмена (локально) или из удаленного ответа
        if copied_response is None:
            import pyperclip
            copied_response = pyperclip.paste()
        
        if copied_response and copied_response.strip():
            await message.answer(
                f"✅ Ответ от Windsurf:\n\n{copied_response}",
                reply_markup=main_keyboard,
            )
        else:
            await message.answer(
                "⚠️ Ответ не удалось получить из буфера обмена. Попробуйте еще раз или проверьте, что окно Windsurf активно.",
                reply_markup=main_keyboard,
            )

        # OCR/калибровка удалены из проекта, поэтому дополнительные блоки не используются

    except Exception as e:
        logger.error(f"Error: {e}")
        await message.answer("❌ Произошла ошибка при обработке запроса")


async def main():
    logger.info("Starting Windsurf Bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
