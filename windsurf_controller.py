import asyncio
import os
from dotenv import load_dotenv

import pyautogui
import time
import logging
import platform
import subprocess

import pyperclip
from mac_window_manager import MacWindowManager
from selection import copy_from_right_panel
from clipboard_utils import copy_to_clipboard as cb_copy, paste_from_clipboard_mac as cb_paste_mac
from text_filter import clean_copied_text, extract_answer_by_prompt
from PIL import ImageChops, ImageStat
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
USE_FULLTEXT_STABILIZATION = os.getenv("USE_FULLTEXT_STABILIZATION", "0") not in ("0", "false", "False")
USE_CPU_READY_DETECTION = os.getenv("USE_CPU_READY_DETECTION", "1") not in ("0", "false", "False")
CPU_READY_THRESHOLD = _env_float("CPU_READY_THRESHOLD", 6.0)
CPU_READY_STABLE_SECONDS = _env_float("CPU_READY_STABLE_SECONDS", 20.0)
CPU_SAMPLE_INTERVAL_SECONDS = _env_float("CPU_SAMPLE_INTERVAL_SECONDS", 1.0)
USE_UI_BUTTON_DETECTION = os.getenv("USE_UI_BUTTON_DETECTION", "0") not in ("0", "false", "False")
SEND_BTN_REGION_RIGHT = _env_int("SEND_BTN_REGION_RIGHT", 84)
SEND_BTN_REGION_BOTTOM = _env_int("SEND_BTN_REGION_BOTTOM", 58)
SEND_BTN_REGION_W = _env_int("SEND_BTN_REGION_W", 54)
SEND_BTN_REGION_H = _env_int("SEND_BTN_REGION_H", 36)
SEND_BTN_BLUE_DELTA = _env_int("SEND_BTN_BLUE_DELTA", 40)
SEND_BTN_WHITE_BRIGHT = _env_int("SEND_BTN_WHITE_BRIGHT", 200)
FRONTMOST_WAIT_SECONDS = _env_float("FRONTMOST_WAIT_SECONDS", 3.0)
FOCUS_RETRY_COUNT = _env_int("FOCUS_RETRY_COUNT", 3)

# Визуальная стабилизация (macOS): детекция «остановки движения» в области ответа
USE_VISUAL_STABILITY = os.getenv("USE_VISUAL_STABILITY", "1") not in ("0", "false", "False")
VISUAL_REGION_TOP = _env_int("VISUAL_REGION_TOP", 100)
VISUAL_REGION_BOTTOM = _env_int("VISUAL_REGION_BOTTOM", 150)
VISUAL_SAMPLE_INTERVAL_SECONDS = _env_float("VISUAL_SAMPLE_INTERVAL_SECONDS", 0.5)
VISUAL_DIFF_THRESHOLD = _env_float("VISUAL_DIFF_THRESHOLD", 5.0)
VISUAL_STABLE_SECONDS = _env_float("VISUAL_STABLE_SECONDS", 2.0)
SAVE_VISUAL_DEBUG = os.getenv("SAVE_VISUAL_DEBUG", "0") not in ("0", "false", "False")
SAVE_VISUAL_DIR = os.getenv("SAVE_VISUAL_DIR", "debug")
USE_COPY_SHORT_FALLBACK = os.getenv("USE_COPY_SHORT_FALLBACK", "1") not in ("0", "false", "False")
RIGHT_CLICK_X_FRACTION = _env_float("RIGHT_CLICK_X_FRACTION", 0.5)  # в пределах правой трети (0..1)
RIGHT_CLICK_Y_OFFSET = _env_int("RIGHT_CLICK_Y_OFFSET", 80)  # пикселей ниже VISUAL_REGION_TOP
ECHO_FILTER_ENABLED = os.getenv("ECHO_FILTER_ENABLED", "1") not in ("0", "false", "False")
ECHO_PREFIX_LEN = _env_int("ECHO_PREFIX_LEN", 24)
ECHO_MAX_DELTA = _env_int("ECHO_MAX_DELTA", 64)
ECHO_LEN_RATIO = _env_float("ECHO_LEN_RATIO", 1.4)
USE_READY_PIXEL = os.getenv("USE_READY_PIXEL", "1") not in ("0", "false", "False")
READY_PIXEL_REQUIRED = os.getenv("READY_PIXEL_REQUIRED", "0") not in ("0", "false", "False")
READY_PIXEL_X = _env_int("READY_PIXEL_X", -1)
READY_PIXEL_Y = _env_int("READY_PIXEL_Y", -1)
READY_PIXEL_R = _env_int("READY_PIXEL_R", 225)
READY_PIXEL_G = _env_int("READY_PIXEL_G", 220)
READY_PIXEL_B = _env_int("READY_PIXEL_B", 204)
READY_PIXEL_TOL = _env_int("READY_PIXEL_TOL", 12)
READY_PIXEL_TOL_PCT = _env_float("READY_PIXEL_TOL_PCT", -1.0)  # если >=0, использовать процентную толерантность
READY_PIXEL_COORD_MODE = os.getenv("READY_PIXEL_COORD_MODE", "top").strip().lower()
READY_PIXEL_DX = _env_int("READY_PIXEL_DX", 0)
READY_PIXEL_DY = _env_int("READY_PIXEL_DY", 0)
CLICK_ABS_X = _env_int("CLICK_ABS_X", -1)
CLICK_ABS_Y = _env_int("CLICK_ABS_Y", -1)

# Отладка опорного пикселя: по умолчанию сохраняем только при совпадении и не сохраняем гипотезы
SAVE_READY_HYPOTHESES = os.getenv("SAVE_READY_HYPOTHESES", "0") not in ("0", "false", "False")
SAVE_READY_ONLY_ON_MATCH = os.getenv("SAVE_READY_ONLY_ON_MATCH", "1") not in ("0", "false", "False")


def map_ready_pixel_xy(rp_x: int, rp_y: int, rp_mode: str | None = None, rp_dx: int | None = None, rp_dy: int | None = None) -> tuple[int, int]:
    """Маппинг координат опорного пикселя в экранные координаты согласно режиму.
    Если параметры не заданы, берутся из ENV.
    """
    if rp_mode is None:
        rp_mode = os.getenv("READY_PIXEL_COORD_MODE", READY_PIXEL_COORD_MODE).strip().lower()
    if rp_dx is None:
        rp_dx = int(os.getenv("READY_PIXEL_DX", str(READY_PIXEL_DX)))
    if rp_dy is None:
        rp_dy = int(os.getenv("READY_PIXEL_DY", str(READY_PIXEL_DY)))
    x2, y2 = int(rp_x) + int(rp_dx), int(rp_y) + int(rp_dy)
    if rp_mode == 'flipy':
        # инвертируем только по режиму, без ограничения экраном
        try:
            _, sh = pyautogui.size()
        except Exception:
            sh = 0
        return x2, (sh - 1 - y2) if sh else y2
    if rp_mode == 'top2x':
        return x2 * 2, y2 * 2
    if rp_mode == 'flipy2x':
        try:
            _, sh = pyautogui.size()
        except Exception:
            sh = 0
        return x2 * 2, ((sh * 2 - 1) - y2 * 2) if sh else (y2 * 2)
    # default 'top'
    return x2, y2

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
        self.last_full_copy_length = 0
        self.response_stabilized_by = None  # 'short' | 'full' | None
        self.cpu_quiet_seconds = 0.0
        self.cpu_last_total_percent = 0.0
        self.last_visual_region = None  # (rx, ry, rw, rh)
        self.last_click_xy = None  # (x, y)
        self.last_ready_pixel = None  # {'x':..,'y':..,'rgb':(r,g,b),'match':bool,'delta':(dr,dg,db)}

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
            "last_full_copy_length": self.last_full_copy_length,
            "response_stabilized_by": self.response_stabilized_by,
            "cpu_quiet_seconds": self.cpu_quiet_seconds,
            "cpu_last_total_percent": self.cpu_last_total_percent,
            "last_visual_region": self.last_visual_region,
            "last_click_xy": self.last_click_xy,
            "last_ready_pixel": self.last_ready_pixel,
        }


class DesktopController:
    def __init__(self):
        self.is_ready = False
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = max(0.1, KEY_DELAY_SECONDS)
        self.telemetry = _Telemetry()
        self._mac_manager = MacWindowManager() if platform.system() == "Darwin" else None

    def _lcp_suffix(self, a: str, b: str) -> str:
        """Возвращает суффикс b после наибольшего общего префикса a и b."""
        try:
            if not isinstance(a, str) or not isinstance(b, str):
                return b or ""
            n = min(len(a), len(b))
            i = 0
            while i < n and a[i] == b[i]:
                i += 1
            return b[i:]
        except Exception:
            return b or ""

    def _looks_like_echo(self, original: str, copied: str) -> bool:
        try:
            o = (original or "").strip()
            c = (copied or "").strip()
            if not o or not c:
                return False
            if not ECHO_FILTER_ENABLED:
                return False
            prefix = o[: min(ECHO_PREFIX_LEN, len(o))]
            # Эхо, если начинается с префикса исходного текста и по длине почти не длиннее исходника
            if c.startswith(prefix):
                allowed_len = max(len(o) + ECHO_MAX_DELTA, int(len(o) * ECHO_LEN_RATIO))
                if len(c) <= allowed_len:
                    return True
            return False
        except Exception:
            return False


    def _classify_send_button_mac(self) -> tuple[str, tuple[int, int, int] | None]:
        """Классифицирует состояние кнопки (send/stop/unknown) по цвету области в правом нижнем углу окна (пиксельный метод)."""
        try:
            if not self._mac_manager:
                return 'unknown', None
            # Определяем по региону (если доступны координаты окна)
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
            logger.debug(f"classify_send_button_mac (in DesktopController) failed: {e}")
            return 'unknown', None

    def _wait_for_ready_mac(self, message: str, baseline_text: str | None = None) -> tuple[bool, str]:
        """Ожидание готовности ответа на macOS двумя способами:
        1) CPU-тишь процесса Windsurf (по умолчанию).
        2) Пиксельная детекция кнопки (send/stop) — если включена.
        По готовности копируем весь текст и извлекаем суффикс относительно baseline.
        """
        start = time.time()
        # Снимем baseline полного текста (до генерации)
        baseline_full = ""
        if not READY_PIXEL_REQUIRED:
            try:
                pyautogui.hotkey('command', 'a')
                time.sleep(0.15)
                pyautogui.hotkey('command', 'c')
                time.sleep(0.2)
                baseline_full = (pyperclip.paste() or "").strip()
            except Exception:
                baseline_full = ""

        loops = 0
        ready_by = None  # 'visual' | 'pixel'
        # Визуальная стабилизация
        visual_prev_small = None
        visual_last_change = start
        last_visual_sample = 0.0

        while time.time() - start < max(0.0, RESPONSE_MAX_WAIT_SECONDS):
            loops += 1

            # 1) Визуальная стабилизация (динамически читаем флаг из ENV)
            _use_vs = os.getenv("USE_VISUAL_STABILITY", "1").lower() not in ("0", "false")
            if _use_vs and self._mac_manager:
                now = time.time()
                if now - last_visual_sample >= max(0.1, VISUAL_SAMPLE_INTERVAL_SECONDS):
                    last_visual_sample = now
                    bounds = None
                    try:
                        bounds = self._mac_manager.get_front_window_bounds()
                    except Exception:
                        bounds = None
                    if bounds:
                        x, y, w, h = bounds
                        # Анализируем только правую треть окна (панель ответа)
                        right_third_x = x + max(0, int(w * 2 / 3))
                        rx = max(0, right_third_x + 8)
                        ry = max(0, y + max(0, VISUAL_REGION_TOP))
                        rw = max(16, int(w / 3) - 16)
                        rh = max(24, h - max(0, VISUAL_REGION_TOP) - max(0, VISUAL_REGION_BOTTOM))
                        try:
                            color_img = pyautogui.screenshot(region=(rx, ry, rw, rh))
                            img = color_img.resize((96, 72)).convert('L')
                            # запомним регион для диагностики
                            self.telemetry.last_visual_region = (rx, ry, rw, rh)
                            if visual_prev_small is not None:
                                diff = ImageChops.difference(img, visual_prev_small)
                                stat = ImageStat.Stat(diff)
                                mean_diff = float(stat.mean[0]) if stat and stat.mean else 0.0
                                if mean_diff > VISUAL_DIFF_THRESHOLD:
                                    visual_last_change = now
                            visual_prev_small = img
                            if (now - visual_last_change) >= VISUAL_STABLE_SECONDS:
                                ready_by = 'visual'
                            # Сохранение промежуточных кадров области анализа — по отдельному флагу
                            _save_samples = os.getenv("SAVE_VISUAL_SAMPLES", "0").lower() not in ("0", "false")
                            if _save_samples:
                                try:
                                    os.makedirs(SAVE_VISUAL_DIR, exist_ok=True)
                                    ts = time.strftime("%Y%m%d_%H%M%S")
                                    ms = int((time.time() % 1) * 1000)
                                    color_img.save(os.path.join(SAVE_VISUAL_DIR, f"visual_region_{ts}_{ms:03d}.png"))
                                except Exception as _e:
                                    logger.debug(f"save visual debug failed: {_e}")
                        except Exception:
                            pass

            # 2) Пиксельная детекция кнопки
            if ready_by is None and USE_UI_BUTTON_DETECTION:
                ui_state, avg = self._classify_send_button_mac()
                self.telemetry.last_ui_button = ui_state
                self.telemetry.last_ui_avg_color = avg
                if ui_state == 'send':
                    ready_by = 'pixel'

            # 3) Датчик готовности по опорному пикселю (абсолютные координаты)
            if ready_by is None and USE_READY_PIXEL and READY_PIXEL_X >= 0 and READY_PIXEL_Y >= 0:
                try:
                    # Поддержка динамического чтения ENV на каждом цикле, чтобы не требовать рестарта
                    try:
                        load_dotenv(override=True)
                    except Exception:
                        pass
                    rp_x = int(os.getenv("READY_PIXEL_X", str(READY_PIXEL_X)))
                    rp_y = int(os.getenv("READY_PIXEL_Y", str(READY_PIXEL_Y)))
                    rp_r = int(os.getenv("READY_PIXEL_R", str(READY_PIXEL_R)))
                    rp_g = int(os.getenv("READY_PIXEL_G", str(READY_PIXEL_G)))
                    rp_b = int(os.getenv("READY_PIXEL_B", str(READY_PIXEL_B)))
                    rp_tol = int(os.getenv("READY_PIXEL_TOL", str(READY_PIXEL_TOL)))
                    rp_tol_pct = float(os.getenv("READY_PIXEL_TOL_PCT", str(READY_PIXEL_TOL_PCT)))
                    rp_mode = os.getenv("READY_PIXEL_COORD_MODE", READY_PIXEL_COORD_MODE).strip().lower()
                    rp_dx = int(os.getenv("READY_PIXEL_DX", str(READY_PIXEL_DX)))
                    rp_dy = int(os.getenv("READY_PIXEL_DY", str(READY_PIXEL_DY)))

                    sx, sy = map_ready_pixel_xy(rp_x, rp_y, rp_mode, rp_dx, rp_dy)
                    pr, pg, pb = pyautogui.pixel(sx, sy)
                    dr = abs(int(pr) - rp_r)
                    dg = abs(int(pg) - rp_g)
                    db = abs(int(pb) - rp_b)
                    if rp_tol_pct is not None and rp_tol_pct >= 0:
                        # относительная ошибка по каналам (в % от 255)
                        rel = (dr + dg + db) / (3.0 * 255.0) * 100.0
                        match = rel <= rp_tol_pct
                    else:
                        match = (dr <= rp_tol and dg <= rp_tol and db <= rp_tol)
                    logger.debug(
                        "READY_PIXEL probe: used_xy=%s rgb=%s target=%s delta=%s tol=%s tol_pct=%s -> match=%s",
                        (sx, sy), (int(pr), int(pg), int(pb)), (rp_r, rp_g, rp_b), (dr, dg, db), rp_tol, rp_tol_pct, match,
                    )
                    self.telemetry.last_ready_pixel = {
                        'x': rp_x, 'y': rp_y, 'used_xy': (sx, sy), 'mode': rp_mode, 'dxdy': (rp_dx, rp_dy),
                        'rgb': (int(pr), int(pg), int(pb)),
                        'target': (rp_r, rp_g, rp_b),
                        'tol': rp_tol,
                        'tol_pct': rp_tol_pct if rp_tol_pct is not None and rp_tol_pct >= 0 else None,
                        'delta': (dr, dg, db), 'match': match,
                    }
                    # Сохраняем снимки (умолчание: только при совпадении и только USED; гипотезы — по флагу)
                    if SAVE_VISUAL_DEBUG:
                        try:
                            if (not SAVE_READY_ONLY_ON_MATCH) or match:
                                from PIL import ImageDraw
                                ts_dbg = int(time.time())
                                sw, sh = pyautogui.size()
                                cw, ch = 180, 140
                                # used (фактически применённые координаты)
                                urx = int(sx - cw / 2)
                                ury = int(sy - ch / 2)
                                urx = max(0, min(sw - cw, urx))
                                ury = max(0, min(sh - ch, ury))
                                uimg = pyautogui.screenshot(region=(urx, ury, cw, ch))
                                du = ImageDraw.Draw(uimg)
                                du.line([(cw//2 - 8, ch//2), (cw//2 + 8, ch//2)], fill=(0,255,0), width=2)
                                du.line([(cw//2, ch//2 - 8), (cw//2, ch//2 + 8)], fill=(0,255,0), width=2)
                                os.makedirs(SAVE_VISUAL_DIR, exist_ok=True)
                                uimg.save(os.path.join(SAVE_VISUAL_DIR, f"ready_pixel_{'match' if match else 'probe'}_USED_{rp_mode}_{ts_dbg}_{urx}x{ury}_{cw}x{ch}.png"))

                                # Полноэкранный снимок с крестом в фактической точке
                                try:
                                    fs = pyautogui.screenshot()
                                    dfs = ImageDraw.Draw(fs)
                                    cx, cy = sx, sy
                                    dfs.line([(cx - 12, cy), (cx + 12, cy)], fill=(0,255,0), width=3)
                                    dfs.line([(cx, cy - 12), (cx, cy + 12)], fill=(0,255,0), width=3)
                                    max_w = 1600
                                    if fs.width > max_w:
                                        ratio = max_w / fs.width
                                        fs = fs.resize((max_w, int(fs.height * ratio)))
                                    fs.save(os.path.join(SAVE_VISUAL_DIR, f"ready_pixel_{'match' if match else 'probe'}_USED_FULL_{rp_mode}_{ts_dbg}_{sx}x{sy}.png"))
                                except Exception:
                                    pass

                                # Дополнительные гипотезы — только если явно включено
                                if SAVE_READY_HYPOTHESES:
                                    # 1) top-origin как есть
                                    rx1 = int(rp_x - cw / 2)
                                    ry1 = int(rp_y - ch / 2)
                                    rx1 = max(0, min(sw - cw, rx1))
                                    ry1 = max(0, min(sh - ch, ry1))
                                    img1 = pyautogui.screenshot(region=(rx1, ry1, cw, ch))
                                    d1 = ImageDraw.Draw(img1)
                                    d1.line([(cw//2 - 8, ch//2), (cw//2 + 8, ch//2)], fill=(255,0,0), width=2)
                                    d1.line([(cw//2, ch//2 - 8), (cw//2, ch//2 + 8)], fill=(255,0,0), width=2)
                                    img1.save(os.path.join(SAVE_VISUAL_DIR, f"ready_pixel_{'match' if match else 'probe'}_top_{ts_dbg}_{rx1}x{ry1}_{cw}x{ch}.png"))

                                    # 2) flipped Y
                                    fy = max(0, min(sh - 1, sh - 1 - rp_y))
                                    rx2 = int(rp_x - cw / 2)
                                    ry2 = int(fy - ch / 2)
                                    rx2 = max(0, min(sw - cw, rx2))
                                    ry2 = max(0, min(sh - ch, ry2))
                                    img2 = pyautogui.screenshot(region=(rx2, ry2, cw, ch))
                                    d2 = ImageDraw.Draw(img2)
                                    d2.line([(cw//2 - 8, ch//2), (cw//2 + 8, ch//2)], fill=(255,0,0), width=2)
                                    d2.line([(cw//2, ch//2 - 8), (cw//2, ch//2 + 8)], fill=(255,0,0), width=2)
                                    img2.save(os.path.join(SAVE_VISUAL_DIR, f"ready_pixel_{'match' if match else 'probe'}_flipY_{ts_dbg}_{rx2}x{ry2}_{cw}x{ch}.png"))

                                    # 3) retina 2x top-origin
                                    rx3 = int(rp_x*2 - cw/2)
                                    ry3 = int(rp_y*2 - ch/2)
                                    rx3 = max(0, min(sw - cw, rx3))
                                    ry3 = max(0, min(sh - ch, ry3))
                                    img3 = pyautogui.screenshot(region=(rx3, ry3, cw, ch))
                                    d3 = ImageDraw.Draw(img3)
                                    d3.line([(cw//2 - 8, ch//2), (cw//2 + 8, ch//2)], fill=(255,0,0), width=2)
                                    d3.line([(cw//2, ch//2 - 8), (cw//2, ch//2 + 8)], fill=(255,0,0), width=2)
                                    img3.save(os.path.join(SAVE_VISUAL_DIR, f"ready_pixel_{'match' if match else 'probe'}_top2x_{ts_dbg}_{rx3}x{ry3}_{cw}x{ch}.png"))

                                    # 4) retina 2x + flipped Y
                                    fy2 = max(0, (sh*2 - 1) - rp_y*2)
                                    rx4 = int(rp_x*2 - cw/2)
                                    ry4 = int(fy2 - ch/2)
                                    rx4 = max(0, min(sw - cw, rx4))
                                    ry4 = max(0, min(sh - ch, ry4))
                                    img4 = pyautogui.screenshot(region=(rx4, ry4, cw, ch))
                                    d4 = ImageDraw.Draw(img4)
                                    d4.line([(cw//2 - 8, ch//2), (cw//2 + 8, ch//2)], fill=(255,0,0), width=2)
                                    d4.line([(cw//2, ch//2 - 8), (cw//2, ch//2 + 8)], fill=(255,0,0), width=2)
                                    img4.save(os.path.join(SAVE_VISUAL_DIR, f"ready_pixel_{'match' if match else 'probe'}_flipY2x_{ts_dbg}_{rx4}x{ry4}_{cw}x{ch}.png"))
                        except Exception:
                            pass
                    if match:
                        ready_by = 'ready_pixel'
                        logger.info(
                            "READY_PIXEL matched: used_xy=(%d,%d) rgb=(%d,%d,%d) target=(%d,%d,%d) tol=%d tol_pct=%s",
                            sx, sy, int(pr), int(pg), int(pb), rp_r, rp_g, rp_b, rp_tol, str(rp_tol_pct)
                        )
                except Exception as _e:
                    self.telemetry.last_ready_pixel = {'x': READY_PIXEL_X, 'y': READY_PIXEL_Y, 'error': str(_e)}

            if ready_by is not None and (not READY_PIXEL_REQUIRED or ready_by == 'ready_pixel'):
                logger.info("Readiness satisfied by=%s, proceeding to copy", ready_by)
                break

            time.sleep(RESPONSE_POLL_INTERVAL_SECONDS)

        # Финальный сбор текста
        copied_text = ""
        if ready_by is not None and (not READY_PIXEL_REQUIRED or ready_by == 'ready_pixel'):
            try:
                # 0) Если включён строгий режим — выделим текст мышью в правой панели и скопируем
                short_txt = ''
                if READY_PIXEL_REQUIRED and self._mac_manager:
                    bounds = None
                    try:
                        bounds = self._mac_manager.get_front_window_bounds()
                    except Exception:
                        bounds = None
                    if bounds:
                        x, y, w, h = bounds
                        right_third_x = x + max(0, int(w * 2 / 3))
                        rx = max(0, right_third_x + 8)
                        ry = max(0, y + max(0, VISUAL_REGION_TOP))
                        rw = max(16, int(w / 3) - 16)
                        rh = max(24, h - max(0, VISUAL_REGION_TOP) - max(0, VISUAL_REGION_BOTTOM))
                        try:
                            # Клик для фокуса в правой панели
                            focus_x = rx + min(rw - 8, 24)
                            focus_y = ry + min(rh - 8, 24)
                            pyautogui.click(focus_x, focus_y)
                            time.sleep(0.1)
                            # Протяжка выделения до низа панели
                            end_x = rx + max(8, rw - 24)
                            end_y = ry + max(8, rh - 24)
                            pyautogui.mouseDown(focus_x, focus_y)
                            time.sleep(0.05)
                            pyautogui.moveTo(end_x, end_y, duration=0.15)
                            time.sleep(0.05)
                            pyautogui.mouseUp(end_x, end_y)
                            time.sleep(0.1)
                            pyautogui.hotkey('command', 'c')
                            time.sleep(0.2)
                            short_txt = (pyperclip.paste() or '').strip()
                            self.telemetry.last_copy_method = 'drag'
                            self.telemetry.last_click_xy = (focus_x, focus_y)
                        except Exception:
                            short_txt = ''
                # 1) Если не получилось — попробуем клавиатурную навигацию к последнему ответу и копирование
                #    В строгом режиме по опорному пикселю этот путь отключаем, чтобы не захватывать редактор
                if not short_txt and not READY_PIXEL_REQUIRED:
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
                        short_txt = (pyperclip.paste() or '').strip()
                        self.telemetry.last_copy_method = 'short'
                    except Exception:
                        short_txt = ''
                disable_echo = (ready_by in ('ready_pixel', 'pixel'))
                # Обрежем всё до и включая вопрос, чтобы оставить только ответ
                processed_short = extract_answer_by_prompt(str(message), short_txt) if READY_PIXEL_REQUIRED else short_txt
                if processed_short and (disable_echo or not self._looks_like_echo(str(message), processed_short)):
                    copied_text = processed_short
                    self.telemetry.last_copy_is_echo = False
                    self.telemetry.last_copy_length = len(copied_text)
                    final_full = ''
                else:
                    # 1) Если короткое не удалось — кликаем по абсолютной точке (если задана) или в правую треть и копируем весь текст
                    bounds = None
                    try:
                        bounds = self._mac_manager.get_front_window_bounds() if self._mac_manager else None
                    except Exception:
                        bounds = None
                    if bounds:
                        x, y, w, h = bounds
                        # Берём АКТУАЛЬНЫЕ значения из ENV на момент клика, чтобы не требовать рестарт бота
                        try:
                            load_dotenv(override=True)
                        except Exception:
                            pass
                        # 1) Координаты в процентах от окна (если заданы)
                        used_winpct = False
                        try:
                            winpct_raw = os.getenv("CLICK_WINPCT", "").strip()
                        except Exception:
                            winpct_raw = ""
                        wp_x = wp_y = None
                        if winpct_raw and "," in winpct_raw:
                            try:
                                sx, sy = winpct_raw.split(",", 1)
                                wp_x = float(sx.strip())
                                wp_y = float(sy.strip())
                            except Exception:
                                wp_x = wp_y = None
                        if wp_x is None or wp_y is None:
                            try:
                                wp_x = float(os.getenv("CLICK_WINPCT_X", ""))
                                wp_y = float(os.getenv("CLICK_WINPCT_Y", ""))
                            except Exception:
                                wp_x = wp_x if isinstance(wp_x, float) else None
                                wp_y = wp_y if isinstance(wp_y, float) else None
                        if isinstance(wp_x, float) and isinstance(wp_y, float):
                            # clamp to [0,1]
                            px = max(0.0, min(1.0, wp_x))
                            py = max(0.0, min(1.0, wp_y))
                            click_x = int(x + px * w)
                            click_y = int(y + py * h)
                            used_winpct = True

                        # 2) Абсолютные координаты (если заданы и режим winpct не использован)
                        if not used_winpct:
                            try:
                                cx_env = int(os.getenv("CLICK_ABS_X", str(CLICK_ABS_X)))
                            except Exception:
                                cx_env = CLICK_ABS_X
                            try:
                                cy_env = int(os.getenv("CLICK_ABS_Y", str(CLICK_ABS_Y)))
                            except Exception:
                                cy_env = CLICK_ABS_Y
                            if cx_env >= 0 and cy_env >= 0:
                                click_x, click_y = cx_env, cy_env

                        # 3) Правый сектор окна (fallback)
                        if 'click_x' not in locals() or 'click_y' not in locals():
                            # Динамически подхватываем и параметры прицеливания
                            try:
                                rxf = float(os.getenv("RIGHT_CLICK_X_FRACTION", str(RIGHT_CLICK_X_FRACTION)))
                            except Exception:
                                rxf = RIGHT_CLICK_X_FRACTION
                            try:
                                ryo = int(os.getenv("RIGHT_CLICK_Y_OFFSET", str(RIGHT_CLICK_Y_OFFSET)))
                            except Exception:
                                ryo = RIGHT_CLICK_Y_OFFSET
                            try:
                                vtop = int(os.getenv("VISUAL_REGION_TOP", str(VISUAL_REGION_TOP)))
                            except Exception:
                                vtop = VISUAL_REGION_TOP
                            right_x0 = x + max(0, int(w * 2 / 3))
                            click_x = right_x0 + max(12, int((w / 3) * min(max(rxf, 0.05), 0.95)))
                            click_y = y + max(0, vtop) + max(0, int(ryo))
                        # Страховка: ограничим точку клика рамками окна и экрана, чтобы не "упираться" в углы
                        try:
                            sw, sh = pyautogui.size()
                        except Exception:
                            sw, sh = None, None
                        if isinstance(sw, int) and isinstance(sh, int) and sw > 0 and sh > 0:
                            click_x = max(0, min(sw - 1, int(click_x)))
                            click_y = max(0, min(sh - 1, int(click_y)))
                        # внутри окна с небольшим отступом от рамок
                        click_x = max(x + 6, min(x + w - 6, int(click_x)))
                        click_y = max(y + 6, min(y + h - 6, int(click_y)))
                        try:
                            # Сохраним скриншот области вокруг точки клика для диагностики (с маркером)
                            if SAVE_VISUAL_DEBUG:
                                try:
                                    ts = int(time.time())
                                    sw, sh = pyautogui.size()
                                    cw, ch = 280, 200  # ширина/высота области вокруг клика
                                    rx = max(0, min(sw - cw, int(click_x - cw / 2)))
                                    ry = max(0, min(sh - ch, int(click_y - ch / 2)))
                                    dbg_img = pyautogui.screenshot(region=(rx, ry, cw, ch))
                                    try:
                                        from PIL import ImageDraw
                                        d = ImageDraw.Draw(dbg_img)
                                        d.line([(cw//2 - 10, ch//2), (cw//2 + 10, ch//2)], fill=(255,0,0), width=2)
                                        d.line([(cw//2, ch//2 - 10), (cw//2, ch//2 + 10)], fill=(255,0,0), width=2)
                                    except Exception:
                                        pass
                                    os.makedirs(SAVE_VISUAL_DIR, exist_ok=True)
                                    dbg_img.save(os.path.join(SAVE_VISUAL_DIR, f"visual_click_{ts}_{rx}x{ry}_{cw}x{ch}.png"))
                                    # Дополнительно: полноэкранный снимок с крестом в реальной точке клика
                                    try:
                                        fs = pyautogui.screenshot()
                                        from PIL import ImageDraw
                                        d2 = ImageDraw.Draw(fs)
                                        d2.line([(click_x - 12, click_y), (click_x + 12, click_y)], fill=(0,255,0), width=3)
                                        d2.line([(click_x, click_y - 12), (click_x, click_y + 12)], fill=(0,255,0), width=3)
                                        max_w = 1600
                                        if fs.width > max_w:
                                            ratio = max_w / fs.width
                                            fs = fs.resize((max_w, int(fs.height * ratio)))
                                        fs.save(os.path.join(SAVE_VISUAL_DIR, f"visual_click_USED_FULL_{ts}_{click_x}x{click_y}.png"))
                                    except Exception:
                                        pass
                                except Exception:
                                    pass
                            pyautogui.click(click_x, click_y)
                            self.telemetry.last_click_xy = (click_x, click_y)
                            time.sleep(0.2)
                        except Exception:
                            pass
                    # Сохраним и финальный регион, если включен отладочный режим
                    if SAVE_VISUAL_DEBUG and bounds:
                        try:
                            right_third_x = x + max(0, int(w * 2 / 3))
                            rx = max(0, right_third_x + 8)
                            ry = max(0, y + max(0, VISUAL_REGION_TOP))
                            rw = max(16, int(w / 3) - 16)
                            rh = max(24, h - max(0, VISUAL_REGION_TOP) - max(0, VISUAL_REGION_BOTTOM))
                            fin_img = pyautogui.screenshot(region=(rx, ry, rw, rh))
                            os.makedirs(SAVE_VISUAL_DIR, exist_ok=True)
                            ts = time.strftime("%Y%m%d_%H%M%S")
                            ms = int((time.time() % 1) * 1000)
                            fin_img.save(os.path.join(SAVE_VISUAL_DIR, f"visual_region_final_{ts}_{ms:03d}.png"))
                        except Exception as _e:
                            logger.debug(f"save final visual debug failed: {_e}")
                    # Выделение содержимого правой панели протяжкой вверх с автоскроллом (без Cmd+A)
                    try:
                        final_full, region = copy_from_right_panel((x, y, w, h))
                        self.telemetry.last_visual_region = region
                        self.telemetry.last_copy_method = 'drag_full'
                    except Exception:
                        final_full = ""
            except Exception:
                final_full = ""
            # Обрежем ответ по последнему вхождению вопроса, если строгий режим включён
            if READY_PIXEL_REQUIRED and final_full:
                try:
                    final_full = extract_answer_by_prompt(str(message), final_full)
                except Exception:
                    pass
            if final_full:
                suffix = self._lcp_suffix(baseline_full or "", final_full)
                if suffix and suffix.strip() and (disable_echo or not self._looks_like_echo(str(message), suffix)):
                    copied_text = suffix
                    self.telemetry.last_copy_method = 'full'
                    self.telemetry.last_copy_is_echo = False
                    self.telemetry.last_copy_length = len(copied_text)
                    self.telemetry.last_full_copy_length = len(final_full or '')
                else:
                    # если суффикс пуст/эхо — попробуем взять весь финальный
                    if disable_echo or not self._looks_like_echo(str(message), final_full):
                        copied_text = final_full
                        self.telemetry.last_copy_method = 'full'
                        self.telemetry.last_copy_is_echo = False
                        self.telemetry.last_copy_length = len(copied_text)
                        self.telemetry.last_full_copy_length = len(final_full or '')
                    else:
                        logger.warning("Финальный полный текст выглядит как эхо — попробую короткое копирование (macOS)")
                        # Попробуем fallback на короткое копирование
                        if USE_COPY_SHORT_FALLBACK:
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
                                short_txt = (pyperclip.paste() or '').strip()
                            except Exception:
                                short_txt = ''
                            if short_txt and (disable_echo or not self._looks_like_echo(str(message), short_txt)):
                                copied_text = short_txt
                                self.telemetry.last_copy_method = 'short'
                                self.telemetry.last_copy_is_echo = False
                                self.telemetry.last_copy_length = len(copied_text)
                            else:
                                logger.warning(
                                    "Короткое копирование не дало результата или эхо (macOS). "
                                    f"last_visual_region={self.telemetry.last_visual_region}, last_click_xy={self.telemetry.last_click_xy}"
                                )

        # finalize metrics for macOS readiness loop
        ready = bool(copied_text)
        self.telemetry.response_wait_loops = loops
        self.telemetry.response_ready_time = round(time.time() - start, 2)
        self.telemetry.response_stabilized = ready
        self.telemetry.response_stabilized_by = ready_by if ready else None
        return ready, copied_text
    


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

                # 1) Гарантируем фокус кликом в правую панель (область ответа)
                try:
                    bounds = self._mac_manager.get_front_window_bounds() if self._mac_manager else None
                except Exception:
                    bounds = None
                if bounds:
                    try:
                        # перечитаем .env динамически и возьмем ANSWER_ABS_X/Y, если заданы
                        try:
                            load_dotenv(override=True)
                        except Exception:
                            pass
                        x, y, w, h = bounds
                        ax = os.getenv("ANSWER_ABS_X")
                        ay = os.getenv("ANSWER_ABS_Y")
                        focus_x = None
                        focus_y = None
                        try:
                            if ax is not None and ay is not None:
                                ax_i = int(str(ax).strip())
                                ay_i = int(str(ay).strip())
                                if ax_i >= 0 and ay_i >= 0:
                                    focus_x, focus_y = ax_i, ay_i
                        except Exception:
                            focus_x = focus_y = None
                        if focus_x is None or focus_y is None:
                            # fallback: правая треть окна (панель ответа)
                            right_third_x = x + max(0, int(w * 2 / 3))
                            rx = max(0, right_third_x + 8)
                            ry = max(0, y + max(0, VISUAL_REGION_TOP))
                            rw = max(16, int(w / 3) - 16)
                            rh = max(24, h - max(0, VISUAL_REGION_TOP) - max(0, VISUAL_REGION_BOTTOM))
                            focus_x = rx + min(rw - 8, 24)
                            focus_y = ry + min(rh - 8, 24)
                        # Клампим координаты к экрану и (дополнительно) к окну
                        try:
                            sw, sh = pyautogui.size()
                        except Exception:
                            sw = sh = None
                        if isinstance(sw, int) and isinstance(sh, int) and sw > 0 and sh > 0:
                            focus_x = max(0, min(sw - 1, int(focus_x)))
                            focus_y = max(0, min(sh - 1, int(focus_y)))
                        # Внутри окна с небольшими отступами
                        fx = max(x + 6, min(x + w - 6, int(focus_x)))
                        fy = max(y + 6, min(y + h - 6, int(focus_y)))
                        pyautogui.click(fx, fy)
                        self.telemetry.last_click_xy = (fx, fy)
                        time.sleep(0.15)
                    except Exception:
                        pass

                # 2) Копируем в буфер и вставляем CMD+V с ретраями
                if not cb_copy(str(message)):
                    self.telemetry.failed_sends += 1
                    return False

                # НЕ используем Cmd+L на macOS — это иногда уводит фокус в терминал/панель

                pasted_ok = cb_paste_mac(str(message), PASTE_RETRY_COUNT)
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
                if not READY_PIXEL_REQUIRED:
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
                        self.telemetry.last_copy_method = 'short'
                    except Exception as e:
                        logger.debug(f"baseline copy (macOS) failed: {e}")
                ready, copied_text = self._wait_for_ready_mac(str(message), baseline_text)
                copied = ready
                if not ready and not READY_PIXEL_REQUIRED:
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
                # Для информации: длина полного текста при стабилизации
                try:
                    if USE_FULLTEXT_STABILIZATION:
                        self.telemetry.last_full_copy_length = len(last_full or "")
                except Exception:
                    pass
                # Очистка и запись ответа в буфер
                try:
                    raw_clip = copied_text or (pyperclip.paste() or "")
                    cleaned = clean_copied_text(str(message), raw_clip)
                    if cleaned and cleaned.strip():
                        pyperclip.copy(cleaned)
                        self.telemetry.last_copy_length = len(cleaned)
                        self.telemetry.last_copy_is_echo = self._looks_like_echo(str(message), cleaned)
                    else:
                        pyperclip.copy(raw_clip or "")
                except Exception as _e:
                    logger.debug(f"clean/copy failed: {_e}")
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
                if not cb_copy(str(message)):
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

                logger.info("Сообщение отправлено, ждем ответ ИИ (Windows)...")
                time.sleep(max(0.0, RESPONSE_WAIT_SECONDS))

                # Компактный путь копирования: выделяем правую панель по прямоугольнику окна и копируем
                logger.info("Копирую ответ из правой панели (Windows) через протяжку...")
                copied_text = ''
                try:
                    if main_window is not None:
                        rect = main_window.rectangle()
                        x, y, w, h = rect.left, rect.top, rect.width(), rect.height()
                        copied_text, region = copy_from_right_panel((x, y, w, h))
                        self.telemetry.last_visual_region = region
                        self.telemetry.last_copy_method = 'drag_full'
                except Exception as e:
                    logger.debug(f"windows drag copy failed: {e}")

                # Обрезка по запросу и очистка от UI-шума
                try:
                    processed = extract_answer_by_prompt(str(message), copied_text or "") if READY_PIXEL_REQUIRED else (copied_text or "")
                    cleaned = clean_copied_text(str(message), processed)
                    if cleaned:
                        pyperclip.copy(cleaned)
                        self.telemetry.last_copy_length = len(cleaned)
                        self.telemetry.last_copy_is_echo = self._looks_like_echo(str(message), cleaned)
                except Exception as e:
                    logger.debug(f"windows clean/copy failed: {e}")

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
