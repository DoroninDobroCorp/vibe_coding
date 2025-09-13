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
RESPONSE_MAX_WAIT_SECONDS = _env_float("RESPONSE_MAX_WAIT_SECONDS", 45.0)
RESPONSE_POLL_INTERVAL_SECONDS = _env_float("RESPONSE_POLL_INTERVAL_SECONDS", 0.8)
RESPONSE_STABLE_MIN_SECONDS = _env_float("RESPONSE_STABLE_MIN_SECONDS", 1.6)
USE_APPLESCRIPT_ON_MAC = os.getenv("USE_APPLESCRIPT_ON_MAC", "1") not in ("0", "false", "False")
USE_UI_BUTTON_DETECTION = os.getenv("USE_UI_BUTTON_DETECTION", "0") not in ("0", "false", "False")
SEND_BTN_REGION_RIGHT = _env_int("SEND_BTN_REGION_RIGHT", 84)
SEND_BTN_REGION_BOTTOM = _env_int("SEND_BTN_REGION_BOTTOM", 58)
SEND_BTN_REGION_W = _env_int("SEND_BTN_REGION_W", 54)
SEND_BTN_REGION_H = _env_int("SEND_BTN_REGION_H", 36)
SEND_BTN_BLUE_DELTA = _env_int("SEND_BTN_BLUE_DELTA", 40)
SEND_BTN_WHITE_BRIGHT = _env_int("SEND_BTN_WHITE_BRIGHT", 200)
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
        self.last_paste_strategy = None  # 'direct' | 'clear_then_paste'
        self.last_copy_method = None     # 'short' | 'full'
        self.last_copy_length = 0
        self.last_copy_is_echo = False
        self.response_wait_loops = 0
        self.response_ready_time = 0.0
        self.response_stabilized = False
        self.last_ui_button = None  # 'send' | 'stop' | 'unknown'
        self.last_ui_avg_color = None  # (r,g,b)

    def as_dict(self):
        return {
            "success_sends": self.success_sends,
            "failed_sends": self.failed_sends,
            "last_error": self.last_error,
            "platform": self.last_platform,
            "windows_automation": WINDOWS_AUTOMATION_AVAILABLE,
            "windsurf_pids": _scan_windsurf_processes(),
            "last_paste_strategy": self.last_paste_strategy,
            "last_copy_method": self.last_copy_method,
            "last_copy_length": self.last_copy_length,
            "last_copy_is_echo": self.last_copy_is_echo,
            "response_wait_loops": self.response_wait_loops,
            "response_ready_time": self.response_ready_time,
            "response_stabilized": self.response_stabilized,
            "last_ui_button": self.last_ui_button,
            "last_ui_avg_color": self.last_ui_avg_color,
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

    def _wait_for_ready_mac(self, message: str, baseline_text: str | None = None) -> tuple[bool, str]:
        """Активное ожидание ответа на macOS: копируем короткий блок до стабилизации и отсутствия эхо."""
        start = time.time()
        last_text = (baseline_text or "").strip()
        last_change = start
        got_non_echo = False
        loops = 0
        copied_text = ""
        last_ui_state = None
        while time.time() - start < max(0.0, RESPONSE_MAX_WAIT_SECONDS):
            loops += 1
            try:
                # Навигация к ответу и копирование
                pyautogui.press('esc')
                time.sleep(0.1)
                pyautogui.keyDown('shift')
                pyautogui.press('tab')
                time.sleep(0.1)
                pyautogui.press('tab')
                pyautogui.keyUp('shift')
                time.sleep(0.2)
                pyautogui.press('enter')
                time.sleep(0.3)
                pyautogui.hotkey('command', 'c')
                time.sleep(0.2)
                txt = pyperclip.paste() or ""
                txt = txt.strip()
            except Exception:
                txt = ""

            if txt:
                if self._looks_like_echo(str(message), txt):
                    self.telemetry.last_copy_is_echo = True
                    got_non_echo = False
                else:
                    self.telemetry.last_copy_is_echo = False
                    if txt != last_text:
                        last_text = txt
                        last_change = time.time()
                        got_non_echo = True
                    else:
                        should_break = got_non_echo and (time.time() - last_change) >= RESPONSE_STABLE_MIN_SECONDS
                        # Если включена детекция кнопки — требуем состояние 'send'
                        if USE_UI_BUTTON_DETECTION:
                            ui_state, avg = self._classify_send_button_mac()
                            last_ui_state = ui_state
                            self.telemetry.last_ui_button = ui_state
                            self.telemetry.last_ui_avg_color = avg
                            if ui_state != 'send':
                                should_break = False
                        if should_break:
                            copied_text = txt
                            break
            time.sleep(RESPONSE_POLL_INTERVAL_SECONDS)

        ready = bool(copied_text)
        self.telemetry.response_wait_loops = loops
        self.telemetry.response_ready_time = round(time.time() - start, 2)
        self.telemetry.response_stabilized = ready
        return ready, copied_text

    def _classify_send_button_mac(self) -> tuple[str, tuple[int, int, int] | None]:
        """Классифицирует состояние кнопки (send/stop/unknown) по цвету области в правом нижнем углу окна."""
        try:
            if not self._mac_manager:
                return 'unknown', None
            bounds = self._mac_manager.get_front_window_bounds()
            if not bounds:
                return 'unknown', None
            x, y, w, h = bounds
            rx = max(0, x + w - SEND_BTN_REGION_RIGHT)
            ry = max(0, y + h - SEND_BTN_REGION_BOTTOM)
            rw = max(1, SEND_BTN_REGION_W)
            rh = max(1, SEND_BTN_REGION_H)
            img = pyautogui.screenshot(region=(rx, ry, rw, rh))
            # Уменьшаем и усредняем
            small = img.resize((8, 6))
            pixels = list(small.getdata())
            r = sum(p[0] for p in pixels) / len(pixels)
            g = sum(p[1] for p in pixels) / len(pixels)
            b = sum(p[2] for p in pixels) / len(pixels)
            r_i, g_i, b_i = int(r), int(g), int(b)
            blue_delta = b - max(r, g)
            brightness = (r + g + b) / 3.0
            if blue_delta >= SEND_BTN_BLUE_DELTA:
                return 'send', (r_i, g_i, b_i)
            if brightness >= SEND_BTN_WHITE_BRIGHT:
                return 'stop', (r_i, g_i, b_i)
            return 'unknown', (r_i, g_i, b_i)
        except Exception as e:
            logger.debug(f"classify_send_button_mac failed: {e}")
            return 'unknown', None

    def _wait_for_ready_windows(self, message: str, main_window, baseline_text: str | None = None) -> tuple[bool, str]:
        """Активное ожидание ответа на Windows: копируем короткий блок до стабилизации и отсутствия эхо."""
        start = time.time()
        last_text = (baseline_text or "").strip()
        last_change = start
        got_non_echo = False
        loops = 0
        copied_text = ""
        while time.time() - start < max(0.0, RESPONSE_MAX_WAIT_SECONDS):
            loops += 1
            try:
                pyautogui.press("esc")
                time.sleep(0.2)
                try:
                    if main_window is not None:
                        main_window.set_focus()
                except Exception:
                    pass
                time.sleep(0.1)
                if main_window is not None:
                    main_window.type_keys("^l", set_foreground=True, pause=0.02)
                    time.sleep(0.2)
                pyautogui.keyDown("shift")
                pyautogui.press("tab")
                time.sleep(0.15)
                pyautogui.press("tab")
                pyautogui.keyUp("shift")
                time.sleep(0.3)
                pyautogui.press("enter")
                time.sleep(0.5)
                if main_window is not None:
                    main_window.type_keys("^c", set_foreground=True, pause=0.02)
                    time.sleep(0.3)
                txt = pyperclip.paste() or ""
                txt = txt.strip()
            except Exception:
                txt = ""

            if txt:
                if self._looks_like_echo(str(message), txt):
                    self.telemetry.last_copy_is_echo = True
                    got_non_echo = False
                else:
                    self.telemetry.last_copy_is_echo = False
                    if txt != last_text:
                        last_text = txt
                        last_change = time.time()
                        got_non_echo = True
                    else:
                        if got_non_echo and (time.time() - last_change) >= RESPONSE_STABLE_MIN_SECONDS:
                            copied_text = txt
                            break
            time.sleep(RESPONSE_POLL_INTERVAL_SECONDS)

        ready = bool(copied_text)
        self.telemetry.response_wait_loops = loops
        self.telemetry.response_ready_time = round(time.time() - start, 2)
        self.telemetry.response_stabilized = ready
        return ready, copied_text

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

    def get_front_window_bounds(self) -> tuple[int, int, int, int] | None:
        """Возвращает (x, y, w, h) активного окна Windsurf. None при ошибке."""
        try:
            pos = self._osascript('tell application "System Events" to tell process "Windsurf" to get position of window 1')
            size = self._osascript('tell application "System Events" to tell process "Windsurf" to get size of window 1')
            if pos.returncode != 0 or size.returncode != 0:
                return None
            # Ответ вида: "{x, y}" и "{w, h}" или "x, y" без скобок
            def _parse_pair(s: str) -> tuple[int, int] | None:
                s = (s or "").strip().strip("{}").strip()
                parts = [p.strip() for p in s.split(",")]
                if len(parts) != 2:
                    return None
                try:
                    return int(float(parts[0])), int(float(parts[1]))
                except Exception:
                    return None
            xy = _parse_pair(pos.stdout)
            wh = _parse_pair(size.stdout)
            if not xy or not wh:
                return None
            return xy[0], xy[1], wh[0], wh[1]
        except Exception as e:
            logger.debug(f"get_front_window_bounds failed: {e}")
            return None


class DesktopController:
    def __init__(self):
        self.is_ready = False
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = max(0.1, KEY_DELAY_SECONDS)
        self.telemetry = _Telemetry()
        self._mac_manager = MacWindowManager() if platform.system() == "Darwin" else None

    def _looks_like_echo(self, original: str, copied: str) -> bool:
        try:
            o = (original or "").strip()
            c = (copied or "").strip()
            if not o or not c:
                return False
            prefix = o[: min(24, len(o))]
            # Эхо, если начинается с префикса исходного текста и по длине почти не длиннее исходника
            if c.startswith(prefix):
                if len(c) <= max(len(o) + 32, int(len(o) * 1.2)):
                    return True
            return False
        except Exception:
            return False

    

    def _wait_for_ready_windows(self, message: str, main_window) -> tuple[bool, str]:
        """Активное ожидание ответа на Windows: копируем короткий блок до стабилизации и отсутствия эхо."""
        start = time.time()
        last_text = ""
        last_change = start
        got_non_echo = False
        loops = 0
        copied_text = ""
        while time.time() - start < max(0.0, RESPONSE_MAX_WAIT_SECONDS):
            loops += 1
            try:
                pyautogui.press("esc")
                time.sleep(0.2)
                try:
                    if main_window is not None:
                        main_window.set_focus()
                except Exception:
                    pass
                time.sleep(0.1)
                if main_window is not None:
                    main_window.type_keys("^l", set_foreground=True, pause=0.02)
                    time.sleep(0.2)
                pyautogui.keyDown("shift")
                pyautogui.press("tab")
                time.sleep(0.15)
                pyautogui.press("tab")
                pyautogui.keyUp("shift")
                time.sleep(0.3)
                pyautogui.press("enter")
                time.sleep(0.5)
                if main_window is not None:
                    main_window.type_keys("^c", set_foreground=True, pause=0.02)
                    time.sleep(0.3)
                txt = pyperclip.paste() or ""
                txt = txt.strip()
            except Exception:
                txt = ""

            if txt:
                if self._looks_like_echo(str(message), txt):
                    self.telemetry.last_copy_is_echo = True
                    got_non_echo = False
                else:
                    self.telemetry.last_copy_is_echo = False
                    if txt != last_text:
                        last_text = txt
                        last_change = time.time()
                        got_non_echo = True
                    else:
                        if got_non_echo and (time.time() - last_change) >= RESPONSE_STABLE_MIN_SECONDS:
                            copied_text = txt
                            break
            time.sleep(RESPONSE_POLL_INTERVAL_SECONDS)

        ready = bool(copied_text)
        self.telemetry.response_wait_loops = loops
        self.telemetry.response_ready_time = round(time.time() - start, 2)
        self.telemetry.response_stabilized = ready
        return ready, copied_text

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
        """Вставка и верификация на macOS с ретраями.
        На повторных попытках: выделяем всё и удаляем, затем вставляем заново.
        """
        pasted_ok = False
        expected = str(expected_text).strip()
        for attempt in range(PASTE_RETRY_COUNT + 1):
            try:
                if attempt == 0:
                    self.telemetry.last_paste_strategy = 'direct'
                else:
                    self.telemetry.last_paste_strategy = 'clear_then_paste'
                    logger.warning("Повтор вставки: очищаю поле (Cmd+A, Backspace) и пробую снова")
                    pyautogui.hotkey('command', 'a')
                    time.sleep(0.1)
                    pyautogui.press('backspace')
                    time.sleep(0.15)

                pyautogui.hotkey('command', 'v')
                time.sleep(0.5)
                # Проверяем вставку (Cmd+A, Cmd+C)
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
                got = (pasted_text or "").strip()
                if got == expected:
                    pasted_ok = True
                    break
                else:
                    logger.debug("Верификация вставки: не совпало (got='%s', expected='%s')", got[:80], expected[:80])
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

                # Активное ожидание готовности ответа
                time.sleep(max(0.0, RESPONSE_WAIT_SECONDS))
                # baseline: текущий короткий блок (обычно это предыдущий ответ)
                baseline_text = ""
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
                    time.sleep(0.3)
                    pyautogui.hotkey('command', 'c')
                    time.sleep(0.2)
                    baseline_text = (pyperclip.paste() or "").strip()
                except Exception as e:
                    logger.debug(f"baseline copy (macOS) failed: {e}")
                self.telemetry.last_copy_method = 'short'
                ready, copied_text = self._wait_for_ready_mac(str(message), baseline_text)
                copied = ready
                if not ready:
                    # Fallback: полный текст окна
                    logger.warning("Не удалось дождаться стабильного короткого ответа — копирую полный текст (macOS)")
                    try:
                        self.telemetry.last_copy_method = 'full'
                        pyautogui.hotkey('command', 'a')
                        time.sleep(0.2)
                        pyautogui.hotkey('command', 'c')
                        time.sleep(0.4)
                        copied_text = pyperclip.paste()
                        copied = bool(copied_text and copied_text.strip() and not self._looks_like_echo(str(message), copied_text))
                    except Exception as e:
                        logger.debug(f"full copy fallback failed: {e}")
                self.telemetry.last_copy_length = len(copied_text or "")
                if not copied:
                    logger.warning("Ответ не получен или выглядит как эхо (macOS)")

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
                        # На повторных попытках предварительно очищаем поле
                        if attempt > 0:
                            logger.warning("Повтор вставки (Windows): очищаю поле (Ctrl+A, Backspace) перед вставкой")
                            pyautogui.hotkey('ctrl', 'a')
                            time.sleep(0.1)
                            pyautogui.press('backspace')
                            time.sleep(0.15)
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
                    except Exception as e:
                        logger.debug(f"win paste attempt {attempt} failed: {e}")
                        time.sleep(0.3)

                logger.info("Сообщение напечатано, отправляю Enter")
                pyautogui.press("enter")
                time.sleep(0.5)

                logger.info("Сообщение отправлено, ждем ответ ИИ...")
                time.sleep(max(0.0, RESPONSE_WAIT_SECONDS))

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

                # Активное ожидание готовности ответа (Windows)
                # baseline: текущий короткий блок (обычно это предыдущий ответ)
                baseline_text = ""
                try:
                    if main_window is not None:
                        main_window.type_keys("^c", set_foreground=True, pause=0.02)
                        time.sleep(0.3)
                    baseline_text = (pyperclip.paste() or "").strip()
                except Exception as e:
                    logger.debug(f"baseline copy (Windows) failed: {e}")
                self.telemetry.last_copy_method = 'short'
                ready, copied_text = self._wait_for_ready_windows(str(message), main_window, baseline_text)
                short_copied = ready
                if not short_copied:
                    logger.warning("Короткий ответ не стабилизировался (Windows) — копирую весь текст окна")
                    self.telemetry.last_copy_method = 'full'
                    try:
                        pyautogui.hotkey('ctrl', 'a')
                        time.sleep(0.2)
                        pyautogui.hotkey('ctrl', 'c')
                        time.sleep(0.4)
                        copied_text = pyperclip.paste()
                    except Exception as e:
                        logger.debug(f"full copy fallback (Windows) failed: {e}")

                if copied_text:
                    if self._looks_like_echo(str(message), copied_text):
                        self.telemetry.last_copy_is_echo = True
                        logger.warning("Даже полный текст похож на эхо исходного запроса (Windows)")
                    else:
                        self.telemetry.last_copy_is_echo = False
                    self.telemetry.last_copy_length = len(copied_text)
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
            "RESPONSE_MAX_WAIT_SECONDS": RESPONSE_MAX_WAIT_SECONDS,
            "RESPONSE_POLL_INTERVAL_SECONDS": RESPONSE_POLL_INTERVAL_SECONDS,
            "RESPONSE_STABLE_MIN_SECONDS": RESPONSE_STABLE_MIN_SECONDS,
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
