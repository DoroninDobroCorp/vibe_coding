import asyncio
import os
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

from windsurf_controller import desktop_controller

# Используйте для запуска в терминале taskkill /f /im python.exe; Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'z:\Dev\vibe\vibe_coding'; python bot.py"

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
dp = Dispatcher(bot=bot)

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
        [KeyboardButton(text="/status")],
        # [KeyboardButton(text="/full")],
    ],
    resize_keyboard=True,
)


@dp.message(CommandStart())
async def start_command(message: types.Message):
    await message.answer(
        "🤖 Бот для работы с Windsurf Desktop\n\n"
        "Команды:\n"
        "/status — статус диагностики и параметров\n\n"
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
    ]
    await message.answer("\n".join(status_lines), reply_markup=main_keyboard)


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
        # Отправляем сообщение в Windsurf
        await message.answer("🔄 Отправляю запрос в Windsurf...")
        success = await desktop_controller.send_message(user_input)

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

        # Получаем скопированный ответ из буфера обмена
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
