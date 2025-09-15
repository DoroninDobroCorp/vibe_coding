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

    pasted_ok = False
    expected = str(expected_text).strip()
    for attempt in range(paste_retry_count + 1):
        try:
            if attempt > 0:
                logger.warning("Повтор вставки: очищаю поле (Cmd+A, Backspace) и пробую снова")
                pyautogui.hotkey('command', 'a')
                time.sleep(0.1)
                pyautogui.press('backspace')
                time.sleep(0.15)

            pyautogui.hotkey('command', 'v')
            time.sleep(0.5)
            # Проверяем вставку (Cmd+A, Cmd+C)
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
            if got == expected:
                pasted_ok = True
                break
        except Exception as e:
            logger.debug(f"mac paste attempt {attempt} failed: {e}")
            time.sleep(0.3)
    return pasted_ok
