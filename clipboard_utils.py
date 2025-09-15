import platform
import subprocess
import time
import logging
from typing import Optional

import pyperclip

try:
    if platform.system() == "Windows":
        import win32clipboard
        import win32con
        WIN32CLIPBOARD_AVAILABLE = True
    else:
        WIN32CLIPBOARD_AVAILABLE = False
except Exception:
    WIN32CLIPBOARD_AVAILABLE = False

logger = logging.getLogger(__name__)


def copy_to_clipboard(text: str) -> bool:
    try:
        if WIN32CLIPBOARD_AVAILABLE:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(str(text), win32con.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            logger.info("Текст скопирован через win32clipboard")
            return True
        else:
            try:
                pyperclip.copy(str(text))
                logger.info("Текст скопирован через pyperclip")
                return True
            except Exception as e:
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
        return False


def paste_from_clipboard_mac(expected_text: str, paste_retry_count: int = 2) -> bool:
    """Вставка и верификация на macOS с ретраями.
    На повторных попытках: выделяем всё и удаляем, затем вставляем заново.
    Предполагается, что клавиатурные действия выполняются снаружи.
    """
    import pyautogui

    import os
    detailed_log = False
    try:
        detailed_log = (os.getenv("DETAILED_AUTOMATION_LOG", "0").lower() not in ("0", "false", "no"))
    except Exception:
        detailed_log = False

    pasted_ok = False
    expected = str(expected_text).strip()
    for attempt in range(paste_retry_count + 1):
        try:
            # Optional re-focus before each attempt to ensure input field is active
            try:
                refocus_enabled = (os.getenv("CLICK_BEFORE_PASTE", "1").lower() not in ("0", "false", "no"))
            except Exception:
                refocus_enabled = True
            if refocus_enabled:
                try:
                    ix = os.getenv("INPUT_ABS_X")
                    iy = os.getenv("INPUT_ABS_Y")
                    ax = os.getenv("ANSWER_ABS_X")
                    ay = os.getenv("ANSWER_ABS_Y")
                    cx = cy = None
                    if ix is not None and iy is not None:
                        cx = int(str(ix).strip())
                        cy = int(str(iy).strip())
                    if (cx is None or cy is None) and ax is not None and ay is not None:
                        cx = int(str(ax).strip())
                        cy = int(str(ay).strip())
                    if cx is not None and cy is not None and cx >= 0 and cy >= 0:
                        try:
                            sw, sh = pyautogui.size()
                        except Exception:
                            sw = sh = None
                        if isinstance(sw, int) and isinstance(sh, int) and sw > 0 and sh > 0:
                            cx = max(0, min(sw - 1, int(cx)))
                            cy = max(0, min(sh - 1, int(cy)))
                        if detailed_log:
                            logger.info(f"[Paste] attempt {attempt}: refocus click at ({cx},{cy})")
                        pyautogui.click(cx, cy)
                        time.sleep(0.2)
                except Exception as _e:
                    if detailed_log:
                        logger.info(f"[Paste] attempt {attempt}: refocus skipped due to error: {_e}")

            if attempt > 0:
                logger.warning("Повтор вставки: очищаю поле (Cmd+A, Backspace) и пробую снова")
                pyautogui.hotkey('command', 'a')
                time.sleep(0.1)
                pyautogui.press('backspace')
                time.sleep(0.15)

            pyautogui.hotkey('command', 'v')
            time.sleep(0.5)
            # Проверяем вставку (Cmd+A, Cmd+C)
            if detailed_log:
                logger.info(f"[Paste] attempt {attempt}: select-all and copy to verify")
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
            if detailed_log:
                logger.info(f"[Paste] attempt {attempt}: got_len={len(got)} expected_len={len(expected)} eq={got==expected}")
                if len(got) > 3 * max(1, len(expected)) and not (got == expected):
                    logger.info("[Paste] hint: получен очень длинный текст — вероятно, фокус не в поле ввода (выделилась панель ответа)")
            if got == expected:
                pasted_ok = True
                break
        except Exception as e:
            logger.debug(f"mac paste attempt {attempt} failed: {e}")
            time.sleep(0.3)
    return pasted_ok
