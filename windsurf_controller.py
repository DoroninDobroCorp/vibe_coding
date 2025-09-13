import asyncio
import os

import pyautogui
import time
import logging
import platform
import subprocess

import pyperclip
from dotenv import load_dotenv
try:
    # Импорты специфичные для Windows
    from pywinauto import Application
    from pywinauto.keyboard import send_keys
    WINDOWS_AUTOMATION_AVAILABLE = platform.system() == "Windows"
except Exception:
    Application = None
    send_keys = None
    WINDOWS_AUTOMATION_AVAILABLE = False

# Добавляем альтернативный способ работы с буфером обмена
try:
    if platform.system() == "Windows":
        import win32clipboard
        import win32con
        WIN32CLIPBOARD_AVAILABLE = True
    else:
        WIN32CLIPBOARD_AVAILABLE = False
except ImportError:
    WIN32CLIPBOARD_AVAILABLE = False

load_dotenv()
logger = logging.getLogger(__name__)

WINDSURF_WINDOW_TITLE = os.getenv("WINDSURF_WINDOW_TITLE")

# Параметры через ENV (с дефолтами)
def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default

def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except Exception:
        return default

PASTE_RETRY_COUNT = _env_int("PASTE_RETRY_COUNT", 2)
COPY_RETRY_COUNT = _env_int("COPY_RETRY_COUNT", 2)
RESPONSE_WAIT_SECONDS = _env_float("RESPONSE_WAIT_SECONDS", 7.0)
KEY_DELAY_SECONDS = _env_float("KEY_DELAY_SECONDS", 0.2)
USE_APPLESCRIPT_ON_MAC = os.getenv("USE_APPLESCRIPT_ON_MAC", "1") not in ("0", "false", "False")
FRONTMOST_WAIT_SECONDS = _env_float("FRONTMOST_WAIT_SECONDS", 3.0)
FOCUS_RETRY_COUNT = _env_int("FOCUS_RETRY_COUNT", 3)


def _scan_windsurf_processes():
    try:
        import psutil
        pids = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                name = (proc.info.get('name') or '').lower()
                if 'windsurf' in name:
                    pids.append(proc.info['pid'])
            except Exception:
                continue
        return pids
    except Exception as e:
        logger.debug(f"psutil scan error: {e}")
        return []


class _Telemetry:
    def __init__(self):
        self.success_sends = 0
        self.failed_sends = 0
        self.last_error = None
        self.last_platform = platform.system()

    def as_dict(self):
        return {
            "success_sends": self.success_sends,
            "failed_sends": self.failed_sends,
            "last_error": self.last_error,
            "platform": self.last_platform,
            "windows_automation": WINDOWS_AUTOMATION_AVAILABLE,
            "windsurf_pids": _scan_windsurf_processes(),
        }


# ========= MacOS Window Manager via AppleScript =========
class MacWindowManager:
    """Утилита для работы с окнами Windsurf на macOS через AppleScript/Accessibility.
    Требует включенный доступ в "Универсальный доступ" для терминала/процесса Python.
    """

    def _osascript(self, script: str) -> subprocess.CompletedProcess:
        return subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)

    def list_window_titles(self) -> list[str]:
        script = (
            'tell application "System Events" to tell process "Windsurf" to get name of windows'
        )
        res = self._osascript(script)
        if res.returncode != 0:
            return []
        # AppleScript может возвращать {"Title1", "Title2"} или строку при одном окне
        out = res.stdout.strip()
        if out.startswith("{") and out.endswith("}"):
            items = [s.strip().strip('"') for s in out[1:-1].split(",")]
            return items
        return [out.strip('"')] if out else []

    def focus_by_index(self, index_one_based: int) -> bool:
        try:
            script = (
                'tell application "Windsurf" to activate\n'
                f'tell application "System Events" to tell process "Windsurf" to perform action "AXRaise" of window {index_one_based}'
            )
            res = self._osascript(script)
            return res.returncode == 0
        except Exception:
            return False

    def focus_by_title_substring(self, substr: str) -> bool:
        titles = self.list_window_titles()
        if not titles:
            return False
        for idx, title in enumerate(titles, start=1):
            if substr.lower() in (title or "").lower():
                return self.focus_by_index(idx)
        return False

    def is_frontmost(self) -> bool:
        script = 'tell application "System Events" to get frontmost of process "Windsurf"'
        res = self._osascript(script)
        return res.returncode == 0 and res.stdout.strip().lower() in ("true", "yes")


class DesktopController:
    def __init__(self):
        self.is_ready = False
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = max(0.1, KEY_DELAY_SECONDS)
        self.telemetry = _Telemetry()
        self._mac_manager = MacWindowManager() if platform.system() == "Darwin" else None

    def copy_to_clipboard(self, text):
        """Надежное копирование текста в буфер обмена"""
        try:
            if WIN32CLIPBOARD_AVAILABLE:
                # Используем win32clipboard для большей надежности
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(str(text), win32con.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                logger.info("Текст скопирован через win32clipboard")
                return True
            else:
                # Fallback на pyperclip
                try:
                    pyperclip.copy(str(text))
                    logger.info("Текст скопирован через pyperclip")
                    return True
                except Exception as e:
                    # Доп. fallback для macOS: pbcopy
                    if platform.system() == "Darwin":
                        try:
                            p = subprocess.Popen(["/usr/bin/pbcopy"], stdin=subprocess.PIPE)
                            p.communicate(input=str(text).encode("utf-8"))
                            logger.info("Текст скопирован через pbcopy")
                            return True
                        except Exception as e2:
                            logger.error(f"pbcopy failed: {e2}")
                    raise e
        except Exception as e:
            logger.error(f"Ошибка при копировании в буфер: {e}")
            self.telemetry.last_error = f"copy_to_clipboard: {e}"
            return False

    def _paste_from_clipboard_mac(self, expected_text: str) -> bool:
        """Вставка и верификация на macOS с ретраями"""
        pasted_ok = False
        for attempt in range(PASTE_RETRY_COUNT + 1):
            try:
                pyautogui.hotkey('command', 'v')
                time.sleep(0.5)
                # Проверяем: CMD+A, CMD+C и сравниваем
                pyautogui.hotkey('command', 'a')
                time.sleep(0.1)
                pyautogui.hotkey('command', 'c')
                time.sleep(0.2)
                try:
                    pasted_text = pyperclip.paste()
                except Exception:
                    if platform.system() == "Darwin":
                        pasted_text = subprocess.check_output(["/usr/bin/pbpaste"]).decode("utf-8", "ignore")
                    else:
                        pasted_text = ""
                if pasted_text.strip() == str(expected_text).strip():
                    pasted_ok = True
                    break
            except Exception as e:
                logger.debug(f"mac paste attempt {attempt} failed: {e}")
                time.sleep(0.3)
        return pasted_ok

    def _ensure_windsurf_frontmost_mac(self, target: str | None) -> bool:
        """Сфокусировать Windsurf и, при необходимости, конкретное окно.
        target может быть None/"active" (текущее окно), "index:N" или подстрока заголовка."""
        if not USE_APPLESCRIPT_ON_MAC:
            return True
        try:
            # Активируем приложение
            subprocess.run(["osascript", "-e", 'tell application "Windsurf" to activate'], check=False)
            time.sleep(0.3)
            # Если задан таргет окна — пытаемся фокусировать его
            if target and target not in ("active", "default"):
                if target.startswith("index:"):
                    idx = int(target.split(":", 1)[1])
                    ok = self._mac_manager.focus_by_index(idx)
                    if not ok:
                        logger.warning(f"Не удалось сфокусировать окно по индексу: {idx}")
                else:
                    ok = self._mac_manager.focus_by_title_substring(target)
                    if not ok:
                        logger.warning(f"Не удалось сфокусировать окно по заголовку: {target}")
            # Ждем, пока Windsurf станет frontmost
            start = time.time()
            while time.time() - start < FRONTMOST_WAIT_SECONDS:
                if self._mac_manager.is_frontmost():
                    return True
                time.sleep(0.1)
            logger.warning("Windsurf не стал frontmost за отведенное время")
            return False
        except Exception as e:
            logger.debug(f"ensure frontmost failed: {e}")
            return False

    def send_message_sync(self, message, target: str | None = None):
        """Синхронная версия отправки сообщения (вызывается в отдельном потоке)"""

        system = platform.system()
        self.telemetry.last_platform = system
        try:
            if system == "Darwin":  # macOS путь
                logger.info("macOS: активируем приложение Windsurf")
                self._ensure_windsurf_frontmost_mac(target or "active")

                # Копируем в буфер и вставляем CMD+V с ретраями
                if not self.copy_to_clipboard(str(message)):
                    self.telemetry.failed_sends += 1
                    return False

                # Попытка сфокусировать поле ввода как в Windows-потоке (Cmd+L)
                try:
                    pyautogui.press('esc')
                    time.sleep(0.1)
                    pyautogui.hotkey('command', 'l')
                    time.sleep(0.3)
                except Exception as e:
                    logger.debug(f"mac focus (cmd+l) failed: {e}")

                pasted_ok = self._paste_from_clipboard_mac(str(message))
                if not pasted_ok:
                    logger.error("Не удалось вставить текст в Windsurf (macOS)")
                    self.telemetry.last_error = "mac paste failed"
                    self.telemetry.failed_sends += 1
                    return False

                logger.info("Вставка успешна, отправляю Enter")
                pyautogui.press('enter')
                time.sleep(0.5)

                # Ждем ответа ИИ
                time.sleep(RESPONSE_WAIT_SECONDS)

                # Попытка скопировать последний ответ (лучшее усилие)
                copied = False
                for attempt in range(COPY_RETRY_COUNT + 1):
                    try:
                        pyautogui.press('esc')
                        time.sleep(0.1)
                        pyautogui.keyDown('shift')
                        pyautogui.press('tab')
                        time.sleep(0.1)
                        pyautogui.press('tab')
                        pyautogui.keyUp('shift')
                        time.sleep(0.2)
                        pyautogui.press('enter')
                        time.sleep(0.4)
                        pyautogui.hotkey('command', 'c')
                        time.sleep(0.3)
                        copied_text = pyperclip.paste()
                        if copied_text and copied_text.strip():
                            logger.info(f"Скопирован ответ (macOS): {copied_text[:80]}...")
                            copied = True
                            break
                    except Exception as e:
                        logger.debug(f"mac copy attempt {attempt} failed: {e}")
                        time.sleep(0.3)
                if not copied:
                    logger.warning("Не удалось скопировать ответ (macOS), буфер может быть пуст")

                self.telemetry.success_sends += 1
                return True

            elif WINDOWS_AUTOMATION_AVAILABLE:
                # Ищем окно Windsurf по имени процесса (Windows)
                logger.info("Ищем окно Windsurf (Windows)...")
                windsurf_pids = _scan_windsurf_processes()
                logger.info(f"Найдено процессов Windsurf: {len(windsurf_pids)} - PIDs: {windsurf_pids}")

                main_window = None
                for pid in windsurf_pids:
                    try:
                        logger.info(f"Проверяем процесс PID: {pid}")
                        app = Application(backend="uia").connect(process=pid)

                        all_windows = app.windows()
                        visible_windows = [w for w in all_windows if w.is_visible()]

                        logger.info(f"PID {pid}: всего окон={len(all_windows)}, видимых={len(visible_windows)}")

                        if visible_windows:
                            main_window = visible_windows[0]
                            main_window.set_focus()
                            logger.info(f"Активировано окно из PID {pid}: {main_window.window_text()}")
                            break
                        elif all_windows:
                            main_window = all_windows[0]
                            main_window.set_focus()
                            logger.info(f"Активировано скрытое окно из PID {pid}: {main_window.window_text()}")
                            break
                    except Exception as e:
                        logger.info(f"PID {pid} недоступен: {e}")
                        continue

                if not main_window:
                    raise Exception("Ни в одном процессе Windsurf не найдены окна")
                time.sleep(0.8)

                # Поле ввода уже активно, просто печатаем
                logger.info(f"Печатаем сообщение напрямую: {message}")

                # Копируем строку в буфер
                if not self.copy_to_clipboard(str(message)):
                    logger.error("Не удалось скопировать текст в буфер обмена")
                    self.telemetry.failed_sends += 1
                    return False
                time.sleep(0.2)

                # Устанавливаем фокус на окно
                if main_window is not None:
                    try:
                        main_window.set_focus()
                        time.sleep(0.3)
                    except Exception as e:
                        logger.warning(f"Не удалось установить фокус через main_window: {e}")

                # Дополнительная задержка для полной активации окна
                time.sleep(0.3)

                # Проверяем содержимое буфера обмена перед вставкой, ретраи
                for attempt in range(PASTE_RETRY_COUNT + 1):
                    try:
                        clipboard_content = pyperclip.paste()
                        if clipboard_content.strip() != str(message).strip():
                            if not self.copy_to_clipboard(str(message)):
                                continue
                            time.sleep(0.2)
                        # Пытаемся вставить
                        pyautogui.hotkey('ctrl', 'v')
                        time.sleep(0.5)
                        # Проверяем вставку
                        pyautogui.hotkey('ctrl', 'a')
                        time.sleep(0.1)
                        pyautogui.hotkey('ctrl', 'c')
                        time.sleep(0.2)
                        pasted_text = pyperclip.paste()
                        if pasted_text.strip() == str(message).strip():
                            break
                    except Exception:
                        time.sleep(0.3)

                logger.info("Сообщение напечатано, отправляю Enter")
                pyautogui.press("enter")
                time.sleep(0.5)

                logger.info("Сообщение отправлено, ждем ответ ИИ...")
                time.sleep(RESPONSE_WAIT_SECONDS)

                # Копирование ответа (Windows)
                logger.info("Копируем ответ ИИ...")
                pyautogui.press("esc")
                time.sleep(0.25)
                try:
                    if main_window is not None:
                        main_window.set_focus()
                except Exception:
                    pass
                time.sleep(0.2)
                if main_window is not None:
                    main_window.type_keys("^l", set_foreground=True, pause=0.02)
                    time.sleep(0.3)

                pyautogui.keyDown("shift")
                pyautogui.press("tab")
                time.sleep(0.2)
                pyautogui.press("tab")
                pyautogui.keyUp("shift")
                time.sleep(0.5)
                pyautogui.press("enter")
                time.sleep(0.8)

                copied_text = pyperclip.paste()
                if copied_text.strip().startswith(str(message).strip()[:20]):
                    try:
                        if main_window is not None:
                            main_window.set_focus()
                    except Exception:
                        pass
                    time.sleep(0.2)
                    if main_window is not None:
                        main_window.type_keys("^l", set_foreground=True, pause=0.02)
                        time.sleep(0.3)
                    pyautogui.keyDown("shift")
                    pyautogui.press("tab")
                    time.sleep(0.2)
                    pyautogui.press("tab")
                    pyautogui.keyUp("shift")
                    time.sleep(0.3)
                    if main_window is not None:
                        main_window.type_keys("^c", set_foreground=True, pause=0.02)
                        time.sleep(0.4)
                    copied_text = pyperclip.paste()

                if copied_text:
                    logger.info(f"Ответ скопирован в буфер: {copied_text[:100]}...")
                self.telemetry.success_sends += 1
                return True

            else:
                logger.warning("Автоматизация недоступна на этой платформе")
                self.telemetry.last_error = "unsupported platform"
                return False
        except Exception as e:
            logger.error(f"Ошибка: {str(e)}")
            self.telemetry.last_error = str(e)
            self.telemetry.failed_sends += 1
            return False

    def get_diagnostics(self):
        """Диагностика и телеметрия для /status"""
        d = self.telemetry.as_dict()
        d.update({
            "RESPONSE_WAIT_SECONDS": RESPONSE_WAIT_SECONDS,
            "PASTE_RETRY_COUNT": PASTE_RETRY_COUNT,
            "COPY_RETRY_COUNT": COPY_RETRY_COUNT,
        })
        return d

    async def send_message(self, message):
        """Асинхронная обертка для отправки сообщения"""
        return await asyncio.to_thread(self.send_message_sync, message)

    async def send_message_to(self, target: str, message):
        """Асинхронная отправка сообщения в конкретное окно/таргет (macOS: index:N или часть заголовка)."""
        return await asyncio.to_thread(self.send_message_sync, message, target)

    def list_windows(self) -> list:
        """Список заголовков окон Windsurf (macOS). На других платформах возвращает пустой список."""
        try:
            if platform.system() == "Darwin" and self._mac_manager:
                return self._mac_manager.list_window_titles()
        except Exception as e:
            logger.debug(f"list_windows failed: {e}")
        return []


desktop_controller = DesktopController()
