import os
import time
from typing import Tuple

import pyautogui
import pyperclip

# Этот модуль намеренно читает параметры из os.getenv, чтобы не создавать циклических импортов.


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default


def copy_from_right_panel(bounds: Tuple[int, int, int, int]) -> Tuple[str, Tuple[int, int, int, int]]:
    """Копирует текст из правой панели ответа Windsurf с помощью протяжки и автоскролла.
    Возвращает (скопированный_текст, регион_анализа_rx_ry_rw_rh).
    """
    x, y, w, h = bounds
    VISUAL_REGION_TOP = _env_int("VISUAL_REGION_TOP", 100)
    VISUAL_REGION_BOTTOM = _env_int("VISUAL_REGION_BOTTOM", 150)
    right_third_x = x + max(0, int(w * 2 / 3))
    rx = max(0, right_third_x + 8)
    ry = max(0, y + max(0, VISUAL_REGION_TOP))
    rw = max(16, int(w / 3) - 16)
    rh = max(24, h - max(0, VISUAL_REGION_TOP) - max(0, VISUAL_REGION_BOTTOM))

    # Якорь: ANSWER_WINPCT или ANSWER_ABS_X/Y
    ans_px = ans_py = None
    ans_raw = (os.getenv("ANSWER_WINPCT", "") or "").strip()
    if ans_raw and "," in ans_raw:
        try:
            sx, sy = ans_raw.split(",", 1)
            ans_px = float(sx.strip())
            ans_py = float(sy.strip())
        except Exception:
            ans_px = ans_py = None
    if not (isinstance(ans_px, float) and isinstance(ans_py, float)):
        try:
            ax = int(os.getenv("ANSWER_ABS_X", "-1"))
            ay = int(os.getenv("ANSWER_ABS_Y", "-1"))
            if ax >= 0 and ay >= 0:
                start_x, start_y = ax, ay
            else:
                start_x = rx + max(12, int(rw * 0.66))
                start_y = ry + max(12, rh - 24)
        except Exception:
            start_x = rx + max(12, int(rw * 0.66))
            start_y = ry + max(12, rh - 24)
    else:
        px = max(0.0, min(1.0, ans_px))
        py = max(0.0, min(1.0, ans_py))
        start_x = int(x + px * w)
        start_y = int(y + py * h)

    # Протяжка и автоскролл
    pyautogui.moveTo(start_x, start_y)
    pyautogui.mouseDown(start_x, start_y)
    time.sleep(0.05)
    pyautogui.moveTo(rx + 12, ry + 12, duration=0.2)
    for _ in range(10):
        pyautogui.scroll(500)
        time.sleep(0.04)
    pyautogui.mouseUp(rx + 12, ry + 12)
    time.sleep(0.1)
    pyautogui.hotkey('command', 'c')
    time.sleep(0.2)
    text = (pyperclip.paste() or "").strip()
    return text, (rx, ry, rw, rh)
