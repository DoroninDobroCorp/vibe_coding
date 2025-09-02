import asyncio
import os

import logger as logger
import pyautogui
import time
import logging

import pyperclip
from PIL import ImageGrab
from dotenv import load_dotenv
from pywinauto import Application
from pywinauto.keyboard import send_keys

# Добавляем альтернативный способ работы с буфером обмена
try:
    import win32clipboard
    import win32con
    WIN32CLIPBOARD_AVAILABLE = True
except ImportError:
    WIN32CLIPBOARD_AVAILABLE = False
    logger.warning("win32clipboard недоступен, используем pyperclip")

from config import config
from ocr import ocr_processor

load_dotenv()
logger = logging.getLogger(__name__)

WINDSURF_WINDOW_TITLE = os.getenv("WINDSURF_WINDOW_TITLE")


class DesktopController:
    def __init__(self):
        self.is_ready = False
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.3

    def copy_to_clipboard(self, text):
        """Надежное копирование текста в буфер обмена"""
        try:
            if WIN32CLIPBOARD_AVAILABLE:
                # Используем win32clipboard для большей надежности
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(str(text), win32con.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                logger.info("Текст скопирован через win32clipboard")
                return True
            else:
                # Fallback на pyperclip
                pyperclip.copy(str(text))
                logger.info("Текст скопирован через pyperclip")
                return True
        except Exception as e:
            logger.error(f"Ошибка при копировании в буфер: {e}")
            return False

    # def calibrate(self, area_type):
    #     """Режим калибровки - пользователь кликает в нужные области"""
    #     logger.info(f"Калибровка {area_type}. Кликните в нужную область...")
    #     time.sleep(3)
    #     x, y = pyautogui.position()
    #
    #     if area_type == "input_box":
    #         config.calibration_data["input_box"] = {"x": x, "y": y}
    #     elif area_type == "send_button":
    #         config.calibration_data["send_button"] = {"x": x, "y": y}
    #     elif area_type == "confirm_button":
    #         config.calibration_data["confirm_button"] = {"x": x, "y": y}
    #     elif area_type == "response_area":
    #         width, height = 600, 400
    #         config.calibration_data["response_area"] = {
    #             "x": x,
    #             "y": y,
    #             "width": width,
    #             "height": height,
    #         }
    #
    #     config.save_calibration()
    #     return True

    # def is_calibrated(self):
    #     return all(
    #         [
    #             # config.calibration_data["input_box"],  # Не нужно - используем Ctrl+L
    #             # config.calibration_data["send_button"],  # Не нужно - используем Enter
    #             config.calibration_data["response_area"],
    #         ]
    #     )
    #
    # def click_confirm_button(self):
    #     """Клик подтверждающей кнопки если она есть"""
    #     if config.calibration_data.get("confirm_button"):
    #         confirm = config.calibration_data["confirm_button"]
    #         pyautogui.click(confirm["x"], confirm["y"])
    #         time.sleep(1)
    #         return True
    #     return False

    def send_message_sync(self, message):
        """Синхронная версия отправки сообщения (вызывается в отдельном потоке)"""

        try:
            # Ищем окно Windsurf по имени процесса
            logger.info("Ищем окно Windsurf...")
            import psutil
            windsurf_pids = []

            for proc in psutil.process_iter(['pid', 'name']):
                if 'windsurf' in proc.info['name'].lower():
                    windsurf_pids.append(proc.info['pid'])

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
            time.sleep(3)

            # Поле ввода уже активно, просто печатаем
            logger.info(f"Печатаем сообщение напрямую: {message}")
            
            # Копируем строку в буфер
            if not self.copy_to_clipboard(str(message)):
                logger.error("Не удалось скопировать текст в буфер обмена")
                return False
            time.sleep(0.2)
            
            # Устанавливаем фокус на окно
            if main_window is not None:
                try:
                    main_window.set_focus()
                    time.sleep(0.5)  # Увеличиваем задержку для стабильности
                except Exception as e:
                    logger.warning(f"Не удалось установить фокус через main_window: {e}")
            
            # Дополнительная задержка для полной активации окна
            time.sleep(0.5)
            
            # Проверяем содержимое буфера обмена перед вставкой
            try:
                clipboard_content = pyperclip.paste()
                logger.info(f"Содержимое буфера обмена перед вставкой: '{clipboard_content[:50]}...'")
                if clipboard_content.strip() != str(message).strip():
                    logger.warning("⚠️ Содержимое буфера не соответствует сообщению, копируем заново")
                    if not self.copy_to_clipboard(str(message)):
                        logger.error("Не удалось перекопировать текст")
                        return False
                    time.sleep(0.2)
            except Exception as e:
                logger.warning(f"Не удалось проверить буфер обмена: {e}")
            
            # Пробуем несколько способов вставки для надежности
            logger.info("Пробуем вставить текст...")
            
            # Способ 1: Через pyautogui.hotkey (более надежно)
            try:
                pyautogui.hotkey('ctrl', 'v')
                logger.info("Вставка через pyautogui.hotkey успешна")
            except Exception as e:
                logger.warning(f"pyautogui.hotkey не сработал: {e}")
                
                # Способ 2: Через main_window.type_keys
                try:
                    if main_window is not None:
                        main_window.type_keys("^V", set_foreground=True, pause=0.1)
                        logger.info("Вставка через main_window.type_keys успешна")
                except Exception as e2:
                    logger.warning(f"main_window.type_keys не сработал: {e2}")
                    
                    # Способ 3: Резервный - печатаем по символам
                    logger.info("Пробуем печатать по символам...")
                    pyautogui.write(str(message), interval=0.01)
                    logger.info("Печать по символам завершена")

            time.sleep(1)
            
            # Проверяем, что текст действительно вставился
            logger.info("Проверяем результат вставки...")
            try:
                # Выделяем весь текст в поле ввода
                pyautogui.hotkey('ctrl', 'a')
                time.sleep(0.2)
                # Копируем выделенный текст
                pyautogui.hotkey('ctrl', 'c')
                time.sleep(0.2)
                # Проверяем что скопировалось
                pasted_text = pyperclip.paste()
                if pasted_text.strip() == str(message).strip():
                    logger.info("✅ Текст успешно вставлен и проверен")
                else:
                    logger.warning(f"⚠️ Текст вставился некорректно. Ожидалось: '{message}', получено: '{pasted_text}'")
                    # Если текст не вставился, пробуем еще раз
                    if not pasted_text.strip():
                        logger.info("Поле пустое, пробую повторную вставку...")
                        # Очищаем буфер и копируем заново
                        if not self.copy_to_clipboard(str(message)):
                            logger.error("Не удалось скопировать текст для повторной вставки")
                            return False
                        time.sleep(0.2)
                        pyautogui.hotkey('ctrl', 'v')
                        time.sleep(0.5)
                        
                        # Проверяем еще раз
                        pyautogui.hotkey('ctrl', 'a')
                        time.sleep(0.2)
                        pyautogui.hotkey('ctrl', 'c')
                        time.sleep(0.2)
                        pasted_text = pyperclip.paste()
                        if pasted_text.strip() == str(message).strip():
                            logger.info("✅ Повторная вставка успешна")
                        else:
                            logger.error(f"❌ Повторная вставка не удалась: '{pasted_text}'")
            except Exception as e:
                logger.warning(f"Не удалось проверить результат вставки: {e}")

            logger.info("Сообщение напечатано, готово к отправке")

            # Нажимаем Enter для отправки
            pyautogui.press("enter")
            time.sleep(2)

            logger.info("Сообщение отправлено, ждем ответ ИИ...")
            # Ждем, чтобы ИИ успел ответить
            time.sleep(7)

            # Копируем ответ: держим Shift и нажимаем Tab дважды, затем Enter
            logger.info("Копируем ответ ИИ...")
            # Снимаем активное выделение (если есть) и фокусируемся на чате Cascade
            pyautogui.press("esc")
            time.sleep(0.25)
            # Минимальная последовательность копирования ответа
            try:
                if main_window is not None:
                    main_window.set_focus()
            except Exception:
                pass
            time.sleep(0.2)
            if main_window is not None:
                main_window.type_keys("^l", set_foreground=True, pause=0.02)
                time.sleep(0.3)
            
            pyautogui.keyDown("shift")
            pyautogui.press("tab")
            time.sleep(0.2)
            pyautogui.press("tab")
            pyautogui.keyUp("shift")
            time.sleep(0.5)
            pyautogui.press("enter")
            time.sleep(2)

            # Проверяем что ответ скопирован в буфер
            copied_text = pyperclip.paste()
            # Если в буфере наше исходное сообщение, пробуем ещё раз: выделяем и копируем Ctrl+C
            if copied_text.strip().startswith(str(message).strip()[:20]):
                logger.info("В буфере исходное сообщение, пробую повторное копирование через Ctrl+C")
                try:
                    if main_window is not None:
                        main_window.set_focus()
                except Exception:
                    pass
                time.sleep(0.2)
                if main_window is not None:
                    main_window.type_keys("^l", set_foreground=True, pause=0.02)
                    time.sleep(0.3)
                pyautogui.keyDown("shift")
                pyautogui.press("tab")
                time.sleep(0.2)
                pyautogui.press("tab")
                pyautogui.keyUp("shift")
                time.sleep(0.3)
                if main_window is not None:
                    main_window.type_keys("^c", set_foreground=True, pause=0.02)
                    time.sleep(0.4)
                copied_text = pyperclip.paste()

            logger.info(f"Ответ скопирован в буфер: {copied_text[:100]}...")
            return True
        except Exception as e:
            logger.error(f"Ошибка: {str(e)}")
            return False

    async def send_message(self, message):
        """Асинхронная обертка для отправки сообщения"""
        return await asyncio.to_thread(self.send_message_sync, message)

    # def get_response_sync(self, wait_time=10, max_attempts=3):
    #     """Синхронная версия получения ответа"""
    #     attempt = 0
    #     last_response = "Не удалось распознать ответ"
    #     while attempt < max_attempts:
    #         try:
    #             app = Application(backend="uia").connect(title=WINDSURF_WINDOW_TITLE)
    #             app.window(title=WINDSURF_WINDOW_TITLE).set_focus()
    #             time.sleep(wait_time)
    #
    #             area = config.calibration_data["response_area"]
    #             bbox = (
    #                 area["x"],
    #                 area["y"],
    #                 area["x"] + area["width"],
    #                 area["y"] + area["height"],
    #             )
    #             pyautogui.click(area["x"], area["y"])  # Активируем область ответа
    #
    #             screenshot = ImageGrab.grab(bbox=bbox)
    #             response_text = ocr_processor.extract_text(screenshot)
    #             if response_text.strip():
    #                 last_response = response_text
    #                 break  # Успешно распознан текст
    #
    #             attempt += 1
    #             time.sleep(2)  # Пауза перед повтором
    #         except Exception as e:
    #             logger.error(f"Get response error (attempt {attempt + 1}): {e}")
    #             attempt += 1
    #             time.sleep(2)
    #
    #     return last_response

    async def get_response(self, wait_time=10, max_attempts=3):
        """Асинхронная обертка для получения ответа"""
        return await asyncio.to_thread(self.get_response_sync, wait_time, max_attempts)


desktop_controller = DesktopController()
