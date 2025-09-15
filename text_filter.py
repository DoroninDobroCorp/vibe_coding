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
    """Удаляет всё до вопроса и фильтрует шумовые строки (UI-хвосты, подписи, даты)."""
    try:
        s = extract_answer_by_prompt(prompt, text or "", echo_prefix_len)
        lines = (s or "").splitlines()
        month_re = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{1,2}:\d{2}\s+(AM|PM)$")
        noise_substrings = [
            "feedback submitted",
            "feedback",
            "submitted",
            "a fews ago",
            "a few sec ago",
            "a few mins ago",
            " ago",
            "edited",
            "copied",
            # русские UI-метки
            "сохраненные кар",   # сохраненные картинки
            "сохраненные изоб",  # сохраненные изображения
            "сохранённые кар",
            "сохранённые изоб",
        ]
        cleaned = []
        for ln in lines:
            low = ln.strip().lower()
            if not low:
                cleaned.append("")
                continue
            if any(ns in low for ns in noise_substrings):
                continue
            if month_re.match(ln.strip()):
                continue
            if low.startswith("feedback") or low.startswith("submitted"):
                continue
            cleaned.append(ln)
        # Убираем ведущие/двойные пустые строки
        out_lines = []
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
