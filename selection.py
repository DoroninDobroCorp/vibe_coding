import os
import time
import logging
from typing import Tuple

import pyautogui
import pyperclip

# Этот модуль намеренно читает параметры из os.getenv, чтобы не создавать циклических импортов.


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default


logger = logging.getLogger(__name__)


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

    # Якорь: только ANSWER_ABS_X/Y; если не заданы — используем точку в правом нижнем секторе панели
    try:
        ax = int(os.getenv("ANSWER_ABS_X", "-1"))
        ay = int(os.getenv("ANSWER_ABS_Y", "-1"))
    except Exception:
        ax = ay = -1
    if ax >= 0 and ay >= 0:
        start_x, start_y = ax, ay
    else:
        start_x = rx + max(12, int(rw * 0.9))
        start_y = ry + max(12, int(rh * 0.9))

    logger.info(
        f"copy_from_right_panel: region=(rx={rx},ry={ry},rw={rw},rh={rh}), anchor=({start_x},{start_y})"
    )

    # Вспомогательный клик перед копированием (если задан в .env)
    try:
        copy_click_x = _env_int("COPY_CLICK_X", 0)
        copy_click_y = _env_int("COPY_CLICK_Y", 0)
        if copy_click_x > 0 and copy_click_y > 0:
            logger.info(f"[Copy] Вспомогательный клик перед копированием в ({copy_click_x},{copy_click_y})")
            pyautogui.click(copy_click_x, copy_click_y)
            time.sleep(0.3)  # Даем время на реакцию UI
    except Exception as e:
        logger.debug(f"[Copy] Вспомогательный клик пропущен: {e}")
    
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
    
    # Копирование с логированием
    pyautogui.hotkey('command', 'c')
    time.sleep(0.3)  # Увеличена задержка для надежности
    text = (pyperclip.paste() or "").strip()
    logger.info(f"[Copy] Скопировано {len(text)} символов")
    return text, (rx, ry, rw, rh)
