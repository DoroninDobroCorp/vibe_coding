"""Утилиты для работы с пикселями и цветами на экране."""

import subprocess
import tempfile
import os
from typing import Tuple
import pyautogui
from PIL import Image


def _sanitize_k(k: int) -> int:
    """Нормализует размер окна усреднения (должен быть нечётным >= 1)."""
    try:
        k = int(k)
    except Exception:
        k = 1
    if k < 1:
        k = 1
    if k % 2 == 0:
        k += 1
    return k


def rgb_at(x: int, y: int) -> Tuple[int, int, int]:
    """Читает цвет пикселя в координатах экрана (top-origin)."""
    try:
        r, g, b = pyautogui.pixel(int(x), int(y))
        return int(r), int(g), int(b)
    except Exception:
        # Fallback через screenshot если pyautogui.pixel недоступен
        try:
            img = pyautogui.screenshot(region=(int(x), int(y), 1, 1))
            r, g, b = img.getpixel((0, 0))
            return int(r), int(g), int(b)
        except Exception:
            return 0, 0, 0


def avg_rgb(x: int, y: int, k: int) -> Tuple[int, int, int]:
    """Усреднение цвета по kxk пикселей вокруг (x,y) через прямые вызовы pixel()."""
    k = _sanitize_k(k)
    if k == 1:
        return rgb_at(x, y)
    
    r = k // 2
    acc = [0, 0, 0]
    cnt = 0
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            try:
                px, py, pz = rgb_at(x + dx, y + dy)
                acc[0] += px
                acc[1] += py
                acc[2] += pz
                cnt += 1
            except Exception:
                pass
    
    if cnt == 0:
        return rgb_at(x, y)
    return acc[0] // cnt, acc[1] // cnt, acc[2] // cnt


def avg_rgb_via_screencapture(x: int, y: int, k: int) -> Tuple[int, int, int]:
    """Усреднение по kxk с использованием 'screencapture -R' (устойчиво на retina)."""
    k = _sanitize_k(k)
    r = k // 2
    rx, ry, rw, rh = x - r, y - r, k, k
    
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            tmp_path = tf.name
        
        subprocess.run(
            ["screencapture", "-R", f"{rx},{ry},{rw},{rh}", tmp_path],
            check=False,
            timeout=1.0,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        if not os.path.exists(tmp_path):
            return rgb_at(x, y)
        
        img = Image.open(tmp_path)
        os.remove(tmp_path)
        
        w, h = img.size
        if w == 0 or h == 0:
            return rgb_at(x, y)
        
        pixels = list(img.getdata())
        acc_r = acc_g = acc_b = cnt = 0
        for pix in pixels:
            if len(pix) >= 3:
                acc_r += pix[0]
                acc_g += pix[1]
                acc_b += pix[2]
                cnt += 1
        
        if cnt == 0:
            return rgb_at(x, y)
        return acc_r // cnt, acc_g // cnt, acc_b // cnt
    except Exception:
        try:
            if 'tmp_path' in locals() and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return rgb_at(x, y)


def sample_rgb_consistent(x: int, y: int, avg_k: int) -> Tuple[int, int, int]:
    """Сэмплирование цвета согласованно с color_pipette: через screencapture с усреднением."""
    try:
        return avg_rgb_via_screencapture(x, y, avg_k)
    except Exception:
        try:
            return avg_rgb(x, y, avg_k)
        except Exception:
            return rgb_at(x, y)


def map_ready_pixel_xy(
    rp_x: int, 
    rp_y: int, 
    rp_mode: str = "top", 
    rp_dx: int = 0, 
    rp_dy: int = 0
) -> Tuple[int, int]:
    """
    Маппинг координат опорного пикселя в экранные координаты согласно режиму.
    
    Режимы:
    - 'top': координаты от верхнего левого угла экрана (по умолчанию)
    - 'bottom': координаты от нижнего левого угла экрана
    """
    x2, y2 = rp_x, rp_y
    rp_mode = (rp_mode or "top").strip().lower()
    
    if rp_mode == "bottom":
        try:
            sw, sh = pyautogui.size()
            y2 = int(sh) - int(rp_y)
        except Exception:
            pass
    
    # Применяем сдвиги
    x2 += rp_dx
    y2 += rp_dy
    
    return x2, y2


def pick_ready_src(default: str = 'cap') -> str:
    """Выбирает источник измерения READY_PIXEL: 'cap', 'dir' или 'auto'."""
    from core.config import config
    s = (config.READY_PIXEL_SRC or default).strip().lower()
    if s not in ('auto', 'cap', 'dir'):
        s = default
    return s


def measure_ready_pixel_rgb(
    x: int, 
    y: int, 
    avg_k: int, 
    target: Tuple[int, int, int] | None = None
) -> Tuple[Tuple[int, int, int], str]:
    """
    Измерить RGB в точке (x,y) для READY_PIXEL в соответствии с READY_PIXEL_SRC.
    
    Возвращает ((r,g,b), used_src).
    При 'auto' выбирается источник с меньшей дельтой до target.
    """
    src = pick_ready_src('cap')
    
    if src == 'auto' and target:
        rgb_cap = avg_rgb_via_screencapture(x, y, avg_k)
        rgb_dir = avg_rgb(x, y, avg_k)
        
        def delta(a: Tuple[int, int, int], b: Tuple[int, int, int]) -> int:
            return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])
        
        d_cap = delta(rgb_cap, target)
        d_dir = delta(rgb_dir, target)
        
        if d_cap <= d_dir:
            return rgb_cap, 'cap'
        else:
            return rgb_dir, 'dir'
    elif src == 'dir':
        return avg_rgb(x, y, avg_k), 'dir'
    else:  # 'cap'
        return avg_rgb_via_screencapture(x, y, avg_k), 'cap'
