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
import asyncio as _asyncio
from asyncio.subprocess import PIPE as _PIPE
import html

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

# Создаем диспетчер без бота; бот будет создан в main()
dp = Dispatcher()

# URL удаленного контроллера (опционально). Если не задан, управление локальное
REMOTE_CONTROLLER_URL = (os.getenv("REMOTE_CONTROLLER_URL") or "").strip()
if REMOTE_CONTROLLER_URL.endswith("/"):
    REMOTE_CONTROLLER_URL = REMOTE_CONTROLLER_URL[:-1]

# Git управление через Telegram: список разрешённых user_id (через запятую)
_ids_raw = os.getenv("GIT_ALLOWED_USER_IDS", "")
try:
    GIT_ALLOWED_USER_IDS = {int(x) for x in _ids_raw.replace(" ", "").split(",") if x.strip().isdigit()}
except Exception:
    GIT_ALLOWED_USER_IDS = set()

# Базовые пути для git: можно задать вручную GIT_WORKDIR; иначе будет автоопределение
GIT_WORKDIR = (os.getenv("GIT_WORKDIR") or "").strip()
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# Переопределения git root
# По чату (chat_id -> path) — приоритетнее
CHAT_GIT_ROOT_OVERRIDE: dict[int, str] = {}
# По пользователю (user_id -> path)
GIT_ROOT_OVERRIDE: dict[int, str] = {}

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
        "/model — управление моделью Gemini (list/set/current)\n"
        "/git — управление Git (status/commit/push) — доступ ограничен по user_id\n"
        "/whoami — показать ваш Telegram user_id\n\n"
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


@dp.message(Command(commands=["whoami"]))
async def cmd_whoami(message: types.Message):
    uid = message.from_user.id if message.from_user else None
    uname = message.from_user.username if message.from_user else None
    await message.answer(f"Ваш user_id: {uid}\nusername: @{uname}", reply_markup=main_keyboard)


async def _get_git_root_for(chat_id: int | None, user_id: int | None) -> str:
    """Определить корень git-репозитория.
    Приоритет:
    1) Переопределение чата: /git setroot <path>
    2) Переопределение пользователя: /git setroot_user <path>
    3) GIT_WORKDIR (если каталог существует)
    4) git rev-parse --show-toplevel (cwd=os.getcwd())
    5) git rev-parse --show-toplevel (cwd=REPO_ROOT)
    6) os.getcwd() как fallback
    """
    import shutil, os as _os
    # 1. Переопределение по чату
    if chat_id is not None:
        p = CHAT_GIT_ROOT_OVERRIDE.get(chat_id)
        if p and _os.path.isdir(p):
            return p
    # 2. Переопределение по пользователю
    if user_id is not None:
        p = GIT_ROOT_OVERRIDE.get(user_id)
        if p and _os.path.isdir(p):
            return p
    # 3. Явно заданный путь через env
    if GIT_WORKDIR and _os.path.isdir(GIT_WORKDIR):
        return GIT_WORKDIR
    # 4. Попытка из текущей рабочей директории
    try:
        proc = await _asyncio.create_subprocess_exec(
            "git", "rev-parse", "--show-toplevel",
            cwd=_os.getcwd(), stdout=_PIPE, stderr=_PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode == 0:
            p = (out or b"").decode("utf-8", "ignore").strip()
            if p and _os.path.isdir(p):
                return p
    except Exception:
        pass
    # 5. Попытка из директории файла бота
    try:
        proc = await _asyncio.create_subprocess_exec(
            "git", "rev-parse", "--show-toplevel",
            cwd=REPO_ROOT, stdout=_PIPE, stderr=_PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode == 0:
            p = (out or b"").decode("utf-8", "ignore").strip()
            if p and _os.path.isdir(p):
                return p
    except Exception:
        pass
    # 6. Fallback
    return _os.getcwd()


async def _git_run(args: list[str], cwd: str) -> tuple[int, str, str]:
    """Выполнить git-команду и вернуть (code, stdout, stderr)."""
    try:
        proc = await _asyncio.create_subprocess_exec(
            *args,
            cwd=cwd,
            stdout=_PIPE,
            stderr=_PIPE,
        )
        out, err = await proc.communicate()
        return proc.returncode, (out or b"").decode("utf-8", "ignore"), (err or b"").decode("utf-8", "ignore")
    except Exception as e:
        return 1, "", f"exec error: {e}"


def _git_enabled_for(user_id: int) -> bool:
    return bool(GIT_ALLOWED_USER_IDS) and (user_id in GIT_ALLOWED_USER_IDS)


@dp.message(Command(commands=["git"]))
async def cmd_git(message: types.Message):
    """Управление Git через Telegram.
    Требуется задать env GIT_ALLOWED_USER_IDS=123,456

    Подкоманды:
    /git -> помощь
    /git root
    /git setroot <path>        — задать корень для этого чата
    /git clearroot             — сбросить корень для этого чата
    /git setroot_user <path>   — задать корень персонально для вашего user_id
    /git clearroot_user        — сбросить корень персонально
    /git status
    /git commit <message>
    /git push [remote] [branch]
    """
    user_id = message.from_user.id if message.from_user else None
    if not user_id or not _git_enabled_for(user_id):
        await message.answer(
            "❌ Git-команды отключены. Укажите GIT_ALLOWED_USER_IDS в .env и добавьте свой Telegram user_id.",
            reply_markup=main_keyboard,
        )
        return

    text = (message.text or "").strip()
    parts = text.split()
    if len(parts) == 1:
        help_text = (
            "🛠 Команды Git:\n"
            "• /git root — показать рабочую директорию git\n"
            "• /git setroot <path> — задать корень для этого чата\n"
            "• /git clearroot — сбросить корень для этого чата\n"
            "• /git setroot_user <path> — задать корень персонально для вашего user_id\n"
            "• /git clearroot_user — сбросить персональный корень\n"
            "• /git status — короткий статус и текущая ветка\n"
            "• /git commit <message> — git add -A && git commit -m <message>\n"
            "• /git push [remote] [branch] — по умолчанию origin и текущая ветка\n"
        )
        await message.answer(help_text, reply_markup=main_keyboard)
        return

    sub = parts[1].lower()

    # /git root
    if sub == "root":
        root = await _get_git_root_for(message.chat.id if message.chat else None, message.from_user.id if message.from_user else None)
        await message.answer(f"Текущий git root: {root}", reply_markup=main_keyboard)
        return

    # /git setroot <path>
    if sub == "setroot":
        if len(parts) < 3:
            await message.answer("Укажите путь: /git setroot <path>", reply_markup=main_keyboard)
            return
        path = " ".join(parts[2:]).strip()
        import os as _os
        if not _os.path.isdir(path):
            await message.answer("❌ Путь не существует или не является директорией", reply_markup=main_keyboard)
            return
        # проверяем что это git-репозиторий
        code, out, err = await _git_run(["git", "rev-parse", "--show-toplevel"], cwd=path)
        if code != 0:
            await message.answer("❌ В указанной директории не найден git-репозиторий", reply_markup=main_keyboard)
            return
        CHAT_GIT_ROOT_OVERRIDE[message.chat.id] = path
        await message.answer(f"✅ Корень git для этого чата установлен: {path}", reply_markup=main_keyboard)
        return

    # /git clearroot
    if sub == "clearroot":
        if message.chat and message.chat.id in CHAT_GIT_ROOT_OVERRIDE:
            CHAT_GIT_ROOT_OVERRIDE.pop(message.chat.id, None)
            await message.answer("✅ Корень git для этого чата сброшен", reply_markup=main_keyboard)
        else:
            await message.answer("Корень git для этого чата не установлен", reply_markup=main_keyboard)
        return

    # /git setroot_user <path>
    if sub == "setroot_user":
        if len(parts) < 3:
            await message.answer("Укажите путь: /git setroot_user <path>", reply_markup=main_keyboard)
            return
        path = " ".join(parts[2:]).strip()
        import os as _os
        if not _os.path.isdir(path):
            await message.answer("❌ Путь не существует или не является директорией", reply_markup=main_keyboard)
            return
        code, out, err = await _git_run(["git", "rev-parse", "--show-toplevel"], cwd=path)
        if code != 0:
            await message.answer("❌ В указанной директории не найден git-репозиторий", reply_markup=main_keyboard)
            return
        GIT_ROOT_OVERRIDE[message.from_user.id] = path
        await message.answer(f"✅ Персональный git root установлен: {path}", reply_markup=main_keyboard)
        return

    # /git clearroot_user
    if sub == "clearroot_user":
        if message.from_user and message.from_user.id in GIT_ROOT_OVERRIDE:
            GIT_ROOT_OVERRIDE.pop(message.from_user.id, None)
            await message.answer("✅ Персональный git root сброшен", reply_markup=main_keyboard)
        else:
            await message.answer("Персональный git root не установлен", reply_markup=main_keyboard)
        return

    # /git status
    if sub == "status":
        root = await _get_git_root_for(message.chat.id if message.chat else None, message.from_user.id if message.from_user else None)
        code, out, err = await _git_run(["git", "status", "--porcelain=v1", "-b"], cwd=root)
        out = out.strip() or err.strip() or f"exit={code}"
        if len(out) > 3500:
            out = out[:3500] + "\n... (truncated)"
        await message.answer(f"<pre>{html.escape(out)}</pre>", parse_mode="HTML", reply_markup=main_keyboard)
        return

    # /git commit <message>
    if sub == "commit":
        if len(parts) < 3:
            await message.answer("Укажите сообщение коммита: /git commit <message>", reply_markup=main_keyboard)
            return
        commit_msg = text.split(" ", 2)[2].strip()
        await message.answer("🔄 Выполняю: git add -A; git commit...", reply_markup=main_keyboard)
        root = await _get_git_root_for(message.chat.id if message.chat else None, message.from_user.id if message.from_user else None)
        code1, out1, err1 = await _git_run(["git", "add", "-A"], cwd=root)
        code2, out2, err2 = await _git_run(["git", "commit", "-m", commit_msg], cwd=root)
        summary = (out1 + err1 + "\n" + out2 + err2).strip()
        if len(summary) > 3500:
            summary = summary[:3500] + "\n... (truncated)"
        status = "✅" if code2 == 0 else "⚠️"
        content = summary or f"exit={code1},{code2}"
        await message.answer(f"{status} Результат:\n<pre>{html.escape(content)}</pre>", parse_mode="HTML", reply_markup=main_keyboard)
        return

    # /git push [remote] [branch]
    if sub == "push":
        remote = parts[2] if len(parts) >= 3 else "origin"
        # определяем текущую ветку, если не указана
        if len(parts) >= 4:
            branch = parts[3]
        else:
            root = await _get_git_root_for(message.chat.id if message.chat else None, message.from_user.id if message.from_user else None)
            _, outb, _ = await _git_run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
            branch = (outb.strip() or "main").splitlines()[0]
        await message.answer(f"🔄 Выполняю: git push {remote} {branch}...", reply_markup=main_keyboard)
        root = await _get_git_root_for(message.chat.id if message.chat else None, message.from_user.id if message.from_user else None)
        code, out, err = await _git_run(["git", "push", remote, branch], cwd=root)
        text_out = (out + err).strip()
        if len(text_out) > 3500:
            text_out = text_out[:3500] + "\n... (truncated)"
        status = "✅" if code == 0 else "❌"
        content = text_out or f"exit={code}"
        await message.answer(f"{status} Результат push:\n<pre>{html.escape(content)}</pre>", parse_mode="HTML", reply_markup=main_keyboard)
        return

    await message.answer("Неизвестная подкоманда. Используйте /git для помощи.", reply_markup=main_keyboard)


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
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не задан. Создайте .env и укажите токен.")
        return
    bot = Bot(token=token)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
