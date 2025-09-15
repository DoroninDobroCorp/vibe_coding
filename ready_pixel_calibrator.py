#!/usr/bin/env python3
import os
import sys
import time
import argparse
from typing import Tuple

from dotenv import load_dotenv
import pyautogui
from PIL import ImageDraw

# Reuse the exact mapping logic from the main controller
from windsurf_controller import map_ready_pixel_xy, MacWindowManager


ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")


def update_env_file(updates: dict, env_path: str = ENV_PATH) -> str:
    """Обновляет/добавляет пары KEY=VALUE в .env, сохраняя остальные строки и комментарии.
    Возвращает путь файла."""
    # Читаем исходные строки, если файл есть
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

    # Индекс существующих ключей -> позиция в lines
    key_to_idx = {}
    for idx, line in enumerate(lines):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "=" in s:
            k, _ = s.split("=", 1)
            key_to_idx[k.strip()] = idx

    # Применяем обновления
    for k, v in updates.items():
        kv = f"{k}={v}"
        if k in key_to_idx:
            lines[key_to_idx[k]] = kv
        else:
            lines.append(kv)

    # Пишем назад
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")
    return env_path


def save_used_crops(sx: int, sy: int, out_dir: str, prefix: str, label: str = "probe") -> Tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    # Small crop around the used point with green cross
    cw, ch = 180, 140
    sw, sh = pyautogui.size()
    rx = max(0, min(sw - cw, int(sx - cw / 2)))
    ry = max(0, min(sh - ch, int(sy - ch / 2)))
    crop_path = os.path.join(out_dir, f"{prefix}_{label}_USED_{rx}x{ry}_{cw}x{ch}.png")
    img = pyautogui.screenshot(region=(rx, ry, cw, ch))
    d = ImageDraw.Draw(img)
    # Draw cross at the true relative position of (sx,sy) inside this crop
    relx, rely = sx - rx, sy - ry
    if 0 <= relx < cw and 0 <= rely < ch:
        d.line([(relx - 8, rely), (relx + 8, rely)], fill=(0,255,0), width=2)
        d.line([(relx, rely - 8), (relx, rely + 8)], fill=(0,255,0), width=2)
    else:
        # If off-crop due to clamping, draw a border indicator
        d.rectangle([(1,1),(cw-2,ch-2)], outline=(255,0,0), width=2)
    img.save(crop_path)

    # Fullscreen with green cross
    fs = pyautogui.screenshot()
    dfs = ImageDraw.Draw(fs)
    dfs.line([(sx - 12, sy), (sx + 12, sy)], fill=(0,255,0), width=3)
    dfs.line([(sx, sy - 12), (sx, sy + 12)], fill=(0,255,0), width=3)
    full_path = os.path.join(out_dir, f"{prefix}_{label}_USED_FULL_{sx}x{sy}.png")
    # Optionally downscale for easier viewing
    max_w = 1600
    if fs.width > max_w:
        ratio = max_w / fs.width
        fs = fs.resize((max_w, int(fs.height * ratio)))
    fs.save(full_path)
    return crop_path, full_path


def parse_kv_updates(s: str):
    items = [x.strip() for x in s.split() if x.strip()]
    updates = {}
    for it in items:
        if "=" in it:
            k, v = it.split("=", 1)
            updates[k.strip()] = v.strip()
    return updates


def main():
    load_dotenv()

    ap = argparse.ArgumentParser(description="Ready Pixel Calibrator (macOS)")
    ap.add_argument("--x", type=int, default=None, help="Logical X coordinate (env READY_PIXEL_X by default)")
    ap.add_argument("--y", type=int, default=None, help="Logical Y coordinate (env READY_PIXEL_Y by default)")
    ap.add_argument("--mode", type=str, default=None, choices=["top","flipy","top2x","flipy2x"], help="Coord mode (env READY_PIXEL_COORD_MODE)")
    ap.add_argument("--dx", type=int, default=None, help="Offset X (env READY_PIXEL_DX)")
    ap.add_argument("--dy", type=int, default=None, help="Offset Y (env READY_PIXEL_DY)")
    ap.add_argument("--dir", type=str, default=None, help="Output dir (env SAVE_VISUAL_DIR or debug)")
    ap.add_argument("--prefix", type=str, default="calibrator", help="Output filename prefix")
    ap.add_argument("--once", action="store_true", help="Make one snapshot and exit")
    ap.add_argument("--write", action="store_true", help="Write current values to .env immediately and exit")
    ap.add_argument("--pick", action="store_true", help="Pick a point by hovering the mouse and pressing Enter; updates X/Y to the cursor position")
    ap.add_argument("--winpct", type=str, default=None, help="Window-relative pct as 'x_pct,y_pct' (e.g., 0.95,0.90)")
    args = ap.parse_args()

    # Defaults from env
    rp_x = args.x if args.x is not None else int(os.getenv("READY_PIXEL_X", "-1"))
    rp_y = args.y if args.y is not None else int(os.getenv("READY_PIXEL_Y", "-1"))
    rp_mode = args.mode if args.mode is not None else os.getenv("READY_PIXEL_COORD_MODE", "top").strip().lower()
    rp_dx = args.dx if args.dx is not None else int(os.getenv("READY_PIXEL_DX", "0"))
    rp_dy = args.dy if args.dy is not None else int(os.getenv("READY_PIXEL_DY", "0"))
    out_dir = args.dir or os.getenv("SAVE_VISUAL_DIR", "debug")

    mac_mgr = MacWindowManager()

    def window_bounds():
        try:
            b = mac_mgr.get_front_window_bounds()
            if not b:
                print("Window bounds not available.")
                return None
            x, y, w, h = b
            print(f"Front window bounds: x={x} y={y} w={w} h={h}")
            return b
        except Exception as e:
            print(f"Failed to get window bounds: {e}")
            return None

    def window_percentages_for_point(sx: int, sy: int) -> tuple[float, float] | None:
        b = window_bounds()
        if not b:
            return None
        x, y, w, h = b
        if w <= 0 or h <= 0:
            return None
        px = (sx - x) / float(w)
        py = (sy - y) / float(h)
        return px, py

    def apply_winpct_arg():
        nonlocal rp_x, rp_y, rp_mode, rp_dx, rp_dy
        if not args.winpct:
            return False
        try:
            xs, ys = args.winpct.split(",", 1)
            px, py = float(xs.strip()), float(ys.strip())
        except Exception:
            print("Invalid --winpct format, expected 'x_pct,y_pct' e.g. 0.95,0.90")
            return False
        b = window_bounds()
        if not b:
            return False
        x, y, w, h = b
        rp_x = int(x + max(0.0, min(1.0, px)) * w)
        rp_y = int(y + max(0.0, min(1.0, py)) * h)
        rp_mode = "top"  # window -> absolute screen coords; no DPI mapping needed here
        rp_dx, rp_dy = 0, 0
        return True

    # If window-percent provided, compute absolute X/Y from window bounds
    apply_winpct_arg()

    def pick_once(label: str = "pick") -> tuple[int, int]:
        print("Pick mode: move the mouse to the desired point, then press Enter here...")
        try:
            input("")
        except EOFError:
            pass
        pos = pyautogui.position()
        sx, sy = int(pos.x), int(pos.y)
        # Save visual evidence
        save_used_crops(sx, sy, out_dir, args.prefix, label=label)
        sw, sh = pyautogui.size()
        wp = window_percentages_for_point(sx, sy)
        if wp:
            px, py = wp
            print(f"Picked screen ({sx},{sy}) on screen={sw}x{sh}; window pct ~ ({px:.4f},{py:.4f})")
        else:
            print(f"Picked screen ({sx},{sy}) on screen={sw}x{sh}")
        return sx, sy

    if args.pick:
        sx, sy = pick_once(label="pick")
        rp_x, rp_y = sx, sy
        rp_mode = "top"
        rp_dx, rp_dy = 0, 0
        if args.write:
            def write_env():
                updates = {
                    "READY_PIXEL_X": str(rp_x),
                    "READY_PIXEL_Y": str(rp_y),
                    "READY_PIXEL_COORD_MODE": rp_mode,
                    "READY_PIXEL_DX": str(rp_dx),
                    "READY_PIXEL_DY": str(rp_dy),
                }
                path = update_env_file(updates)
                print(f".env updated: {path}")
            write_env()
            return 0
    if rp_x < 0 or rp_y < 0:
        print("ERROR: Provide --x and --y or set READY_PIXEL_X/Y in .env, or use --winpct x_pct,y_pct or --pick")
        return 2

    def snapshot():
        sx, sy = map_ready_pixel_xy(rp_x, rp_y, rp_mode, rp_dx, rp_dy)
        crop_path, full_path = save_used_crops(sx, sy, out_dir, args.prefix, label="probe")
        sw, sh = pyautogui.size()
        oob = not (0 <= sx < sw and 0 <= sy < sh)
        warn = " [OUT-OF-SCREEN]" if oob else ""
        print(f"Mapped logical ({rp_x},{rp_y}) mode={rp_mode} dxdy=({rp_dx},{rp_dy}) -> screen used_xy=({sx},{sy}) screen={sw}x{sh}{warn}")
        print(f"Saved: {crop_path}\nSaved: {full_path}")

    def write_env():
        updates = {
            "READY_PIXEL_X": str(rp_x),
            "READY_PIXEL_Y": str(rp_y),
            "READY_PIXEL_COORD_MODE": rp_mode,
            "READY_PIXEL_DX": str(rp_dx),
            "READY_PIXEL_DY": str(rp_dy),
        }
        path = update_env_file(updates)
        print(f".env updated: {path}")

    snapshot()
    if args.write:
        write_env()
        return 0
    if args.once:
        return 0

    print("Enter new values in one of formats:")
    print("  x=<int> y=<int> mode=<top|flipy|top2x|flipy2x> dx=<int> dy=<int>")
    print("  or freeform: <x> <y> [mode] [dx] [dy]")
    print("  or window-relative: win <x_pct> <y_pct>   (e.g., win 0.95 0.90)")
    print("  or mouse pick: pick   (hover mouse at point and press Enter)")
    print("Commands: 'bounds' to show window bounds, 'write' to save to .env, 'q' to quit. Empty line = repeat snapshot.")

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye")
            break
        if not line:
            snapshot()
            continue
        if line.lower() in ("q", "quit", "exit"):
            print("Bye")
            break
        if line.lower() in ("w", "write"):
            write_env()
            continue
        if line.lower().startswith("bounds"):
            window_bounds()
            continue
        if line.lower().startswith("win"):
            parts = line.split()
            if len(parts) >= 3:
                try:
                    px, py = float(parts[1]), float(parts[2])
                except ValueError:
                    print("Usage: win <x_pct> <y_pct>")
                    continue
                b = window_bounds()
                if not b:
                    continue
                x, y, w, h = b
                rp_x = int(x + max(0.0, min(1.0, px)) * w)
                rp_y = int(y + max(0.0, min(1.0, py)) * h)
                rp_mode = "top"
                rp_dx, rp_dy = 0, 0
                snapshot()
                continue
        if line.lower().startswith("pick"):
            sx, sy = pick_once(label="pick")
            rp_x, rp_y = sx, sy
            rp_mode = "top"
            rp_dx, rp_dy = 0, 0
            snapshot()
            continue
        if "=" in line:
            updates = parse_kv_updates(line)
            if "x" in updates:
                rp_x = int(updates["x"])
            if "y" in updates:
                rp_y = int(updates["y"])
            if "mode" in updates:
                rp_mode = updates["mode"].strip().lower()
            if "dx" in updates:
                rp_dx = int(updates["dx"])
            if "dy" in updates:
                rp_dy = int(updates["dy"])
        else:
            # freeform: try to parse as: x y [mode] [dx] [dy]
            parts = line.split()
            ints = []
            others = []
            for p in parts:
                try:
                    ints.append(int(p))
                except ValueError:
                    others.append(p)
            if len(ints) >= 1:
                rp_x = ints[0]
            if len(ints) >= 2:
                rp_y = ints[1]
            if len(others) >= 1:
                cand = others[0].strip().lower()
                if cand in ("top","flipy","top2x","flipy2x"):
                    rp_mode = cand
            if len(ints) >= 3:
                rp_dx = ints[2]
            if len(ints) >= 4:
                rp_dy = ints[3]
        snapshot()

    return 0


if __name__ == "__main__":
    sys.exit(main())
