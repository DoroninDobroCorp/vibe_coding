import os
import platform

import pytesseract

import logging

logger = logging.getLogger(__name__)


class OCRProcessor:
    def __init__(self):
        self._setup_tesseract_path()

        # Проверка доступности Tesseract
        try:
            version = pytesseract.get_tesseract_version()
            logger.info(f"Tesseract версия: {version}")
        except Exception as e:
            logger.error(f"Tesseract не найден: {e}")

    def _setup_tesseract_path(self):
        """Автоматическая настройка пути к Tesseract для разных ОС"""
        system = platform.system()

        if system == "Windows":
            # Стандартные пути для Windows
            possible_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]
        elif system == "Darwin":  # macOS
            # Пути для macOS (Homebrew и стандартные)
            possible_paths = [
                "/usr/local/bin/tesseract",
                "/opt/homebrew/bin/tesseract",
                "/usr/bin/tesseract",
            ]
        else:  # Linux
            possible_paths = ["/usr/bin/tesseract", "/usr/local/bin/tesseract"]

        # Проверяем существование путей
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                logger.info(f"Найден Tesseract по пути: {path}")
                return

        # Если не нашли, пробуем использовать из PATH
        logger.info("Tesseract не найден в стандартных путях, пробуем из PATH")
        try:
            pytesseract.get_tesseract_version()  # Проверяем доступность в PATH
            logger.info("Tesseract доступен через PATH")
        except:
            logger.warning("Tesseract не найден. OCR будет работать с ошибками")

    def preprocess_image(self, image):
        """Улучшенная предобработка изображения"""
        # Сохраняем оригинал для анализа
        image.save("original.png")
        logger.info("Сохранено оригинальное изображение: original.png")

        return image

    def extract_text(self, image, lang=os.getenv("OCR_LANGUAGE")):
        """Извлечение текста с различными настройками PSM"""
        try:
            processed_image = self.preprocess_image(image)

            # Пробуем разные режимы сегментации страницы (PSM)
            results = {}
            for psm in [6, 3, 4, 7]:
                custom_config = f"--oem 3 --psm {psm}"
                text = pytesseract.image_to_string(
                    processed_image, config=custom_config, lang=lang
                )
                results[f"psm_{psm}"] = text
                logger.info(
                    f"PSM {psm}: {text[:100]}..."
                    if text
                    else f"PSM {psm}: пустой текст"
                )

            # Также пробуем с белым списком символов для кириллицы
            cyrillic_whitelist = (
                "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя.,"
                '!?;:()[]{}@#$%^&*+-/=\\|_~«»‹›„""‚""`‛<>'
            )
            custom_config = (
                f"--oem 3 --psm 6 -c tessedit_char_whitelist={cyrillic_whitelist}"
            )
            text = pytesseract.image_to_string(
                processed_image, config=custom_config, lang=lang
            )
            results["psm_6_whitelist"] = text
            logger.info(
                f"PSM 6 с whitelist: {text[:100]}..."
                if text
                else "PSM 6 с whitelist: пустой текст"
            )

            # Возвращаем лучший результат (не пустой)
            for key, value in results.items():
                if value.strip():
                    return value.strip()

            logger.warning("Tesseract не распознал текст. Проверьте изображение.")
            return ""
        except Exception as e:
            logger.error(f"OCR Error: {str(e)}")
            return ""


ocr_processor = OCRProcessor()
