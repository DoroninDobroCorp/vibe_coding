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
from PIL import ImageChops, ImageStat, Image

# Новые модули рефакторинга
from core.config import config
from core.telemetry import Telemetry
from core.sleep_utils import sleep_interruptible as _sleep_interruptible
from core.pixel_utils import (
    rgb_at as _rgb_at,
    avg_rgb as _avg_rgb,
    avg_rgb_via_screencapture as _avg_rgb_via_screencapture,
    sample_rgb_consistent as _sample_rgb_consistent,
    map_ready_pixel_xy,
    measure_ready_pixel_rgb as _measure_ready_pixel_rgb,
)
try:
    import psutil  # для диагностики процессов Windsurf
except Exception:
    psutil = None
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

# Используем config вместо прямого чтения из os.getenv
WINDSURF_WINDOW_TITLE = config.WINDSURF_WINDOW_TITLE

# Диагностика процессов Windsurf для /status
def _scan_windsurf_processes():
    """Вернёт список процессов Windsurf с полями pid, name, cpu_percent. Безопасно при отсутствии psutil."""
    if psutil is None:
        return []
    procs = []
    try:
        for p in psutil.process_iter(["pid", "name", "cmdline", "cpu_percent"]):
            try:
                name = (p.info.get("name") or "")
                pid = int(p.info.get("pid") or p.pid)
                cpu = float(p.info.get("cpu_percent") or 0.0)
                cmd = p.info.get("cmdline") or []
                name_l = str(name).lower()
                cmd_s = " ".join(cmd).lower() if isinstance(cmd, list) else str(cmd).lower()
                if "windsurf" in name_l or "windsurf" in cmd_s:
                    procs.append({"pid": pid, "name": name, "cpu_percent": round(cpu, 2)})
            except Exception:
                continue
    except Exception as e:
        try:
            logger.debug(f"_scan_windsurf_processes failed: {e}")
        except Exception:
            pass
    return procs

# === Используем централизованный config вместо прямого чтения ENV ===
PASTE_RETRY_COUNT = config.PASTE_RETRY_COUNT
COPY_RETRY_COUNT = config.COPY_RETRY_COUNT
RESPONSE_WAIT_SECONDS = config.RESPONSE_WAIT_SECONDS
KEY_DELAY_SECONDS = config.KEY_DELAY_SECONDS
RESPONSE_MAX_WAIT_SECONDS = config.RESPONSE_MAX_WAIT_SECONDS
RESPONSE_POLL_INTERVAL_SECONDS = config.RESPONSE_POLL_INTERVAL_SECONDS
RESPONSE_STABLE_MIN_SECONDS = config.RESPONSE_STABLE_MIN_SECONDS
USE_APPLESCRIPT_ON_MAC = config.USE_APPLESCRIPT_ON_MAC
USE_FULLTEXT_STABILIZATION = config.USE_FULLTEXT_STABILIZATION
USE_CPU_READY_DETECTION = config.USE_CPU_READY_DETECTION
CPU_READY_THRESHOLD = config.CPU_READY_THRESHOLD
CPU_READY_STABLE_SECONDS = config.CPU_READY_STABLE_SECONDS
CPU_SAMPLE_INTERVAL_SECONDS = config.CPU_SAMPLE_INTERVAL_SECONDS
USE_UI_BUTTON_DETECTION = config.USE_UI_BUTTON_DETECTION
SEND_BTN_REGION_RIGHT = config.SEND_BTN_REGION_RIGHT
SEND_BTN_REGION_BOTTOM = config.SEND_BTN_REGION_BOTTOM
SEND_BTN_REGION_W = config.SEND_BTN_REGION_W
SEND_BTN_REGION_H = config.SEND_BTN_REGION_H
SEND_BTN_BLUE_DELTA = config.SEND_BTN_BLUE_DELTA
SEND_BTN_WHITE_BRIGHT = config.SEND_BTN_WHITE_BRIGHT
FRONTMOST_WAIT_SECONDS = config.FRONTMOST_WAIT_SECONDS
FOCUS_RETRY_COUNT = config.FOCUS_RETRY_COUNT
USE_VISUAL_STABILITY = config.USE_VISUAL_STABILITY
VISUAL_REGION_TOP = config.VISUAL_REGION_TOP
VISUAL_REGION_BOTTOM = config.VISUAL_REGION_BOTTOM
VISUAL_SAMPLE_INTERVAL_SECONDS = config.VISUAL_SAMPLE_INTERVAL_SECONDS
VISUAL_DIFF_THRESHOLD = config.VISUAL_DIFF_THRESHOLD
VISUAL_STABLE_SECONDS = config.VISUAL_STABLE_SECONDS
SAVE_VISUAL_DEBUG = config.SAVE_VISUAL_DEBUG
SAVE_VISUAL_DIR = config.SAVE_VISUAL_DIR
USE_COPY_SHORT_FALLBACK = config.USE_COPY_SHORT_FALLBACK
RIGHT_CLICK_X_FRACTION = config.RIGHT_CLICK_X_FRACTION
RIGHT_CLICK_Y_OFFSET = config.RIGHT_CLICK_Y_OFFSET
ECHO_FILTER_ENABLED = config.ECHO_FILTER_ENABLED
ECHO_PREFIX_LEN = config.ECHO_PREFIX_LEN
ECHO_MAX_DELTA = config.ECHO_MAX_DELTA
ECHO_LEN_RATIO = config.ECHO_LEN_RATIO
USE_READY_PIXEL = config.USE_READY_PIXEL
READY_PIXEL_REQUIRED = config.READY_PIXEL_REQUIRED
TRIM_AFTER_PROMPT = config.TRIM_AFTER_PROMPT
READY_PIXEL_X = config.READY_PIXEL_X
READY_PIXEL_Y = config.READY_PIXEL_Y
READY_PIXEL_R = config.READY_PIXEL_R
READY_PIXEL_G = config.READY_PIXEL_G
READY_PIXEL_B = config.READY_PIXEL_B
READY_PIXEL_TOL = config.READY_PIXEL_TOL
READY_PIXEL_TOL_PCT = config.READY_PIXEL_TOL_PCT
READY_PIXEL_COORD_MODE = config.READY_PIXEL_COORD_MODE
READY_PIXEL_DX = config.READY_PIXEL_DX
READY_PIXEL_DY = config.READY_PIXEL_DY
READY_PIXEL_PROBE_INTERVAL_SECONDS = config.READY_PIXEL_PROBE_INTERVAL_SECONDS
READY_PIXEL_AVG_K = config.READY_PIXEL_AVG_K
READY_PIXEL_REQUIRE_TRANSITION = config.READY_PIXEL_REQUIRE_TRANSITION
READY_PIXEL_STABLE_SECONDS = config.READY_PIXEL_STABLE_SECONDS
READY_PIXEL_TRANSITION_TIMEOUT_SECONDS = config.READY_PIXEL_TRANSITION_TIMEOUT_SECONDS
CLICK_ABS_X = config.CLICK_ABS_X
CLICK_ABS_Y = config.CLICK_ABS_Y
SAVE_READY_HYPOTHESES = config.SAVE_READY_HYPOTHESES
SAVE_READY_ONLY_ON_MATCH = config.SAVE_READY_ONLY_ON_MATCH
ENV_RELOAD_INTERVAL_SECONDS = config.ENV_RELOAD_INTERVAL_SECONDS
WSMODEL_RESTORE_CLIPBOARD = config.WSMODEL_RESTORE_CLIPBOARD

# === Дублирующиеся функции удалены — используем core.pixel_utils ===
# map_ready_pixel_xy, _rgb_at, _avg_rgb, _avg_rgb_via_screencapture, _sanitize_k,
# _sample_rgb_consistent, _measure_ready_pixel_rgb
# теперь импортируются из core.pixel_utils

# Telemetry теперь импортируется из core.telemetry вместо локального класса


class DesktopController:
    def __init__(self):
        self.is_ready = False
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = max(0.1, KEY_DELAY_SECONDS)
        self.telemetry = Telemetry()
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
        last_ready_probe = 0.0  # Время последней проверки READY_PIXEL
        # Для логики стабильности и перехода non-match -> match
        seen_nonmatch = False
        match_started_at = None
        transition_deadline = None
        try:
            _transition_timeout = float(READY_PIXEL_TRANSITION_TIMEOUT_SECONDS)
        except Exception:
            _transition_timeout = 25.0
        if READY_PIXEL_REQUIRE_TRANSITION:
            transition_deadline = (start + _transition_timeout) if _transition_timeout and _transition_timeout > 0 else None
        # READY_PIXEL-only режим: не отправляем никаких хоткеев во время ожидания
        baseline_full = ""
        logger.info("macOS: ожидание READY_PIXEL — без отправки каких-либо клавиш/копирования до готовности")

        loops = 0
        ready_by = None  # 'visual' | 'pixel'
        # Визуальная стабилизация — отключено (оставляем только READY_PIXEL)
        visual_prev_small = None
        last_visual_change = start
        last_visual_sample = 0.0
        # Упростили детекцию: без edge/стабилизации и без динамической перезагрузки .env
        last_env_reload = start - ENV_RELOAD_INTERVAL_SECONDS

        # Если RESPONSE_MAX_WAIT_SECONDS<=0 — ждём бесконечно (пока не совпадёт READY_PIXEL)
        while True:
            # Прерывание по таймауту только если он задан (>0)
            if RESPONSE_MAX_WAIT_SECONDS and RESPONSE_MAX_WAIT_SECONDS > 0:
                if time.time() - start >= RESPONSE_MAX_WAIT_SECONDS:
                    break
            loops += 1

            # 1) Визуальная стабилизация — отключено намеренно
            _use_vs = False
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

            # 2) Пиксельная детекция кнопки — отключено намеренно
            if False and ready_by is None and USE_UI_BUTTON_DETECTION:
                ui_state, avg = self._classify_send_button_mac()
                self.telemetry.last_ui_button = ui_state
                self.telemetry.last_ui_avg_color = avg
                if ui_state == 'send':
                    ready_by = 'pixel'

            # 3) Датчик готовности по опорному пикселю (абсолютные координаты) с edge-логикой
            if ready_by is None and USE_READY_PIXEL and READY_PIXEL_X >= 0 and READY_PIXEL_Y >= 0 \
               and (time.time() - last_ready_probe) >= READY_PIXEL_PROBE_INTERVAL_SECONDS:
                last_ready_probe = time.time()
                try:
                    # Динамическая перезагрузка .env отключена по умолчанию для стабильности измерения
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
                    # Сэмплируем цвет с учетом READY_PIXEL_SRC (auto|cap|dir), как в пипетке (status)
                    (pr, pg, pb), used_src = _measure_ready_pixel_rgb(
                        int(sx), int(sy), max(1, int(READY_PIXEL_AVG_K)), (rp_r, rp_g, rp_b)
                    )
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
                        'rgb': (int(pr), int(pg), int(pb)), 'src': used_src,
                        'target': (rp_r, rp_g, rp_b),
                        'tol': rp_tol,
                        'tol_pct': rp_tol_pct if rp_tol_pct is not None and rp_tol_pct >= 0 else None,
                        'delta': (dr, dg, db), 'match': match,
                    }
                    # Логика перехода (edge)
                    now_ts = time.time()
                    if not match:
                        seen_nonmatch = True
                        match_started_at = None
                        logger.info(
                            "READY_PIXEL проверка: used_xy=(%d,%d) цвет=(%d,%d,%d) не подходит; жду %.1fs",
                            sx, sy, int(pr), int(pg), int(pb), READY_PIXEL_PROBE_INTERVAL_SECONDS
                        )
                        _sleep_interruptible(float(READY_PIXEL_PROBE_INTERVAL_SECONDS))
                        continue
                    # Тут match == True
                    if READY_PIXEL_REQUIRE_TRANSITION and not seen_nonmatch:
                        # Требуем увидеть хотя бы один non-match после отправки
                        # Если задан таймаут перехода и он истёк — либо принимаем (если timeout<=0 не задан), либо продолжаем ждать
                        if transition_deadline is not None and now_ts >= transition_deadline:
                            logger.info("READY_PIXEL: переход non-match->match не зафиксирован до таймаута, продолжаю ожидать совпадение...")
                            _sleep_interruptible(float(READY_PIXEL_PROBE_INTERVAL_SECONDS))
                            continue
                    # Стабильность совпадения
                    if match_started_at is None:
                        match_started_at = now_ts
                    stable_for = now_ts - match_started_at
                    if stable_for < max(0.0, READY_PIXEL_STABLE_SECONDS):
                        logger.info("READY_PIXEL: совпадение, но ждём стабильность %.1fs (уже %.2fs)", READY_PIXEL_STABLE_SECONDS, stable_for)
                        _sleep_interruptible(float(READY_PIXEL_PROBE_INTERVAL_SECONDS))
                        continue
                    # Все условия выполнены
                    ready_by = 'ready_pixel'
                    # Сохраняем снимки (умолчание: только при совпадении и не сохраняем гипотезы)
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

            # Короткий прерывный сон, чтобы Ctrl+C срабатывал мгновенно
            _sleep_interruptible(max(0.05, float(RESPONSE_POLL_INTERVAL_SECONDS)))

        # Финальный сбор текста
        copied_text = ""
        if ready_by is not None and (not READY_PIXEL_REQUIRED or ready_by == 'ready_pixel'):
            try:
                # 0) Если включён строгий режим — выделим текст мышью в правой панели и скопируем
                short_txt = ''
                if False and READY_PIXEL_REQUIRED and self._mac_manager:
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
                # Обрезка по запросу и очистка от UI-шума
                processed_short = extract_answer_by_prompt(str(message), short_txt) if TRIM_AFTER_PROMPT else short_txt
                if processed_short and (disable_echo or not self._looks_like_echo(str(message), processed_short)):
                    copied_text = processed_short
                    self.telemetry.last_copy_is_echo = False
                    self.telemetry.last_copy_length = len(copied_text)
                    final_full = ''
                else:
                    # 1) Полное копирование: клик по ANSWER_ABS_X/Y, скролл вниз до конца и протяжка c автоскроллом
                    bounds = None
                    try:
                        bounds = self._mac_manager.get_front_window_bounds() if self._mac_manager else None
                    except Exception:
                        bounds = None
                    if bounds:
                        x, y, w, h = bounds
                        # Точка клика — только ANSWER_ABS_X/Y; если не заданы — fallback в правой панели
                        try:
                            ax = int(os.getenv("ANSWER_ABS_X", "-1"))
                            ay = int(os.getenv("ANSWER_ABS_Y", "-1"))
                        except Exception:
                            ax = ay = -1
                        if ax >= 0 and ay >= 0:
                            click_x, click_y = ax, ay
                        else:
                            right_third_x = x + max(0, int(w * 2 / 3))
                            rx = max(0, right_third_x + 8)
                            ry = max(0, y + max(0, VISUAL_REGION_TOP))
                            rw = max(16, int(w / 3) - 16)
                            rh = max(24, h - max(0, VISUAL_REGION_TOP) - max(0, VISUAL_REGION_BOTTOM))
                            click_x = rx + max(12, int(rw * 0.9))
                            click_y = ry + max(12, int(rh * 0.9))
                        # Страховка: ограничим точку клика рамками окна и экрана
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
                            # Защита от клика по зоне READY_PIXEL
                            do_click = True
                            if USE_READY_PIXEL and READY_PIXEL_X >= 0 and READY_PIXEL_Y >= 0:
                                rp_sx, rp_sy = map_ready_pixel_xy(READY_PIXEL_X, READY_PIXEL_Y, READY_PIXEL_COORD_MODE, READY_PIXEL_DX, READY_PIXEL_DY)
                                dx = int(click_x) - int(rp_sx)
                                dy = int(click_y) - int(rp_sy)
                                ban_r = max(6, int(READY_PIXEL_TOL) + 4)
                                if (dx*dx + dy*dy) <= (ban_r * ban_r):
                                    logger.info(f"Пропускаю клик перед копированием: ({click_x},{click_y}) близко к READY_PIXEL ({rp_sx},{rp_sy}), r<={ban_r}")
                                    do_click = False
                            if do_click:
                                logger.info(f"Фокус перед копированием: click=({click_x},{click_y})")
                                pyautogui.click(click_x, click_y)
                                self.telemetry.last_click_xy = (click_x, click_y)
                                time.sleep(0.15)
                                # Прокрутка до самого низа, чтобы начать копирование с конца
                                for _ in range(12):
                                    pyautogui.scroll(-1000)
                                    time.sleep(0.04)
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
            # Обрезка по запросу и очистка от UI-шума
            if TRIM_AFTER_PROMPT and final_full:
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
            # Если задан таргет окна — пытаемся сфокусировать его
            desired_title: str | None = None
            desired_sub: str | None = None
            if target and target not in ("active", "default"):
                if target.startswith("index:"):
                    # Маппим индекс на заголовок из списка, чтобы избежать расхождений индексов в полноэкранном режиме
                    try:
                        idx = int(target.split(":", 1)[1])
                    except Exception:
                        idx = -1
                    titles = []
                    try:
                        titles = self._mac_manager.list_window_titles() or []
                    except Exception:
                        titles = []
                    if 1 <= idx <= len(titles):
                        desired_title = titles[idx - 1]
                        # Сначала пытаемся через меню Window/Окно (стабильно для полноэкранных)
                        ok = self._mac_manager.focus_by_title_menu(desired_title)
                        if not ok:
                            # Фоллбек: Accessibility индекс
                            ok = self._mac_manager.focus_by_index(idx)
                        if not ok and desired_title:
                            # Фоллбек: подстрока из заголовка
                            ok = self._mac_manager.focus_by_title_substring(desired_title)
                        if not ok:
                            logger.warning(f"Не удалось сфокусировать окно по индексу: {idx} -> '{desired_title}'")
                    else:
                        logger.warning(f"Некорректный индекс окна: {idx}; доступно: {len(titles)}")
                else:
                    desired_sub = str(target)
                    # Сначала меню Window/Окно, затем Accessibility по подстроке
                    ok = self._mac_manager.focus_by_title_menu(desired_sub)
                    if not ok:
                        ok = self._mac_manager.focus_by_title_substring(desired_sub)
                    if not ok:
                        logger.warning(f"Не удалось сфокусировать окно по заголовку: {target}")
            # Ждем, пока Windsurf станет frontmost; по возможности проверим, что активирован нужный заголовок
            start = time.time()
            while time.time() - start < FRONTMOST_WAIT_SECONDS:
                if self._mac_manager.is_frontmost():
                    if desired_title or desired_sub:
                        try:
                            ft = self._mac_manager.get_front_window_title() or ""
                        except Exception:
                            ft = ""
                        if desired_title:
                            l = ft.strip().lower(); r = desired_title.strip().lower()
                            if l == r or (l and r and (l in r or r in l)):
                                return True
                        elif desired_sub:
                            if desired_sub.strip().lower() in ft.strip().lower():
                                return True
                        # Иначе подождём ещё чуть-чуть
                    else:
                        return True
                time.sleep(0.1)
            logger.warning("Windsurf не стал frontmost или активировался не тот заголовок за отведенное время")
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
                focused_ok = self._ensure_windsurf_frontmost_mac(target or "active")
                if target and not focused_ok:
                    logger.warning(f"Фокусировка на целевом окне не удалась: target={target}")
                    self.telemetry.last_error = f"focus failed for target: {target}"
                    self.telemetry.failed_sends += 1
                    return False

                # 1) Гарантируем фокус кликом по полю ввода (если заданы INPUT_ABS_X/Y),
                #    иначе кликом в область ответа (ANSWER_ABS_X/Y) — только для фокуса приложения
                try:
                    bounds = self._mac_manager.get_front_window_bounds() if self._mac_manager else None
                except Exception:
                    bounds = None
                if bounds:
                    try:
                        x, y, w, h = bounds
                        detailed_log = False
                        try:
                            detailed_log = (os.getenv("DETAILED_AUTOMATION_LOG", "0").lower() not in ("0", "false", "no"))
                        except Exception:
                            detailed_log = False
                        if detailed_log:
                            logger.info(f"[Focus] window bounds (x={x}, y={y}, w={w}, h={h})")
                        ix = os.getenv("INPUT_ABS_X")
                        iy = os.getenv("INPUT_ABS_Y")
                        ax = os.getenv("ANSWER_ABS_X")
                        ay = os.getenv("ANSWER_ABS_Y")
                        focus_x = None
                        focus_y = None
                        try:
                            # приоритет: INPUT_ABS -> ANSWER_ABS
                            if ix is not None and iy is not None:
                                ix_i = int(str(ix).strip())
                                iy_i = int(str(iy).strip())
                                if ix_i >= 0 and iy_i >= 0:
                                    focus_x, focus_y = ix_i, iy_i
                            if focus_x is None and ax is not None and ay is not None:
                                ax_i = int(str(ax).strip())
                                ay_i = int(str(ay).strip())
                                if ax_i >= 0 and ay_i >= 0:
                                    focus_x, focus_y = ax_i, ay_i
                        except Exception:
                            focus_x = focus_y = None
                        if detailed_log:
                            logger.info(f"[Focus] requested coords: INPUT=({ix},{iy}) ANSWER=({ax},{ay}) -> chosen=({focus_x},{focus_y})")
                        # никаких fallback-ов: кликаем только по ANSWER_ABS_X/Y; если не заданы — пропускаем клик

                        # Клампим координаты к экрану и (дополнительно) к окну
                        try:
                            sw, sh = pyautogui.size()
                        except Exception:
                            sw = sh = None
                        if focus_x is not None and focus_y is not None:
                            if isinstance(sw, int) and isinstance(sh, int) and sw > 0 and sh > 0:
                                focus_x = max(0, min(sw - 1, int(focus_x)))
                                focus_y = max(0, min(sh - 1, int(focus_y)))
                                if detailed_log:
                                    logger.info(f"[Focus] screen size=({sw},{sh}) -> clamped focus=({focus_x},{focus_y})")
                            # Внутри окна с небольшими отступами
                            fx = max(x + 6, min(x + w - 6, int(focus_x)))
                            fy = max(y + 6, min(y + h - 6, int(focus_y)))
                            # Защита: не кликать, если рядом с READY_PIXEL (кнопка Stop)
                            try:
                                if USE_READY_PIXEL and READY_PIXEL_X >= 0 and READY_PIXEL_Y >= 0:
                                    rp_sx, rp_sy = map_ready_pixel_xy(READY_PIXEL_X, READY_PIXEL_Y, READY_PIXEL_COORD_MODE, READY_PIXEL_DX, READY_PIXEL_DY)
                                    dx = int(fx) - int(rp_sx)
                                    dy = int(fy) - int(rp_sy)
                                    # Радиус запрета: чуть больше допуска цвета
                                    ban_r = max(6, int(READY_PIXEL_TOL) + 4)
                                    if detailed_log:
                                        logger.info(f"[Focus] READY_PIXEL mapped=({rp_sx},{rp_sy}) tol={READY_PIXEL_TOL} ban_r={ban_r} base_click=({fx},{fy}) d2={dx*dx+dy*dy}")
                                    if (dx*dx + dy*dy) <= (ban_r * ban_r):
                                        logger.info(f"Фокус‑клик близко к READY_PIXEL, ищу безопасное смещение: base=({fx},{fy}) rp=({rp_sx},{rp_sy}) r<={ban_r}")
                                        # Попробуем несколько смещений, чтобы уйти от кнопки Stop, но остаться в окне
                                        candidates = [
                                            (-120, -60), (120, -60), (-160, 0), (160, 0), (0, -120), (0, 120)
                                        ]
                                        clicked = False
                                        for dxo, dyo in candidates:
                                            nfx = max(x + 6, min(x + w - 6, int(fx + dxo)))
                                            nfy = max(y + 6, min(y + h - 6, int(fy + dyo)))
                                            ndx = int(nfx) - int(rp_sx)
                                            ndy = int(nfy) - int(rp_sy)
                                            if detailed_log:
                                                logger.info(f"[Focus] try offset ({dxo},{dyo}) -> ({nfx},{nfy}) d2={ndx*ndx+ndy*ndy}")
                                            if (ndx*ndx + ndy*ndy) > (ban_r * ban_r):
                                                logger.info(f"Фокус‑клик (offset) по координатам: ({nfx},{nfy})")
                                                pyautogui.click(nfx, nfy)
                                                self.telemetry.last_click_xy = (nfx, nfy)
                                                clicked = True
                                                break
                                        if not clicked:
                                            # В крайнем случае кликаем по исходной точке
                                            logger.info(f"Фокус‑клик (forced) по координатам: ({fx},{fy})")
                                            pyautogui.click(fx, fy)
                                            self.telemetry.last_click_xy = (fx, fy)
                                    else:
                                        logger.info(f"Фокус‑клик по координатам: ({fx},{fy})")
                                        pyautogui.click(fx, fy)
                                        self.telemetry.last_click_xy = (fx, fy)
                                else:
                                    logger.info(f"Фокус‑клик по координатам: ({fx},{fy})")
                                    pyautogui.click(fx, fy)
                                    self.telemetry.last_click_xy = (fx, fy)
                            except Exception:
                                # На всякий случай делаем клик, если проверка не удалась
                                try:
                                    logger.info(f"Фокус‑клик (fallback) по координатам: ({fx},{fy})")
                                    pyautogui.click(fx, fy)
                                    self.telemetry.last_click_xy = (fx, fy)
                                except Exception:
                                    self.telemetry.last_click_xy = None
                            time.sleep(0.15)
                    except Exception:
                        pass

                # 2) Копируем в буфер и вставляем CMD+V с ретраями
                if detailed_log:
                    logger.info("[Paste] copying message to clipboard")
                if not cb_copy(str(message)):
                    self.telemetry.failed_sends += 1
                    return False

                # НЕ используем Cmd+L на macOS — это иногда уводит фокус в терминал/панель

                if detailed_log:
                    logger.info(f"[Paste] starting paste retries: count={PASTE_RETRY_COUNT}")
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
                # baseline: отключено, чтобы не прерывать генерацию
                baseline_text = ""
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
                # Диагностика финального ответа
                try:
                    final_len = int(self.telemetry.last_copy_length or 0)
                    full_len = int(self.telemetry.last_full_copy_length or 0)
                    method = self.telemetry.last_copy_method or '—'
                    echo_flag = bool(self.telemetry.last_copy_is_echo)
                    logger.info(
                        "Final response prepared: method=%s cleaned_len=%d full_len=%d echo=%s",
                        method, final_len, full_len, echo_flag,
                    )
                except Exception:
                    pass
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
                    processed = extract_answer_by_prompt(str(message), copied_text or "") if TRIM_AFTER_PROMPT else (copied_text or "")
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
        d = self.telemetry.to_dict()
        d.update({
            "platform": platform.system(),
            "windows_automation": WINDOWS_AUTOMATION_AVAILABLE,
            "windsurf_pids": _scan_windsurf_processes(),
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

    def set_model_ui(self, model_name: str, target: str | None = None) -> tuple[bool, str]:
        """Переключить модель в UI Windsurf (macOS): Cmd+/, ввести имя модели, Enter.
        target: None/"active" или 'index:N'/'<substring>' — см. _ensure_windsurf_frontmost_mac.
        Возвращает (ok, message)."""
        try:
            # Dry-run режим для самотестов: не трогаем UI, только фиксируем телеметрию
            if os.getenv("WSMODEL_DRY_RUN", "0").lower() not in ("0", "false"):
                self.telemetry.last_model_set = str(model_name)
                logger.info(f"[DRY-RUN] UI: (skip) переключил модель Windsurf -> {model_name}")
                return True, f"(dry-run) Модель переключена: {model_name}"
            if platform.system() != "Darwin":
                return False, "UI model switching поддерживается только на macOS"
            # Сфокусировать нужное окно Windsurf
            self._ensure_windsurf_frontmost_mac(target or "active")
            time.sleep(0.2)
            # Кликнуть в правую панель (ANSWER_ABS_X/Y), чтобы гарантировать фокус перед Cmd+/
            try:
                ax = int(os.getenv("ANSWER_ABS_X", "-1"))
                ay = int(os.getenv("ANSWER_ABS_Y", "-1"))
            except Exception:
                ax = ay = -1
            if ax >= 0 and ay >= 0:
                try:
                    sw, sh = pyautogui.size()
                except Exception:
                    sw = sh = 0
                cx = max(0, min(sw - 1, int(ax))) if sw else int(ax)
                cy = max(0, min(sh - 1, int(ay))) if sh else int(ay)
                try:
                    pyautogui.moveTo(cx, cy, duration=0.05)
                    pyautogui.click()
                    self.telemetry.last_click_xy = (cx, cy)
                    time.sleep(0.15)
                except Exception:
                    pass
            # Открыть палитру команд и ввести запрос (через буфер, чтобы избежать раскладки)
            pyautogui.hotkey('command', '/')
            time.sleep(0.25)
            # Очистим строку
            pyautogui.hotkey('command', 'a')
            time.sleep(0.05)
            # Подготовим буфер обмена
            old_clip = None
            try:
                if WSMODEL_RESTORE_CLIPBOARD:
                    old_clip = pyperclip.paste()
            except Exception:
                old_clip = None
            try:
                pyperclip.copy(str(model_name))
                time.sleep(0.05)
            except Exception:
                pass
            pyautogui.hotkey('command', 'v')
            time.sleep(0.2)
            # Подтверждение кликом (вместо Enter)
            try:
                sw, sh = pyautogui.size()
            except Exception:
                sw = sh = 0
            cx = int(WSMODEL_CONFIRM_CLICK_X)
            cy = int(WSMODEL_CONFIRM_CLICK_Y)
            # Спец. условие для /wsmodel set: проверяем пиксель в точке (по умолчанию 1179,728)
            # Если он "белый" (>=254 по всем каналам), то финальный клик смещаем на безопасную точку
            # Делаем двойное измерение (direct + screencapture) и логируем детали.
            try:
                # Кламп координаты измерения в пределах экрана
                try:
                    sx = int(os.getenv("WSMODEL_PROBE_X", "1179").strip())
                except Exception:
                    sx = 1179
                try:
                    sy = int(os.getenv("WSMODEL_PROBE_Y", "728").strip())
                except Exception:
                    sy = 728
                if sw and sh:
                    sx = max(0, min(sw - 1, sx))
                    sy = max(0, min(sh - 1, sy))
                # Переместим курсор к точке проверки и подождём 1.5s, чтобы визуально видеть где измеряем
                try:
                    logger.info("wsmodel confirm: навожу курсор на точку проверки (%d,%d) и жду 1.5s", sx, sy)
                    pyautogui.moveTo(sx, sy, duration=0.05)
                except Exception:
                    pass
                time.sleep(1.5)
                pr1, pg1, pb1 = _rgb_at(sx, sy)
                pr2, pg2, pb2 = _avg_rgb_via_screencapture(sx, sy, 1)
                is_white_direct = (int(pr1) >= 254 and int(pg1) >= 254 and int(pb1) >= 254)
                is_white_cap = (int(pr2) >= 254 and int(pg2) >= 254 and int(pb2) >= 254)
                logger.info(
                    "wsmodel confirm probe @(%d,%d): direct=(%d,%d,%d) cap=(%d,%d,%d) -> white_direct=%s white_cap=%s",
                    sx, sy, int(pr1), int(pg1), int(pb1), int(pr2), int(pg2), int(pb2), is_white_direct, is_white_cap,
                )
                if is_white_direct or is_white_cap:
                    # Безопасная точка подтверждения (ENV override)
                    try:
                        safe_x = int(os.getenv("WSMODEL_CONFIRM_SAFE_X", "1130").strip())
                    except Exception:
                        safe_x = 1130
                    try:
                        safe_y = int(os.getenv("WSMODEL_CONFIRM_SAFE_Y", "695").strip())
                    except Exception:
                        safe_y = 695
                    logger.info("wsmodel confirm: белый фон обнаружен — смещаю клик на (%d,%d)", safe_x, safe_y)
                    cx, cy = safe_x, safe_y
                else:
                    logger.info("wsmodel confirm: белый фон НЕ обнаружен — кликаю по стандартным (%d,%d)", cx, cy)
            except Exception as e:
                logger.warning(f"wsmodel confirm probe failed: {e}")
            if cx >= 0 and cy >= 0:
                ccx = max(0, min((sw - 1) if sw else cx, cx))
                ccy = max(0, min((sh - 1) if sh else cy, cy))
                try:
                    logger.info("wsmodel confirm click at (%d,%d) [clamped from (%d,%d)]", ccx, ccy, cx, cy)
                    pyautogui.moveTo(ccx, ccy, duration=0.05)
                    pyautogui.click()
                    time.sleep(0.2)
                except Exception:
                    # Фоллбэк — Enter, если клик не удался
                    pyautogui.press('enter')
            else:
                pyautogui.press('enter')
            # Восстановим буфер, если нужно
            try:
                if WSMODEL_RESTORE_CLIPBOARD and (old_clip is not None):
                    pyperclip.copy(old_clip)
            except Exception:
                pass
            self.telemetry.last_model_set = str(model_name)
            logger.info(f"UI: переключил модель Windsurf -> {model_name}")
            return True, f"Модель переключена: {model_name}"
        except Exception as e:
            self.telemetry.last_error = f"set_model_ui failed: {e}"
            logger.warning(f"set_model_ui failed: {e}")
            return False, f"Ошибка переключения модели: {e}"


    def newchat_click(self, target: str | None = None) -> tuple[bool, str]:
        """Клик по координатам (1192, 51) для открытия нового чата в UI Windsurf (macOS)."""
        try:
            if platform.system() != "Darwin":
                return False, "Команда поддерживается только на macOS"
            # Сфокусировать окно Windsurf
            try:
                self._ensure_windsurf_frontmost_mac(target or "active")
            except Exception:
                pass
            time.sleep(0.1)
            try:
                sw, sh = pyautogui.size()
            except Exception:
                sw = sh = 0
            x, y = 1192, 51
            cx = max(0, min((sw - 1) if sw else x, x))
            cy = max(0, min((sh - 1) if sh else y, y))
            try:
                pyautogui.moveTo(cx, cy, duration=0.05)
                pyautogui.click()
                self.telemetry.last_click_xy = (cx, cy)
            except Exception as e:
                return False, f"Клик не удался: {e}"
            return True, "Новый чат открыт (клик по координатам)"
        except Exception as e:
            self.telemetry.last_error = f"newchat_click failed: {e}"
            return False, f"Ошибка newchat: {e}"

    def change_project(self, folder_name: str, target: str | None = None) -> tuple[bool, str]:
        """Открыть папку ~/VovkaNowEngineer/<folder_name> в указанном окне Windsurf и развернуть на весь экран (macOS).
        target: None/"active" или 'index:N'/'<substring>' — см. _ensure_windsurf_frontmost_mac.
        """
        try:
            if not folder_name or not str(folder_name).strip():
                return False, "Папка не указана"
            base = os.path.join(os.path.expanduser("~"), "VovkaNowEngineer")
            dest = os.path.join(base, folder_name.strip())
            if not os.path.isdir(dest):
                return False, f"Каталог не найден: {dest}"
            if platform.system() == "Darwin":
                # 1) UI-путь (предпочтительно): переиспользовать текущее окно через Cmd+O → Cmd+Shift+G → путь → Enter → Enter
                try:
                    logger.info("change_project: switching to %s via Open dialog in current window", dest)
                    self._ensure_windsurf_frontmost_mac(target or "active")
                except Exception:
                    pass
                time.sleep(0.2)
                try:
                    pyautogui.hotkey('command', 'o')
                    time.sleep(0.35)
                    pyautogui.hotkey('command', 'shift', 'g')  # Go to Folder
                    time.sleep(0.25)
                    old_clip = None
                    if WSMODEL_RESTORE_CLIPBOARD:
                        try:
                            old_clip = pyperclip.paste()
                        except Exception:
                            old_clip = None
                    try:
                        pyperclip.copy(dest)
                        time.sleep(0.07)
                    except Exception:
                        pass
                    pyautogui.hotkey('command', 'v')
                    time.sleep(0.12)
                    pyautogui.press('enter')  # go
                    time.sleep(0.35)
                    pyautogui.press('enter')  # open in current window
                    # Дать времени окну перегрузиться
                    time.sleep(0.8)
                    # Разворачиваем в полноэкранный режим (macOS стандарт)
                    pyautogui.hotkey('command', 'control', 'f')
                    # Подождём, чтобы UI устаканился, прежде чем проверять пиксель
                    logger.info("change_project: жду 3s перед финальной проверкой пикселя...")
                    time.sleep(3.0)
                    # Финальное действие: кликнуть в (1205,15), НО пропустить,
                    # если цвет равен 127,126,122 или 51,51,51 (по direct или screencapture)
                    try:
                        try:
                            sw, sh = pyautogui.size()
                        except Exception:
                            sw = sh = 0
                        # Точка финальной проверки (ENV override), по умолчанию 1205,15
                        try:
                            tx = int(os.getenv("CHANGE_FINAL_PROBE_X", "1205").strip())
                        except Exception:
                            tx = 1205
                        try:
                            ty = int(os.getenv("CHANGE_FINAL_PROBE_Y", "15").strip())
                        except Exception:
                            ty = 15
                        if sw and sh:
                            tx = max(0, min(sw - 1, tx))
                            ty = max(0, min(sh - 1, ty))
                        # Наведём курсор к точке финальной проверки и дадим время 1.5s
                        try:
                            logger.info("change_project: навожу курсор на точку финальной проверки (%d,%d) и жду 1.5s", tx, ty)
                            pyautogui.moveTo(tx, ty, duration=0.05)
                        except Exception:
                            pass
                        time.sleep(1.5)
                        r1, g1, b1 = _rgb_at(tx, ty)
                        r2, g2, b2 = _avg_rgb_via_screencapture(tx, ty, 1)
                        forbid1 = (int(r1) == 127 and int(g1) == 126 and int(b1) == 122) or (int(r1) == 51 and int(g1) == 51 and int(b1) == 51)
                        forbid2 = (int(r2) == 127 and int(g2) == 126 and int(b2) == 122) or (int(r2) == 51 and int(g2) == 51 and int(b2) == 51)
                        logger.info(
                            "change_project final probe @(1205,15)->@(%d,%d): direct=(%d,%d,%d) cap=(%d,%d,%d) forbid_direct=%s forbid_cap=%s",
                            tx, ty, int(r1), int(g1), int(b1), int(r2), int(g2), int(b2), forbid1, forbid2,
                        )
                        if not (forbid1 or forbid2):
                            pyautogui.moveTo(tx, ty, duration=0.05)
                            pyautogui.click()
                            logger.info("change_project: финальный клик по (%d,%d)", tx, ty)
                        else:
                            logger.info("change_project: финальный клик пропущен из-за запрещённого цвета")
                    except Exception as _e:
                        logger.warning(f"change_project final click check failed: {_e}")
                    if WSMODEL_RESTORE_CLIPBOARD and (old_clip is not None):
                        try:
                            pyperclip.copy(old_clip)
                        except Exception:
                            pass
                    return True, f"Открыт проект и развернут на весь экран: {dest}"
                except Exception as e:
                    logger.warning(f"change_project UI path failed: {e}; trying 'open -a' fallback")
                    # 2) Фоллбэк: open -a (может открыть в новом окне). После открытия — разворачиваем.
                    try:
                        rc = subprocess.run(["open", "-a", "Windsurf", dest], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        if rc.returncode == 0:
                            time.sleep(0.8)
                            try:
                                self._ensure_windsurf_frontmost_mac(target or "active")
                            except Exception:
                                pass
                            pyautogui.hotkey('command', 'control', 'f')
                            # Подождём, чтобы UI устаканился, прежде чем проверять пиксель
                            logger.info("change_project (fallback): жду 3s перед финальной проверкой пикселя...")
                            time.sleep(3.0)
                            # Финальное действие: кликнуть в (1205,15), НО пропустить,
                            # если цвет равен 127,126,122 или 51,51,51 (по direct или screencapture)
                            try:
                                try:
                                    sw, sh = pyautogui.size()
                                except Exception:
                                    sw = sh = 0
                                # Точка финальной проверки (ENV override), по умолчанию 1205,15
                                try:
                                    tx = int(os.getenv("CHANGE_FINAL_PROBE_X", "1205").strip())
                                except Exception:
                                    tx = 1205
                                try:
                                    ty = int(os.getenv("CHANGE_FINAL_PROBE_Y", "15").strip())
                                except Exception:
                                    ty = 15
                                if sw and sh:
                                    tx = max(0, min(sw - 1, tx))
                                    ty = max(0, min(sh - 1, ty))
                                # Наведём курсор к точке финальной проверки и дадим время 1.5s
                                try:
                                    logger.info("change_project(fallback): навожу курсор на точку финальной проверки (%d,%d) и жду 1.5s", tx, ty)
                                    pyautogui.moveTo(tx, ty, duration=0.05)
                                except Exception:
                                    pass
                                time.sleep(1.5)
                                r1, g1, b1 = _rgb_at(tx, ty)
                                r2, g2, b2 = _avg_rgb_via_screencapture(tx, ty, 1)
                                forbid1 = (int(r1) == 127 and int(g1) == 126 and int(b1) == 122) or (int(r1) == 51 and int(g1) == 51 and int(b1) == 51)
                                forbid2 = (int(r2) == 127 and int(g2) == 126 and int(b2) == 122) or (int(r2) == 51 and int(g2) == 51 and int(b2) == 51)
                                logger.info(
                                    "change_project final probe @(1205,15)->@(%d,%d): direct=(%d,%d,%d) cap=(%d,%d,%d) forbid_direct=%s forbid_cap=%s",
                                    tx, ty, int(r1), int(g1), int(b1), int(r2), int(g2), int(b2), forbid1, forbid2,
                                )
                                if not (forbid1 or forbid2):
                                    pyautogui.moveTo(tx, ty, duration=0.05)
                                    pyautogui.click()
                                    logger.info("change_project: финальный клик по (%d,%d)", tx, ty)
                                else:
                                    logger.info("change_project: финальный клик пропущен из-за запрещённого цвета")
                            except Exception as _e:
                                logger.warning(f"change_project final click check failed: {_e}")
                            return True, f"Открыт проект через fallback и развернут: {dest}"
                    except Exception as e2:
                        return False, f"Не удалось открыть (fallback): {e2}"
            else:
                return False, "Смена проекта поддерживается только на macOS"
        except Exception as e:
            self.telemetry.last_error = f"change_project failed: {e}"
            return False, f"Ошибка change: {e}"


desktop_controller = DesktopController()
