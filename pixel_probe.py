import sys
import time
import platform
import os

import pyautogui
from PIL import ImageDraw

try:
    # optional, for window-relative percentages
    from windsurf_controller import MacWindowManager  # type: ignore
except Exception:
    MacWindowManager = None  # type: ignore


def _rgb_at(x: int, y_top_origin: int):
    """Читает цвет пикселя, координаты относительно верхнего левого угла экрана."""
    try:
        r, g, b = pyautogui.pixel(x, y_top_origin)
        return int(r), int(g), int(b)
    except Exception:
        try:
            img = pyautogui.screenshot(region=(x, y_top_origin, 1, 1))
            r, g, b = img.getpixel((0, 0))
            return int(r), int(g), int(b)
        except Exception:
            return None


def _hex_of(rgb):
    if not isinstance(rgb, tuple) or len(rgb) != 3:
        return "#000000"
    r, g, b = rgb
    return f"#{r:02X}{g:02X}{b:02X}"


def _save_images(x: int, y_top: int, rgb, out_dir: str = None):
    out_dir = out_dir or os.getenv("SAVE_VISUAL_DIR", "debug")
    os.makedirs(out_dir, exist_ok=True)
    ts = int(time.time())
    sw, sh = pyautogui.size()
    # crop around point
    cw, ch = 180, 140
    rx = max(0, min(sw - cw, int(x - cw / 2)))
    ry = max(0, min(sh - ch, int(y_top - ch / 2)))
    try:
        crop = pyautogui.screenshot(region=(rx, ry, cw, ch))
        d = ImageDraw.Draw(crop)
        d.line([(cw // 2 - 8, ch // 2), (cw // 2 + 8, ch // 2)], fill=(0, 255, 0), width=2)
        d.line([(cw // 2, ch // 2 - 8), (cw // 2, ch // 2 + 8)], fill=(0, 255, 0), width=2)
        crop_path = os.path.join(out_dir, f"probe_crop_{ts}_{rx}x{ry}_{cw}x{ch}.png")
        crop.save(crop_path)
    except Exception:
        crop_path = ""
    # fullscreen with cross
    try:
        fs = pyautogui.screenshot()
        d2 = ImageDraw.Draw(fs)
        d2.line([(x - 12, y_top), (x + 12, y_top)], fill=(0, 255, 0), width=3)
        d2.line([(x, y_top - 12), (x, y_top + 12)], fill=(0, 255, 0), width=3)
        max_w = 1600
        if fs.width > max_w:
            ratio = max_w / fs.width
            fs = fs.resize((max_w, int(fs.height * ratio)))
        full_path = os.path.join(out_dir, f"probe_full_{ts}_{x}x{y_top}_{_hex_of(rgb)[1:]}.png")
        fs.save(full_path)
    except Exception:
        full_path = ""
    return crop_path, full_path


def main():
    if platform.system() == "Darwin":
        try:
            import Quartz
        except Exception as e:
            print("ERROR: PyObjC (Quartz) не установлен. Выполните: pip install pyobjc-core pyobjc")
            print(f"Import error: {e}")
            sys.exit(1)

        screen_w, screen_h = pyautogui.size()

        mac_mgr = None
        if MacWindowManager is not None:
            try:
                mac_mgr = MacWindowManager()
            except Exception:
                mac_mgr = None

        def _window_pct(x: int, y_top: int):
            if not mac_mgr:
                return None
            try:
                b = mac_mgr.get_front_window_bounds()
                if not b:
                    return None
                wx, wy, ww, wh = b
                if ww <= 0 or wh <= 0:
                    return None
                px = (x - wx) / float(ww)
                py = (y_top - wy) / float(wh)
                return max(0.0, min(1.0, px)), max(0.0, min(1.0, py))
            except Exception:
                return None

        def callback(proxy, type_, event, refcon):
            if type_ in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventRightMouseDown):
                loc = Quartz.CGEventGetLocation(event)
                x, y_bottom_origin = int(loc.x), int(loc.y)
                # Конвертируем в верхне-левую систему координат
                y_top_origin = max(0, min(screen_h - 1, screen_h - 1 - y_bottom_origin))
                rgb = _rgb_at(x, y_top_origin)
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                if rgb is not None:
                    hexv = _hex_of(rgb)
                    wp = _window_pct(x, y_top_origin)
                    wp_txt = f" window=({wp[0]:.4f},{wp[1]:.4f})" if wp else ""
                    y_bot = screen_h - 1 - y_top_origin
                    print(f"[{ts}] click at x={x}, y_top={y_top_origin}, y_bot={y_bot} | rgb={rgb} {hexv}{wp_txt}")
                    # save images for visual validation
                    try:
                        cp, fp = _save_images(x, y_top_origin, rgb)
                        if cp or fp:
                            print(("Saved: " + cp if cp else "") + ("\nSaved: " + fp if fp else ""))
                    except Exception:
                        pass
                    # print .env-ready snippet
                    try:
                        print(
                            "ENV snippet:\n"
                            f"READY_PIXEL_X={x}\n"
                            f"READY_PIXEL_Y={y_top_origin}\n"
                            f"READY_PIXEL_R={rgb[0]}\n"
                            f"READY_PIXEL_G={rgb[1]}\n"
                            f"READY_PIXEL_B={rgb[2]}\n"
                            f"READY_PIXEL_COORD_MODE=top\n"
                            f"# If using window pct: CLICK_WINPCT={wp[0]:.4f},{wp[1]:.4f}\n" if wp else ""
                        )
                    except Exception:
                        pass
                else:
                    print(f"[{ts}] click at x={x}, y={y_top_origin} | color rgb=unknown")
                sys.stdout.flush()
            return event

        mask = (
            Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseDown)
            | Quartz.CGEventMaskBit(Quartz.kCGEventRightMouseDown)
        )
        tap = Quartz.CGEventTapCreate(
            Quartz.kCGHIDEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            mask,
            callback,
            None,
        )
        if not tap:
            print(
                "ERROR: Не удалось создать Event Tap. Проверьте разрешения: System Settings → Privacy & Security → Accessibility, Screen Recording и Input Monitoring для Terminal/Python."
            )
            sys.exit(1)

        runLoopSource = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        Quartz.CFRunLoopAddSource(
            Quartz.CFRunLoopGetCurrent(), runLoopSource, Quartz.kCFRunLoopDefaultMode
        )
        Quartz.CGEventTapEnable(tap, True)
        print(
            "Pixel probe (macOS/Quartz) started. Click anywhere to print coordinates and RGB color. Press Ctrl+C to exit."
        )
        print("Если клики не видны: дайте разрешения в Privacy & Security → Accessibility, Screen Recording, Input Monitoring.")
        try:
            Quartz.CFRunLoopRun()
        except KeyboardInterrupt:
            print("\nExiting pixel probe.")
            sys.exit(0)
    else:
        print(
            "Pixel probe fallback: Ваша ОС не macOS. Для глобального хука используйте pynput или платформенные API. Нажмите Ctrl+C для выхода."
        )
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nExiting pixel probe.")


if __name__ == "__main__":
    main()
