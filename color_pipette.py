#!/usr/bin/env python3
import os
import sys
import time
import argparse
import tkinter as tk
from tkinter import ttk

import pyautogui
from PIL import Image, ImageTk, ImageDraw

# Optional: try to get front window bounds for window-relative percentages
try:
    from windsurf_controller import MacWindowManager  # type: ignore
except Exception:
    MacWindowManager = None  # type: ignore


def rgb_at(x: int, y_top: int):
    """Robust RGB sampling at top-origin coordinates using pyautogui.
    Falls back to a 1x1 screenshot if pixel() is unavailable.
    """
    try:
        r, g, b = pyautogui.pixel(x, y_top)
        return int(r), int(g), int(b)
    except Exception:
        try:
            img = pyautogui.screenshot(region=(x, y_top, 1, 1))
            r, g, b = img.getpixel((0, 0))
            return int(r), int(g), int(b)
        except Exception:
            return None


def hex_of(rgb):
    if not isinstance(rgb, tuple) or len(rgb) != 3:
        return "#000000"
    r, g, b = rgb
    return f"#{r:02X}{g:02X}{b:02X}"


class PipetteApp:
    def __init__(self, rate_hz: float = 30.0, save_dir: str = "debug", follow: bool = False, avg_k: int = 3):
        self.rate_hz = max(1.0, float(rate_hz))
        self.period_ms = int(1000.0 / self.rate_hz)
        self.save_dir = save_dir
        self.follow = follow
        # averaging kernel size (odd), clamp to 1..9
        try:
            avg_k = int(avg_k)
        except Exception:
            avg_k = 3
        if avg_k % 2 == 0:
            avg_k += 1
        self.avg_k = max(1, min(9, avg_k))

        self.root = tk.Tk()
        self.root.title("Color Pipette")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)

        # UI elements
        self.info_var = tk.StringVar()
        self.info_label = ttk.Label(self.root, textvariable=self.info_var, font=("Menlo", 10))
        self.info_label.grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))

        # Color patch (smaller size so it doesn't obstruct the target)
        self.color_patch = tk.Canvas(self.root, width=32, height=32, highlightthickness=1, highlightbackground="#888")
        self.color_patch.grid(row=0, column=1, rowspan=2, padx=8, pady=8)

        # Magnifier label
        # Magnifier label (will host a smaller preview image)
        self.mag_label = ttk.Label(self.root)
        self.mag_label.grid(row=1, column=0, sticky="w", padx=8, pady=(0, 8))
        self.mag_img = None  # keep reference

        # Help
        help_text = (
            "Space: pause/resume  |  Alt/Option: hold to freeze  |  F: follow on/off  |  S: save  |  C: copy .env  |  E: echo .env  |  Q: quit"
        )
        self.help_label = ttk.Label(self.root, text=help_text, foreground="#666")
        self.help_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 8))

        # State
        self.paused = False
        self.frozen_alt = False
        self.last_pos = (0, 0)
        self.screen_w, self.screen_h = pyautogui.size()

        # Window manager (optional)
        self.mac_mgr = None
        if MacWindowManager is not None:
            try:
                self.mac_mgr = MacWindowManager()
            except Exception:
                self.mac_mgr = None

        # Key bindings
        self.root.bind("<space>", self.on_toggle_pause)
        self.root.bind("s", self.on_save)
        self.root.bind("S", self.on_save)
        self.root.bind("c", self.on_copy_env)
        self.root.bind("C", self.on_copy_env)
        self.root.bind("e", self.on_echo_env)
        self.root.bind("E", self.on_echo_env)
        self.root.bind("q", self.on_quit)
        self.root.bind("Q", self.on_quit)
        # Toggle follow
        self.root.bind("f", self.on_toggle_follow)
        self.root.bind("F", self.on_toggle_follow)
        # Hold-to-freeze with Alt/Option (bind several variants for mac/win/x11)
        for seq in ("<Alt_L>", "<Alt_R>", "<Option_L>", "<Option_R>"):
            try:
                self.root.bind(seq, self.on_alt_down)
                self.root.bind(f"<KeyRelease-{seq.strip('<>')}>", self.on_alt_up)
            except Exception:
                pass

        # Initial fixed position: place near top-left corner by default (can be moved by dragging title bar)
        try:
            # Compute a compact default width/height based on widgets
            self.root.update_idletasks()
            w = max(220, self.root.winfo_width())
            h = max(180, self.root.winfo_height())
            gx, gy = 40, 40
            self.root.geometry(f"{w}x{h}+{gx}+{gy}")
        except Exception:
            pass

        # Start loop
        self.root.after(self.period_ms, self.tick)

    def geometry_follow(self, x: int, y: int):
        if not self.follow:
            return
        # Place window near cursor with offset, keep inside screen bounds
        off_x, off_y = 24, 24
        geo = self.root.geometry()
        self.root.update_idletasks()
        w = self.root.winfo_width() or 240
        h = self.root.winfo_height() or 240
        gx = x + off_x
        gy = y + off_y
        if gx + w > self.screen_w:
            gx = max(0, self.screen_w - w - 2)
        if gy + h > self.screen_h:
            gy = max(0, self.screen_h - h - 2)
        self.root.geometry(f"{w}x{h}+{gx}+{gy}")

    def get_window_pct(self, x: int, y: int):
        if not self.mac_mgr:
            return None
        try:
            b = self.mac_mgr.get_front_window_bounds()
            if not b:
                return None
            wx, wy, ww, wh = b
            if ww <= 0 or wh <= 0:
                return None
            px = (x - wx) / float(ww)
            py = (y - wy) / float(wh)
            return max(0.0, min(1.0, px)), max(0.0, min(1.0, py))
        except Exception:
            return None

    def tick(self):
        try:
            if not (self.paused or self.frozen_alt):
                pos = pyautogui.position()
                x, y = int(pos.x), int(pos.y)
                self.last_pos = (x, y)
                rgb = self.avg_rgb(x, y)
                hexv = hex_of(rgb) if rgb else "#000000"
                y_bot = self.screen_h - 1 - y
                wp = self.get_window_pct(x, y)
                wp_txt = f" window=({wp[0]:.4f},{wp[1]:.4f})" if wp else ""
                status = []
                if self.paused:
                    status.append("PAUSED")
                if self.frozen_alt:
                    status.append("FROZEN")
                status.append(f"FOLLOW={'on' if self.follow else 'off'}")
                status.append(f"AVG={self.avg_k}x{self.avg_k}")
                stxt = " ".join(f"[{s}]" for s in status)
                self.info_var.set(
                    f"x={x} y_top={y} y_bot={y_bot}  rgb={rgb}  {hexv}{wp_txt}  {stxt}"
                )

                # Update color patch
                if rgb:
                    self.color_patch.configure(bg=hexv)
                else:
                    self.color_patch.configure(bg="#000000")

                # Magnifier: 16x16 region -> 120x120 zoom with crosshair (smaller UI)
                try:
                    cw = ch = 16
                    rx = max(0, min(self.screen_w - cw, x - cw // 2))
                    ry = max(0, min(self.screen_h - ch, y - ch // 2))
                    img = pyautogui.screenshot(region=(rx, ry, cw, ch))
                    img = img.resize((120, 120), resample=Image.NEAREST)
                    d = ImageDraw.Draw(img)
                    cx = cy = 60
                    d.line([(cx - 8, cy), (cx + 8, cy)], fill=(255, 0, 0), width=2)
                    d.line([(cx, cy - 8), (cx, cy + 8)], fill=(255, 0, 0), width=2)
                    self.mag_img = ImageTk.PhotoImage(img)
                    self.mag_label.configure(image=self.mag_img)
                except Exception:
                    pass

                # Move window near cursor
                self.geometry_follow(x, y)
        except Exception:
            pass
        finally:
            self.root.after(self.period_ms, self.tick)

    def avg_rgb(self, x: int, y: int):
        # Average over kxk region centered at (x,y)
        if self.avg_k <= 1:
            return rgb_at(x, y)
        k = self.avg_k
        r = k // 2
        # Clamp region within screen
        rx = max(0, min(self.screen_w - k, x - r))
        ry = max(0, min(self.screen_h - k, y - r))
        try:
            img = pyautogui.screenshot(region=(rx, ry, k, k))
            acc = [0, 0, 0]
            for iy in range(k):
                for ix in range(k):
                    pr, pg, pb = img.getpixel((ix, iy))
                    acc[0] += int(pr)
                    acc[1] += int(pg)
                    acc[2] += int(pb)
            n = k * k
            return (acc[0] // n, acc[1] // n, acc[2] // n)
        except Exception:
            return rgb_at(x, y)

    def _save_images(self, x: int, y: int, rgb):
        os.makedirs(self.save_dir, exist_ok=True)
        ts = int(time.time())
        # Crop around point
        cw, ch = 180, 140
        rx = max(0, min(self.screen_w - cw, int(x - cw / 2)))
        ry = max(0, min(self.screen_h - ch, int(y - ch / 2)))
        crop = pyautogui.screenshot(region=(rx, ry, cw, ch))
        # Compute scale factor in case of Retina (crop image size may differ from requested cw,ch)
        scale_cx = crop.width / float(cw) if cw > 0 else 1.0
        scale_cy = crop.height / float(ch) if ch > 0 else 1.0
        # Pixel position of (x,y) inside the crop image
        px = int((x - rx) * scale_cx)
        py = int((y - ry) * scale_cy)
        # Clamp inside image
        px = max(0, min(crop.width - 1, px))
        py = max(0, min(crop.height - 1, py))
        d = ImageDraw.Draw(crop)
        d.line([(px - 8, py), (px + 8, py)], fill=(0, 255, 0), width=2)
        d.line([(px, py - 8), (px, py + 8)], fill=(0, 255, 0), width=2)
        crop_path = os.path.join(self.save_dir, f"pipette_crop_{ts}_{rx}x{ry}_{cw}x{ch}.png")
        crop.save(crop_path)

        # Fullscreen with cross (hide window to avoid overlay in capture)
        try:
            self.root.withdraw()
            time.sleep(0.05)
            fs = pyautogui.screenshot()
        finally:
            try:
                self.root.deiconify()
            except Exception:
                pass
        # Account for potential Retina scale on full screenshot
        scale_fx = fs.width / float(self.screen_w) if self.screen_w > 0 else 1.0
        scale_fy = fs.height / float(self.screen_h) if self.screen_h > 0 else 1.0
        fx = int(x * scale_fx)
        fy = int(y * scale_fy)
        # Clamp inside image
        fx = max(0, min(fs.width - 1, fx))
        fy = max(0, min(fs.height - 1, fy))
        d2 = ImageDraw.Draw(fs)
        d2.line([(fx - 12, fy), (fx + 12, fy)], fill=(0, 255, 0), width=3)
        d2.line([(fx, fy - 12), (fx, fy + 12)], fill=(0, 255, 0), width=3)
        max_w = 1600
        if fs.width > max_w:
            ratio = max_w / fs.width
            fs = fs.resize((max_w, int(fs.height * ratio)))
        full_path = os.path.join(self.save_dir, f"pipette_full_{ts}_{x}x{y}_{hex_of(rgb)[1:]}.png")
        fs.save(full_path)
        return crop_path, full_path

    def on_toggle_pause(self, event=None):
        self.paused = not self.paused

    def on_save(self, event=None):
        # Use real-time cursor position to avoid race with tick updates
        try:
            pos = pyautogui.position()
            x, y = int(pos.x), int(pos.y)
        except Exception:
            x, y = self.last_pos
        rgb = self.avg_rgb(x, y)
        cp, fp = self._save_images(x, y, rgb or (0, 0, 0))
        env_block = self._env_lines(x, y, rgb)
        msg = f"Saved: {cp}\nSaved: {fp}\n\n{env_block}\n"
        # Console output
        print(msg)
        sys.stdout.flush()
        # Clipboard
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(msg)
        except Exception:
            pass

    def _env_lines(self, x: int, y: int, rgb):
        r, g, b = (rgb or (0, 0, 0))
        return (
            f"READY_PIXEL_X={x}\n"
            f"READY_PIXEL_Y={y}\n"
            f"READY_PIXEL_R={r}\n"
            f"READY_PIXEL_G={g}\n"
            f"READY_PIXEL_B={b}"
        )

    def on_copy_env(self, event=None):
        x, y = self.last_pos
        rgb = self.avg_rgb(x, y)
        lines = self._env_lines(x, y, rgb)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(lines)
        except Exception:
            pass
        print("Copied to clipboard:\n" + lines)
        sys.stdout.flush()

    def on_echo_env(self, event=None):
        x, y = self.last_pos
        rgb = self.avg_rgb(x, y)
        lines = self._env_lines(x, y, rgb)
        print(lines)
        sys.stdout.flush()

    def on_quit(self, event=None):
        self.root.quit()

    def on_toggle_follow(self, event=None):
        self.follow = not self.follow

    def on_alt_down(self, event=None):
        self.frozen_alt = True

    def on_alt_up(self, event=None):
        self.frozen_alt = False

    def run(self):
        print("Color Pipette running. Move the mouse. Hotkeys: Space pause/resume, S save, C copy .env, E echo .env, Q quit.")
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass


def main():
    ap = argparse.ArgumentParser(description="Live color pipette with overlay and magnifier")
    ap.add_argument("--rate", type=float, default=30.0, help="Refresh rate in Hz (default 30)")
    ap.add_argument("--save-dir", type=str, default=os.getenv("SAVE_VISUAL_DIR", "debug"), help="Directory to save images")
    ap.add_argument("--follow", action="store_true", help="Enable window to follow the cursor (default: off)")
    ap.add_argument("--avg", type=int, default=3, help="Averaging kernel size (odd, 1/3/5/7/9). Default 3")
    args = ap.parse_args()

    app = PipetteApp(rate_hz=args.rate, save_dir=args.save_dir, follow=args.follow, avg_k=args.avg)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
