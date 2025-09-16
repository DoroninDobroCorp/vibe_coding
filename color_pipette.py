#!/usr/bin/env python3
import os
import sys
import time
import argparse
import tkinter as tk
from tkinter import ttk

import pyautogui
from PIL import Image, ImageTk, ImageDraw
import subprocess

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
    def __init__(self, rate_hz: float = 30.0, save_dir: str = "debug", follow: bool = False, avg_k: int = 3,
                 info_backend: str = "capture", info_hz: float = 10.0, save_backend: str = "status",
                 auto_quit_seconds: float = 0.0):
        self.rate_hz = max(1.0, float(rate_hz))
        self.period_ms = int(1000.0 / self.rate_hz)
        self.save_dir = save_dir
        self.follow = follow
        # How we sample color for status: 'direct' (pyautogui.pixel) or 'capture' (native screencapture -R)
        self.info_backend = (info_backend or "capture").lower().strip()
        if self.info_backend not in ("capture", "direct"):
            self.info_backend = "capture"
        # How we sample color for saved .env: 'status' (same as status sampling),
        # 'crop' (from captured crop), 'capture' or 'direct'
        self.save_backend = (save_backend or "status").lower().strip()
        if self.save_backend not in ("crop", "capture", "direct", "status"):
            self.save_backend = "status"
        try:
            self.info_hz = float(info_hz)
        except Exception:
            self.info_hz = 10.0
        self.info_period_ms = max(50, int(1000.0 / max(1e-6, self.info_hz)))
        self._info_last_t = 0.0
        self._info_last_rgb = (0, 0, 0)
        self.auto_quit_seconds = float(auto_quit_seconds or 0.0)
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
            "Space: pause/resume  |  Alt/Option: hold to freeze  |  F: follow on/off  |  B: info backend  |  T: save backend  |  S: save  |  C: copy .env  |  E: echo .env  |  V: verify  |  Q: quit"
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
        # Verify and backend toggle
        self.root.bind("v", self.on_verify)
        self.root.bind("V", self.on_verify)
        self.root.bind("b", self.on_toggle_backend)
        self.root.bind("B", self.on_toggle_backend)
        # Toggle save backend
        self.root.bind("t", self.on_toggle_save_backend)
        self.root.bind("T", self.on_toggle_save_backend)
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

        # Optional auto-quit for CI/test runs
        aq = self.auto_quit_seconds
        if aq and aq > 0:
            try:
                self.root.after(int(aq * 1000), self.root.quit)
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
                now = time.time()
                if (now - self._info_last_t) * 1000.0 >= self.info_period_ms:
                    try:
                        rgb_measured = self.sample_rgb_consistent(x, y)
                    except Exception:
                        rgb_measured = self.avg_rgb(x, y)
                    self._info_last_rgb = rgb_measured
                    self._info_last_t = now
                rgb = self._info_last_rgb
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
                status.append(f"SRC={'cap' if self.info_backend=='capture' else 'dir'}")
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
        """Average over kxk region centered at (x,y) using direct pixel() calls.
        Avoid region screenshots to be robust on Retina. Does NOT hide the window.
        """
        try:
            k = int(self.avg_k)
        except Exception:
            k = 1
        if k <= 1:
            return rgb_at(x, y)
        if k > 9:
            k = 9
        if k % 2 == 0:
            k += 1
        r = k // 2
        acc = [0, 0, 0]
        cnt = 0
        try:
            sw, sh = self.screen_w, self.screen_h
        except Exception:
            sw = sh = 0
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                xi = x + dx
                yi = y + dy
                if sw and sh:
                    if xi < 0 or yi < 0 or xi >= sw or yi >= sh:
                        xi = max(0, min(sw - 1, xi))
                        yi = max(0, min(sh - 1, yi))
                try:
                    pr, pg, pb = pyautogui.pixel(int(xi), int(yi))
                    acc[0] += int(pr)
                    acc[1] += int(pg)
                    acc[2] += int(pb)
                    cnt += 1
                except Exception:
                    pass
        if cnt <= 0:
            return rgb_at(x, y)
        return (acc[0] // cnt, acc[1] // cnt, acc[2] // cnt)

    def avg_rgb_hidden(self, x: int, y: int):
        """Hide the pipette window briefly and sample avg RGB to avoid overlay contamination."""
        try:
            # Hide window to avoid capturing overlay colors
            self.root.withdraw()
            # tiny delay to let compositor update
            time.sleep(0.03)
        except Exception:
            pass
        try:
            return self.avg_rgb(x, y)
        finally:
            try:
                self.root.deiconify()
            except Exception:
                pass

    def avg_rgb_via_screencapture(self, x: int, y: int):
        """Average over kxk region centered at (x,y) using native 'screencapture -R'.
        Handles Retina by averaging all pixels of the resulting image (which may be scaled > k).
        """
        try:
            k = int(self.avg_k)
        except Exception:
            k = 1
        if k < 1:
            k = 1
        if k > 9:
            k = 9
        if k % 2 == 0:
            k += 1
        r = k // 2
        rx = int(x - r)
        ry = int(y - r)
        cw = int(k)
        ch = int(k)
        tmp_path = None
        img = None
        try:
            os.makedirs(self.save_dir, exist_ok=True)
            tmp_path = os.path.join(self.save_dir, f"_pipette_tmp_{int(time.time()*1000)}.png")
            cmd = ["screencapture", "-x", "-R", f"{rx},{ry},{cw},{ch}", tmp_path]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode == 0 and os.path.exists(tmp_path):
                try:
                    img = Image.open(tmp_path).convert('RGB')
                except Exception:
                    img = None
        except Exception:
            img = None
        finally:
            try:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
        if img is None:
            # Fallback to pyautogui.screenshot region
            try:
                img = pyautogui.screenshot(region=(rx, ry, cw, ch)).convert('RGB')
            except Exception:
                return rgb_at(x, y)
        # Average all pixels in the image (covers Retina scaling automatically)
        acc_r = acc_g = acc_b = 0
        cnt = 0
        try:
            for iy in range(img.height):
                for ix in range(img.width):
                    pr, pg, pb = img.getpixel((ix, iy))
                    acc_r += int(pr)
                    acc_g += int(pg)
                    acc_b += int(pb)
                    cnt += 1
        except Exception:
            return rgb_at(x, y)
        if cnt <= 0:
            return rgb_at(x, y)
        return (acc_r // cnt, acc_g // cnt, acc_b // cnt)

    def sample_rgb_consistent(self, x: int, y: int):
        """Sample RGB for status using the selected backend."""
        if self.info_backend == "direct":
            return self.avg_rgb(x, y)
        return self.avg_rgb_via_screencapture(x, y)

    def _capture_crop(self, x: int, y: int, cw: int = 180, ch: int = 140):
        """Capture a crop around (x,y) with window hidden. Returns (crop, rx, ry, px, py).
        px,py are pixel coordinates inside crop image corresponding to (x,y), with Retina scaling handled.
        """
        # Не ограничиваем рамку размерами primary-screen: на macOS с несколькими мониторами
        # глобальные координаты могут быть отрицательными или выходить за пределы primary.
        # Полагаемся на нативную обрезку внутри screenshot().
        rx = int(x - cw / 2)
        ry = int(y - ch / 2)
        try:
            self.root.withdraw()
            time.sleep(0.03)
        except Exception:
            pass
        crop = None
        # 1) Пытаемся через нативный screencapture (чаще корректно маппит мульти-мониторы/ретину)
        try:
            os.makedirs(self.save_dir, exist_ok=True)
            tmp_path = os.path.join(self.save_dir, f"_pipette_tmp_{int(time.time()*1000)}.png")
            cmd = ["screencapture", "-x", "-R", f"{rx},{ry},{cw},{ch}", tmp_path]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode == 0 and os.path.exists(tmp_path):
                try:
                    crop = Image.open(tmp_path).convert('RGB')
                except Exception:
                    crop = None
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
        except Exception:
            crop = None
        # 2) Фоллбэк — pyautogui
        if crop is None:
            try:
                crop = pyautogui.screenshot(region=(rx, ry, cw, ch))
            except Exception:
                crop = None
        # Восстановить окно
        try:
            self.root.deiconify()
        except Exception:
            pass
        if crop is None:
            # Последний фоллбэк — пустая картинка нужного размера
            crop = Image.new('RGB', (max(1, cw), max(1, ch)), (0, 0, 0))
        # Map logical to image pixels (handle Retina scale)
        scale_cx = crop.width / float(cw) if cw > 0 else 1.0
        scale_cy = crop.height / float(ch) if ch > 0 else 1.0
        px = int((x - rx) * scale_cx)
        py = int((y - ry) * scale_cy)
        px = max(0, min(crop.width - 1, px))
        py = max(0, min(crop.height - 1, py))
        return crop, rx, ry, px, py

    def _rgb_from_image(self, img: Image.Image, px: int, py: int, k: int) -> tuple[int, int, int]:
        """Read RGB from image at (px,py), optionally averaging in kxk neighborhood inside image coords."""
        try:
            k = int(k)
        except Exception:
            k = 1
        if k < 1:
            k = 1
        if k > 9:
            k = 9
        if k % 2 == 0:
            k += 1
        if k == 1:
            p = img.getpixel((px, py))
            if isinstance(p, tuple) and len(p) >= 3:
                return int(p[0]), int(p[1]), int(p[2])
            v = int(p[0] if isinstance(p, tuple) else p)
            return v, v, v
        r = k // 2
        acc = [0, 0, 0]
        cnt = 0
        for iy in range(py - r, py + r + 1):
            if iy < 0 or iy >= img.height:
                continue
            for ix in range(px - r, px + r + 1):
                if ix < 0 or ix >= img.width:
                    continue
                pp = img.getpixel((ix, iy))
                if isinstance(pp, tuple) and len(pp) >= 3:
                    rr, gg, bb = int(pp[0]), int(pp[1]), int(pp[2])
                else:
                    v = int(pp[0] if isinstance(pp, tuple) else pp)
                    rr = gg = bb = v
                acc[0] += rr; acc[1] += gg; acc[2] += bb
                cnt += 1
        if cnt <= 0:
            return 0, 0, 0
        return acc[0] // cnt, acc[1] // cnt, acc[2] // cnt

    def _save_images(self, x: int, y: int, rgb):
        """Backward-compatible: capture crop/full and draw cross. Color 'rgb' used in filename only.
        Note: on_save теперь сам измеряет rgb с того же crop, что сохраняется.
        """
        os.makedirs(self.save_dir, exist_ok=True)
        ts = int(time.time())
        cw, ch = 180, 140
        crop, rx, ry, px, py = self._capture_crop(x, y, cw, ch)
        d = ImageDraw.Draw(crop)
        d.line([(px - 8, py), (px + 8, py)], fill=(0, 255, 0), width=2)
        d.line([(px, py - 8), (px, py + 8)], fill=(0, 255, 0), width=2)
        crop_path = os.path.join(self.save_dir, f"pipette_crop_{ts}_{rx}x{ry}_{cw}x{ch}.png")
        crop.save(crop_path)

        # Fullscreen with cross
        try:
            self.root.withdraw()
            time.sleep(0.05)
            fs = pyautogui.screenshot()
        finally:
            try:
                self.root.deiconify()
            except Exception:
                pass
        scale_fx = fs.width / float(self.screen_w) if self.screen_w > 0 else 1.0
        scale_fy = fs.height / float(self.screen_h) if self.screen_h > 0 else 1.0
        fx = int(x * scale_fx)
        fy = int(y * scale_fy)
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
        # Используем именно last_pos (то, что видно на оверлее),
        # чтобы снимок и блок .env соответствовали визуальному крестику.
        x, y = self.last_pos
        # Capture crop once, measure RGB exactly at cross point in that crop, then save images with the same crop
        cw, ch = 180, 140
        crop, rx, ry, px, py = self._capture_crop(x, y, cw, ch)
        # Select source for saved RGB
        if self.save_backend == "status":
            # Re-sample now using the same backend as status to avoid staleness
            rgb = self.sample_rgb_consistent(x, y)
        elif self.save_backend == "capture":
            rgb = self.sample_rgb_consistent(x, y)
        elif self.save_backend == "direct":
            rgb = self.avg_rgb(x, y)
        else:
            rgb = self._rgb_from_image(crop, px, py, self.avg_k)
        # Additional diagnostics
        direct = rgb_at(x, y) or (0, 0, 0)
        try:
            tiny = pyautogui.screenshot(region=(x, y, 1, 1))
            tiny_rgb = tiny.getpixel((0, 0))
            tiny_rgb = (int(tiny_rgb[0]), int(tiny_rgb[1]), int(tiny_rgb[2])) if isinstance(tiny_rgb, tuple) else (int(tiny_rgb),) * 3
        except Exception:
            tiny_rgb = (0, 0, 0)
        # For diagnostics, ensure Status matches Used if save_backend=='status'
        if self.save_backend == "status":
            status_rgb = rgb
        else:
            status_rgb = self.sample_rgb_consistent(x, y)
        # Draw cross and annotations on crop
        d = ImageDraw.Draw(crop)
        d.line([(px - 8, py), (px + 8, py)], fill=(0, 255, 0), width=2)
        d.line([(px, py - 8), (px, py + 8)], fill=(0, 255, 0), width=2)
        try:
            txt = (
                f"XY=({x},{y}) px=({px},{py}) AVG={self.avg_k} STATUS_SRC={'cap' if self.info_backend=='capture' else 'dir'} SAVE_SRC={self.save_backend}\n"
                f"Used={rgb}  Status={status_rgb}  Direct={direct}  R1x1={tiny_rgb}"
            )
            # simple background box
            lines = txt.split("\n")
            w = max(len(s) for s in lines)
            d.rectangle([(4, 4), (4 + 8 + 7 * w, 44)], fill=(0, 0, 0, 160))
            d.text((8, 8), txt, fill=(255, 255, 255))
        except Exception:
            pass
        os.makedirs(self.save_dir, exist_ok=True)
        ts = int(time.time())
        crop_path = os.path.join(self.save_dir, f"pipette_crop_{ts}_{rx}x{ry}_{cw}x{ch}.png")
        crop.save(crop_path)
        # Fullscreen
        try:
            self.root.withdraw()
            time.sleep(0.05)
            fs = pyautogui.screenshot()
        finally:
            try:
                self.root.deiconify()
            except Exception:
                pass
        scale_fx = fs.width / float(self.screen_w) if self.screen_w > 0 else 1.0
        scale_fy = fs.height / float(self.screen_h) if self.screen_h > 0 else 1.0
        fx = int(x * scale_fx)
        fy = int(y * scale_fy)
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
        cp, fp = crop_path, full_path
        env_block = self._env_lines(x, y, rgb)
        msg = (
            f"Saved: {cp}\nSaved: {fp}\n"
            f"Diagnostics: Used={rgb} Status={status_rgb} Direct={direct} R1x1={tiny_rgb} AVG={self.avg_k} "
            f"STATUS_SRC={'cap' if self.info_backend=='capture' else 'dir'} SAVE_SRC={self.save_backend}\n\n"
            f"{env_block}\n"
        )
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
        # Choose source consistently with self.save_backend (same policy as on_save)
        rgb = None
        if self.save_backend == "status":
            rgb = self.sample_rgb_consistent(x, y)
        elif self.save_backend == "capture":
            rgb = self.sample_rgb_consistent(x, y)
        elif self.save_backend == "direct":
            rgb = self.avg_rgb(x, y)
        else:
            crop, rx, ry, px, py = self._capture_crop(x, y, 180, 140)
            rgb = self._rgb_from_image(crop, px, py, self.avg_k)
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
        # Choose source consistently with self.save_backend
        if self.save_backend in ("status", "capture"):
            rgb = self.sample_rgb_consistent(x, y)
        elif self.save_backend == "direct":
            rgb = self.avg_rgb(x, y)
        else:
            crop, rx, ry, px, py = self._capture_crop(x, y, 180, 140)
            rgb = self._rgb_from_image(crop, px, py, self.avg_k)
        lines = self._env_lines(x, y, rgb)
        print(lines)
        sys.stdout.flush()

    def on_verify(self, event=None):
        """Сверка измерений: сравнивает три способа в одной точке X,Y из last_pos.
        1) pyautogui.pixel(x,y) — прямое чтение
        2) crop.getpixel(px,py) — из скриншота зоны с ретина-скейлом
        3) screenshot(region=(x,y,1,1)) — 1x1 регион
        Сохраняет crop с крестом и подписями.
        """
        x, y = self.last_pos
        direct = rgb_at(x, y) or (0, 0, 0)
        # crop-based
        cw, ch = 180, 140
        crop, rx, ry, px, py = self._capture_crop(x, y, cw, ch)
        img_rgb = self._rgb_from_image(crop, px, py, 1)
        # 1x1 region
        try:
            tiny = pyautogui.screenshot(region=(x, y, 1, 1))
            tiny_rgb = tiny.getpixel((0, 0))
            tiny_rgb = (int(tiny_rgb[0]), int(tiny_rgb[1]), int(tiny_rgb[2])) if isinstance(tiny_rgb, tuple) else (int(tiny_rgb),) * 3
        except Exception:
            tiny_rgb = (0, 0, 0)
        # draw cross and annotate
        d = ImageDraw.Draw(crop)
        d.line([(px - 8, py), (px + 8, py)], fill=(0, 255, 0), width=2)
        d.line([(px, py - 8), (px, py + 8)], fill=(0, 255, 0), width=2)
        try:
            txt = f"XY=({x},{y}) px=({px},{py})\nDirect={direct}  Img={img_rgb}  R1x1={tiny_rgb}"
            d.rectangle([(4, 4), (4 + 8 + 7 * max(len(s) for s in txt.split('\n')), 36)], fill=(0, 0, 0, 160))
            d.text((8, 8), txt, fill=(255, 255, 255))
        except Exception:
            pass
        os.makedirs(self.save_dir, exist_ok=True)
        ts = int(time.time())
        out = os.path.join(self.save_dir, f"pipette_verify_{ts}_{x}x{y}.png")
        try:
            crop.save(out)
        except Exception:
            pass
        print(f"VERIFY: XY=({x},{y}) direct={direct} img={img_rgb} tiny={tiny_rgb} -> saved {out}")
        sys.stdout.flush()

    def on_quit(self, event=None):
        self.root.quit()

    def on_toggle_follow(self, event=None):
        self.follow = not self.follow

    def on_toggle_backend(self, event=None):
        try:
            self.info_backend = "direct" if self.info_backend == "capture" else "capture"
        except Exception:
            self.info_backend = "capture"
        # force immediate resample
        self._info_last_t = 0.0
        try:
            self.info_label.configure(foreground="#444")
        except Exception:
            pass

    def on_toggle_save_backend(self, event=None):
        order = ["crop", "capture", "direct", "status"]
        try:
            idx = order.index(self.save_backend)
        except Exception:
            idx = 0
        self.save_backend = order[(idx + 1) % len(order)]
        # no need to resample immediately; only affects next save

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
    ap.add_argument("--save-dir", type=str, default="debug", help="Directory to save images")
    ap.add_argument("--follow", action="store_true", help="Enable window to follow the cursor (default: off)")
    ap.add_argument("--avg", type=int, default=3, help="Averaging kernel size (odd, 1/3/5/7/9). Default 3")
    ap.add_argument("--info-backend", type=str, choices=["capture", "direct"], default="capture", help="Status sampling backend")
    ap.add_argument("--save-backend", type=str, choices=["crop", "capture", "direct", "status"], default="status", help="Saved RGB source")
    ap.add_argument("--info-hz", type=float, default=10.0, help="Status sampling frequency in Hz")
    ap.add_argument("--auto-quit", type=float, default=0.0, help="Auto-quit after N seconds (0=disabled)")
    args = ap.parse_args()

    app = PipetteApp(rate_hz=args.rate, save_dir=args.save_dir, follow=args.follow, avg_k=args.avg,
                     info_backend=args.info_backend, info_hz=args.info_hz, save_backend=args.save_backend,
                     auto_quit_seconds=args.auto_quit)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
