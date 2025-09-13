import google.generativeai as genai
import os
import logging
from dotenv import load_dotenv
from typing import List, Tuple

load_dotenv()
logger = logging.getLogger(__name__)


class AIProcessor:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            default_model = "gemini-2.5-flash"
            self.model = genai.GenerativeModel(default_model)
            self.model_name = default_model
        else:
            logger.warning(
                "GEMINI_API_KEY not found. AI summarization will be disabled."
            )
            self.model = None
            self.model_name = None

    def list_models(self) -> List[str]:
        """Возвращает список доступных моделей.
        Пытается получить список от API, если доступен ключ. Иначе — дефолтный набор.
        """
        default = [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "gemini-2.0-pro-exp-02-05",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ]
        models = set(default)
        if self.api_key:
            try:
                for m in genai.list_models():
                    name = getattr(m, "name", "")
                    # API возвращает ресурсы вида models/xxx
                    if name.startswith("models/"):
                        name = name.split("/", 1)[1]
                    if name:
                        models.add(name)
            except Exception as e:
                logger.debug(f"list_models failed: {e}")
        return sorted(models)

    def get_model_name(self) -> str | None:
        return self.model_name

    def set_model(self, model_name: str) -> Tuple[bool, str]:
        """Сменить текущую модель. Возвращает (ok, message)."""
        if not self.api_key:
            return False, "GEMINI_API_KEY не задан — работа с моделями недоступна"
        try:
            self.model = genai.GenerativeModel(model_name)
            self.model_name = model_name
            return True, f"Модель установлена: {model_name}"
        except Exception as e:
            logger.error(f"Не удалось установить модель '{model_name}': {e}")
            return False, f"Ошибка при установке модели: {e}"

    def summarize(self, text):
        """Суммаризация текста с помощью Gemini"""
        if not self.model or not text.strip():
            return text[:500] + "..." if len(text) > 500 else text

        try:
            prompt = f"""
            Суммаризируй следующий текст кратко и ясно на русском языке.\n
            Выдели основные идеи и ключевые моменты.

            Текст для суммаризации:
            {text}
            """

            response = self.model.generate_content(prompt)
            return response.text.strip()

        except Exception as e:
            logger.error(f"Gemini summarization error: {e}")
            return text[:500] + "..." if len(text) > 500 else text


ai_processor = AIProcessor()
