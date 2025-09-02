import google.generativeai as genai
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class AIProcessor:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-2.5-flash")
        else:
            logger.warning(
                "GEMINI_API_KEY not found. AI summarization will be disabled."
            )
            self.model = None

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
