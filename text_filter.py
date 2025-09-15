import re
from typing import Optional

ECHO_PREFIX_LEN_DEFAULT = 24


def extract_answer_by_prompt(prompt: str, text: str, echo_prefix_len: int = ECHO_PREFIX_LEN_DEFAULT) -> str:
    """Вернуть часть текста после последнего вхождения prompt (или его префикса).
    Если совпадений нет — вернуть исходный text.
    """
    try:
        t = text or ""
        if not t:
            return t
        p = (prompt or "").strip()
        if p:
            idx = t.rfind(p)
            if idx >= 0:
                return t[idx + len(p):].lstrip()
            prefix = p[: min(echo_prefix_len, len(p))]
            if prefix:
                i2 = t.rfind(prefix)
                if i2 >= 0:
                    return t[i2 + len(prefix):].lstrip()
        return t
    except Exception:
        return text or ""


def clean_copied_text(prompt: str, text: str, echo_prefix_len: int = ECHO_PREFIX_LEN_DEFAULT) -> str:
    """Удаляет всё до вопроса, фильтрует шум (UI‑хвосты, даты) и удаляет строки, похожие на пользовательский вопрос/эхо."""
    try:
        # 1) Отрезаем всё до конца промпта (используя префикс при необходимости)
        s = extract_answer_by_prompt(prompt, text or "", echo_prefix_len)

        # Вспомогательные нормализаторы
        def _norm(s_: str) -> str:
            s_ = (s_ or "").lower()
            s_ = re.sub(r"[\s\t\n]+", " ", s_)            # схлопываем пробелы
            s_ = re.sub(r"[""'`“”«»()\[\]{}:;,.!?~|\\/+\\-]", " ", s_)  # убираем пунктуацию
            s_ = re.sub(r"\s+", " ", s_).strip()
            return s_

        def _tokens(s_: str) -> list[str]:
            s_ = _norm(s_)
            toks = re.split(r"[^a-zа-я0-9]+", s_)
            return [t for t in toks if len(t) > 2]

        prompt_norm = _norm(prompt or "")
        prompt_tokens = set(_tokens(prompt or ""))

        lines = (s or "").splitlines()
        month_re = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{1,2}:\d{2}\s+(AM|PM)$")
        noise_substrings = [
            "feedback submitted", "feedback", "submitted",
            "a fews ago", "a few sec ago", "a few mins ago", " ago",
            "edited", "copied",
            # русские UI‑метки
            "сохраненные кар", "сохраненные изоб", "сохранённые кар", "сохранённые изоб",
        ]

        refusal_phrases = [
            # частые boilerplate‑фразы отказа/редиректа
            "выходит за рамки моей компетенции",
            "я здесь, чтобы помочь с кодом",
            "this is outside the scope",
            "i'm here to help with code",
        ]

        cleaned: list[str] = []
        for ln in lines:
            raw_ln = ln
            low = raw_ln.strip().lower()

            # Пустые строки сохраняем (но потом схлопнем повторы)
            if not low:
                cleaned.append("")
                continue

            # Шум интерфейса и дат
            if any(ns in low for ns in noise_substrings):
                continue
            if month_re.match(raw_ln.strip()):
                continue
            if low.startswith("feedback") or low.startswith("submitted"):
                continue

            # Удаляем строки, похожие на вопрос пользователя (эхо), даже если частично
            ln_norm = _norm(raw_ln)
            if prompt_tokens:
                ln_tokens = set(_tokens(raw_ln))
                if ln_tokens:
                    inter = len(ln_tokens & prompt_tokens)
                    union = len(ln_tokens | prompt_tokens)
                    jacc = (inter / union) if union else 0.0
                    # если схожесть высокая и строка достаточно содержательная — считаем эхом
                    if jacc >= 0.6 and (len(ln_norm) >= 20 or inter >= 4):
                        continue
            # подстроковое совпадение длинных нормализованных фраз
            if len(ln_norm) >= 20 and (ln_norm in prompt_norm or prompt_norm in ln_norm):
                continue

            # Фразы‑отказы тоже удаляем
            if any(p in low for p in refusal_phrases):
                continue

            cleaned.append(raw_ln)

        # 2) Схлопываем ведущие/двойные пустые строки
        out_lines: list[str] = []
        prev_empty = True
        for ln in cleaned:
            is_empty = (ln.strip() == "")
            if is_empty and prev_empty:
                continue
            out_lines.append(ln)
            prev_empty = is_empty
        return "\n".join(out_lines).strip()
    except Exception:
        return (text or "").strip()
