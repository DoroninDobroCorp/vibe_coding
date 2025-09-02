import asyncio
import os
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

from ai_processor import ai_processor
from windsurf_controller import desktop_controller
from config import config

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
        # "/calibrate_input - Калибровка поля ввода\n"
        # "/calibrate_button - Калибровка кнопки отправки\n"
        # "/calibrate_response - Калибровка области ответа\n"
        # "/calibrate_confirm - Калибровка кнопки подтверждения\n"
        # "/status - Статус калибровки\n"
        # "/full - Полный ответ\n\n"
        "Просто напишите сообщение чтобы отправить его в Windsurf!",
        reply_markup=main_keyboard,
    )


# @dp.message(Command(commands=["calibrate_input"]))
# async def calibrate_input(message: types.Message):
#     success = desktop_controller.calibrate("input_box")
#     await message.answer("Калибровка поля ввода. Кликните в нужную область..")
#     await asyncio.sleep(5)
#     await message.answer(
#         "✅ Поле ввода откалибровано" if success else "❌ Ошибка калибровки"
#     )
#
#
# @dp.message(Command(commands=["calibrate_button"]))
# async def calibrate_button(message: types.Message):
#     success = desktop_controller.calibrate("send_button")
#     await message.answer("Калибровка кнопки ввода. Кликните в нужную область...")
#     await asyncio.sleep(5)
#     await message.answer(
#         "✅ Кнопка отправки откалибрована" if success else "❌ Ошибка калибровки"
#     )
#
#
# @dp.message(Command(commands=["calibrate_response"]))
# async def calibrate_response(message: types.Message):
#     success = desktop_controller.calibrate("response_area")
#     await message.answer("Калибровка поля вывода. Кликните в нужную область...")
#     await asyncio.sleep(5)
#     await message.answer(
#         "✅ Область ответа откалибрована" if success else "❌ Ошибка калибровки"
#     )
#
#
# @dp.message(Command(commands=["calibrate_confirm"]))
# async def calibrate_confirm(message: types.Message):
#     success = desktop_controller.calibrate("confirm_button")
#     await message.answer(
#         "Калибровка кнопки подтверждения. Кликните в нужную область..."
#     )
#     await asyncio.sleep(5)
#     await message.answer(
#         "✅ Кнопка подтверждения откалибрована" if success else "❌ Ошибка калибровки"
#     )
#
#
# @dp.message(Command(commands=["status"]))
# async def status(message: types.Message):
#     status_text = "Статус калибровки:\n"
#     status_text += (
#         f"Поле ввода: {'✅' if config.calibration_data['input_box'] else '❌'}\n"
#     )
#     status_text += (
#         f"Кнопка отправки: {'✅' if config.calibration_data['send_button'] else '❌'}\n"
#     )
#     status_text += f"Область ответа: {'✅' if config.calibration_data['response_area'] else '❌'}\n"
#
#     if desktop_controller.is_calibrated():
#         status_text += "\n🎯 Система готова к работе!"
#     else:
#         status_text += "\n⚠️ Требуется калибровка всех элементов"
#
#     await message.answer(status_text)
#
#
# @dp.message(Command(commands=["full"]))
# async def get_full_response(message: types.Message):
#     # Ждем и получаем ответ
#     user_id = message.from_user.id
#     if user_id not in user_states:
#         user_states[user_id] = {
#             "last_full_response": None,
#             "last_updated": datetime.utcnow(),
#         }
#     else:
#         # Очищаем старые данные (1 час)
#         if datetime.utcnow() - user_states[user_id]["last_updated"] > timedelta(
#             hours=1
#         ):
#             user_states[user_id]["last_full_response"] = None
#     full_response = user_states[user_id]["last_full_response"]
#
#     # Разбиваем длинное сообщение на части
#     if full_response:
#         for i in range(0, len(full_response), 4096):
#             await message.answer(full_response[i: i + 4096])
#     else:
#         await message.answer("Нет сохраненного ответа")


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
            await message.answer("❌ Ошибка при отправке сообщения")
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
            await message.answer("❌ Не удалось получить ответ из буфера обмена")

        # # Закомментированный блок OCR обработки
        # await message.answer("⏳ Ожидаю ответа от Windsurf...")
        # full_response = await desktop_controller.get_response(wait_time=15)
        # user_id = message.from_user.id
        # if user_id not in user_states:
        #     user_states[user_id] = {}
        # user_states[user_id]["last_full_response"] = full_response
        # user_states[user_id]["last_updated"] = datetime.utcnow()
        # try:
        #     summary = ai_processor.summarize(full_response)
        #     await message.answer(
        #         f"✅ Ответ получен:\n\n{summary}\n\n"
        #         f"Используйте /full для полной версии",
        #         reply_markup=main_keyboard,
        #     )
        # except Exception as e:
        #     logger.error(f"Error: {e}")
        #     await message.answer(f"✅ Ответ получен: {full_response[:100]}")

    except Exception as e:
        logger.error(f"Error: {e}")
        await message.answer("❌ Произошла ошибка при обработке запроса")


async def main():
    logger.info("Starting Windsurf Bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
