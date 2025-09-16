import asyncio
import os
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.exceptions import TelegramNetworkError
from dotenv import load_dotenv
from typing import Optional, List

from windsurf_controller import desktop_controller
from mac_window_manager import MacWindowManager
from ai_processor import ai_processor
import asyncio as _asyncio
from asyncio.subprocess import PIPE as _PIPE
import html

# Используйте для запуска в терминале taskkill /f /im python.exe; Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'z:\Dev\vibe\vibe_coding'; python bot.py"

load_dotenv()


async def answer_chunks(message: types.Message, text: str, parse_mode: Optional[str] = None, reply_markup: Optional[ReplyKeyboardMarkup] = None):
    """Безопасная отправка длинных сообщений (разбиение по 4096 символов).
    Ставит клавиатуру только к первому сообщению, чтобы не дублировать её в чате.
    """
    if text is None:
        return
    max_len = 4096
    remaining = text
    first = True
    while remaining:
        if len(remaining) <= max_len:
            chunk = remaining
            remaining = ""
        else:
            # стараемся резать по переводу строки
            split_at = remaining.rfind("\n", 0, max_len)
            if split_at == -1:
                split_at = max_len
            chunk = remaining[:split_at]
            remaining = remaining[split_at:]
        # Пару повторных попыток на случай кратковременного обрыва соединения
        attempts = 0
        while True:
            try:
                await message.answer(chunk, parse_mode=parse_mode, reply_markup=(reply_markup if first else None))
                break
            except TelegramNetworkError as e:
                attempts += 1
                if attempts <= 2:
                    logger.warning(f"answer_chunks retry {attempts} after TelegramNetworkError: {e}")
                    try:
                        await asyncio.sleep(0.7)
                    except Exception:
                        pass
                    continue
                logger.warning(f"answer_chunks give up after {attempts} attempts: {e}")
                return
        first = False



import logging
# Настройка логов по .env: LOG_LEVEL (DEBUG/INFO/WARNING/ERROR)
_lvl_name = os.getenv('LOG_LEVEL', 'WARNING').upper()
_lvl = getattr(logging, _lvl_name, logging.WARNING)
logging.basicConfig(level=_lvl)
# Уровни логов для библиотек: уважать LOG_LEVEL
_lib_level = _lvl if _lvl <= logging.INFO else logging.WARNING
logging.getLogger('aiogram').setLevel(_lib_level)
logging.getLogger('aiohttp').setLevel(_lib_level)
logging.getLogger('windsurf_controller').setLevel(_lib_level)
logger = logging.getLogger(__name__)
logger.setLevel(_lvl)

# Создаем диспетчер без бота; бот будет создан в main()
dp = Dispatcher()

REMOTE_CONTROLLER_URL = ""

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
    try:
        await message.answer(
            "🤖 Бот для работы с Windsurf Desktop\n\n"
            "Команды:\n"
            "/status — статус диагностики и параметров\n"
            "/model — управление моделью API (list/set/current)\n"
            "/wsmodel set [#N|@sub] <name> — переключить модель в UI Windsurf (Cmd+/ → ввести → Enter)\n"
            "/git — управление Git (status/commit/push) — доступ ограничен по user_id\n"
            "/whoami — показать ваш Telegram user_id\n\n"
            "Просто напишите сообщение, чтобы отправить его в Windsurf!",
            reply_markup=main_keyboard,
        )
    except TelegramNetworkError as e:
        logger.warning(f"/start answer failed: {e}")



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
        f"READY_PIXEL=(x={os.getenv('READY_PIXEL_X')}, y={os.getenv('READY_PIXEL_Y')}, rgb=({os.getenv('READY_PIXEL_R')},{os.getenv('READY_PIXEL_G')},{os.getenv('READY_PIXEL_B')}), tol={os.getenv('READY_PIXEL_TOL')})",
        f"CLICK_ABS=(x={os.getenv('CLICK_ABS_X')}, y={os.getenv('CLICK_ABS_Y')})",
        "",
        "AI:",
        f"Gemini модель: {ai_processor.get_model_name() or '—'}",
    ]
    await answer_chunks(message, "\n".join(status_lines), reply_markup=main_keyboard)


@dp.message(Command(commands=["windows"]))
async def windows(message: types.Message):
    try:
        uid = getattr(getattr(message, 'from_user', None), 'id', None)
        cid = getattr(getattr(message, 'chat', None), 'id', None)
        logger.info(f"/windows from user={uid} chat={cid}")
    except Exception:
        pass
    titles = desktop_controller.list_windows()
    lines = ["🪟 Окна Windsurf:"]
    if titles:
        for i, t in enumerate(titles, start=1):
            lines.append(f"#{i}: {t}")
    else:
        lines.append("(не найдено)")
    lines.append("\nОтправляйте с префиксом: [#N] ваш текст или [@часть_заголовка] ваш текст")
    # Добавим отладочную секцию с сырыми данными AppleScript
    try:
        mm = MacWindowManager()
        t2, dbg = mm.list_window_titles_with_debug()
        if t2 and t2 != titles:
            lines.append("\n(ℹ️ fallback) Альтернативный парсер видит:")
            for i, t in enumerate(t2, start=1):
                lines.append(f"→ {i}: {t}")
        if dbg:
            lines.append("\nDebug (AppleScript):")
            # ограничим количество строк, чтобы не заспамить чат
            for d in dbg[:12]:
                lines.append(f"• {d}")
    except Exception:
        pass
    # Отправляем с ретраями и защитой от сетевых обрывов
    try:
        logger.info("/windows reply (first 2000 chars):\n" + "\n".join(lines)[:2000])
    except Exception:
        pass
    await answer_chunks(message, "\n".join(lines), reply_markup=main_keyboard)


@dp.message(Command(commands=["model"]))
async def cmd_model(message: types.Message):
    """Управление моделью API через Telegram (через ai_processor)
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
            "⚙️ Управление моделью API (через ai_processor):\n"
            "• /model current — показать текущую модель\n"
            "• /model list — список доступных моделей\n"
            "• /model list pro — список, фильтр по подстроке\n"
            "• /model set <name> — установить модель\n"
            "\nДля переключения модели в UI Windsurf используйте: /wsmodel set [#N|@sub] <name>"
        )
        try:
            await message.answer(help_text, reply_markup=main_keyboard)
        except TelegramNetworkError as e:
            logger.warning(f"/model help send failed: {e}")
        return

    sub = parts[1].lower()

    if sub == "current":
        try:
            await message.answer(f"Текущая модель: {ai_processor.get_model_name() or '—'}", reply_markup=main_keyboard)
        except TelegramNetworkError as e:
            logger.warning(f"/model current send failed: {e}")
        return

    if sub == "list":
        models = ai_processor.list_models()
        if len(parts) >= 3:
            filt = " ".join(parts[2:]).lower()
            models = [m for m in models if filt in m.lower()]
        if not models:
            try:
                await message.answer("Список моделей пуст", reply_markup=main_keyboard)
            except TelegramNetworkError as e:
                logger.warning(f"/model list empty send failed: {e}")
            return
        lines = ["📚 Доступные модели:"] + [f"• {m}" for m in models[:100]]
        try:
            await message.answer("\n".join(lines), reply_markup=main_keyboard)
        except TelegramNetworkError as e:
            logger.warning(f"/model list send failed: {e}")
        return

    if sub == "set" and len(parts) >= 3:
        new_model = " ".join(parts[2:]).strip()
        ok, msg = ai_processor.set_model(new_model)
        prefix = "✅" if ok else "❌"
        try:
            await message.answer(f"{prefix} {msg}", reply_markup=main_keyboard)
        except TelegramNetworkError as e:
            logger.warning(f"/model set send failed: {e}")
        return

    await message.answer("Неизвестная подкоманда. Используйте /model для помощи.", reply_markup=main_keyboard)


def _parse_target_prefix(s: str) -> tuple[Optional[str], str]:
    """Парсинг префикса [#N] или [@substr] в начале строки. Возвращает (target, rest)."""
    import re
    s = (s or "").strip()
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


@dp.message(Command(commands=["wsmodel"]))
async def cmd_wsmodel(message: types.Message):
    """Переключение модели в UI Windsurf через командную палитру (Cmd+/, ввести имя, Enter).
    Примеры:
    /wsmodel set <name>
    /wsmodel set [#2] <name>
    /wsmodel set [@title_sub] <name>
    """
    text = (message.text or "").strip()
    parts = text.split(maxsplit=2)
    if len(parts) < 2:
        try:
            await message.answer(
                "⚙️ Переключение модели в UI Windsurf:\n"
                "• /wsmodel set <name> — активное окно\n"
                "• /wsmodel set [#N] <name> — окно по индексу в /windows\n"
                "• /wsmodel set [@часть_заголовка] <name> — окно по части заголовка\n"
                "Принцип: Cmd+/ → ввести <name> → Enter",
                reply_markup=main_keyboard,
            )
        except TelegramNetworkError as e:
            logger.warning(f"/wsmodel help send failed: {e}")
        return
    sub = (parts[1] or "").lower()
    if sub != 'set':
        try:
            await message.answer("Неизвестная подкоманда. Используйте: /wsmodel set ...", reply_markup=main_keyboard)
        except TelegramNetworkError as e:
            logger.warning(f"/wsmodel unknown send failed: {e}")
        return
    if len(parts) < 3:
        try:
            await message.answer("Укажите имя модели: /wsmodel set <name>", reply_markup=main_keyboard)
        except TelegramNetworkError as e:
            logger.warning(f"/wsmodel no name send failed: {e}")
        return
    payload = parts[2]
    target, name = _parse_target_prefix(payload)
    if not name:
        await message.answer("Пустое имя модели", reply_markup=main_keyboard)
        return
    ok, msg = desktop_controller.set_model_ui(name, target or "active")
    prefix = "✅" if ok else "❌"
    await message.answer(f"{prefix} {msg}", reply_markup=main_keyboard)


@dp.message(Command(commands=["whoami"]))
async def cmd_whoami(message: types.Message):
    uid = message.from_user.id if message.from_user else None
    uname = message.from_user.username if message.from_user else None
    try:
        await message.answer(f"Ваш user_id: {uid}\nusername: @{uname}", reply_markup=main_keyboard)
    except TelegramNetworkError as e:
        logger.warning(f"/whoami send failed: {e}")


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
    try:
        await message.answer("❌ Команда /git отключена в этой сборке.", reply_markup=main_keyboard)
    except TelegramNetworkError as e:
        logger.warning(f"/git send failed: {e}")


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
        try:
            await message.answer("🔄 Отправляю запрос в Windsurf...")
        except TelegramNetworkError as e:
            logger.warning(f"pre-send notice failed: {e}")
        copied_response = None
        diag = None
        if target:
            success = await desktop_controller.send_message_to(target, text)
        else:
            success = await desktop_controller.send_message(text)
        # Получим локальную телеметрию
        diag = desktop_controller.get_diagnostics()
        # 1) Если отправка неуспешна — сразу сообщаем об ошибке и выходим
        if not success:
            diag = desktop_controller.get_diagnostics()
            reason = diag.get("last_error") or "Неизвестно"
            try:
                await message.answer(
                    "❌ Ошибка при отправке сообщения\n"
                    f"Причина: {reason}\n"
                    f"Платформа: {diag.get('platform')}\n"
                    f"Windsurf процессов: {len(diag.get('windsurf_pids', []))}\n"
                    f"last_paste_strategy: {diag.get('last_paste_strategy')}\n"
                    f"last_copy_method: {diag.get('last_copy_method')}\n"
                    f"last_copy_length: {diag.get('last_copy_length')}\n"
                    f"last_copy_is_echo: {diag.get('last_copy_is_echo')}\n"
                    f"response_wait_loops: {diag.get('response_wait_loops')}\n"
                    f"response_ready_time: {diag.get('response_ready_time')}s\n"
                    f"response_stabilized: {diag.get('response_stabilized')}\n"
                    f"response_stabilized_by: {diag.get('response_stabilized_by')}\n"
                    f"last_ui_button: {diag.get('last_ui_button')}\n"
                    f"last_ui_avg_color: {diag.get('last_ui_avg_color')}\n"
                    f"last_visual_region: {diag.get('last_visual_region')}\n"
                    f"last_click_xy: {diag.get('last_click_xy')}",
                    reply_markup=main_keyboard,
                )
            except TelegramNetworkError as e:
                logger.warning(f"send error details failed: {e}")
            return

        # 2) Строгий режим по опорному пикселю — сообщаем об ожидании только после успешной отправки
        try:
            rp_required = (os.getenv("READY_PIXEL_REQUIRED", "0").lower() not in ("0", "false"))
        except Exception:
            rp_required = False
        if rp_required:
            by = (diag or {}).get("response_stabilized_by")
            last_rp = (diag or {}).get("last_ready_pixel") or {}
            if by != "ready_pixel" or not last_rp.get("match", False):
                try:
                    await message.answer(
                        "⏳ Ждём готовности ответа: контрольная точка ещё не совпала (READY_PIXEL).",
                        reply_markup=main_keyboard,
                    )
                except TelegramNetworkError as e:
                    logger.warning(f"ready wait notify failed: {e}")
                return

        # Получаем скопированный ответ:
        # - в удаленном режиме НЕ используем локальный буфер обмена как fallback, доверяем полю response от контроллера
        # - в локальном режиме берем из буфера
        if copied_response is None:
            import pyperclip
            copied_response = pyperclip.paste()

        # Фильтрация эхо: если diag говорит, что это эхо, не отправляем
        response_is_echo = False
        try:
            if isinstance(diag, dict) and (diag.get("response_is_echo") or diag.get("last_copy_is_echo")):
                response_is_echo = True
        except Exception:
            pass
        # Сообщение о fallback: если не удалось получить короткий ответ и применили полное копирование
        prefix_note = ""
        try:
            if isinstance(diag, dict) and diag.get("last_copy_method") == "full":
                prefix_note = "(ℹ️ Короткий ответ недоступен — выслан полный текст окна)\n\n"
        except Exception:
            pass

        if (copied_response and copied_response.strip()) and not response_is_echo:
            await answer_chunks(
                message,
                f"✅ Ответ от Windsurf:\n\n{prefix_note}{copied_response}",
                reply_markup=main_keyboard,
            )
        else:
            echo_note = "\nПричина: получено эхо исходного запроса — ответа еще нет." if response_is_echo else ""
            hint = (
                "Попробуйте: увеличить RESPONSE_WAIT_SECONDS, повторить запрос, или сфокусировать окно Windsurf."
            )
            try:
                await message.answer(
                    f"⚠️ Ответ не удалось получить из буфера обмена.{echo_note}\n{hint}",
                    reply_markup=main_keyboard,
                )
            except TelegramNetworkError as e:
                logger.warning(f"fallback notify failed: {e}")

        # OCR/калибровка удалены из проекта, поэтому дополнительные блоки не используются

    except Exception as e:
        logger.error(f"Error: {e}")
        try:
            await message.answer("❌ Произошла ошибка при обработке запроса")
        except TelegramNetworkError:
            pass


async def main():
    logger.info("Starting Windsurf Bot...")
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не задан. Создайте .env и укажите токен.")
        return
    bot = Bot(token=token)
    try:
        try:
            me = await bot.get_me()
            logger.info(f"Bot is up: @{getattr(me, 'username', None)} id={getattr(me, 'id', None)}")
        except Exception as e:
            logger.warning(f"get_me failed: {e}")
        await dp.start_polling(bot)
    except (KeyboardInterrupt, TelegramNetworkError) as e:
        logger.warning(f"Bot stopped: {e}")

if __name__ == "__main__":
    asyncio.run(main())
