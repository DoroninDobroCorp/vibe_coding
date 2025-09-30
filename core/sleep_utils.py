"""Утилиты для управления задержками и ожиданиями."""

import time


def sleep_interruptible(total_seconds: float, step_seconds: float = 0.05) -> None:
    """
    Сон маленькими шагами для быстрой реакции на KeyboardInterrupt (Ctrl+C).
    
    Args:
        total_seconds: Общее время сна в секундах
        step_seconds: Размер шага сна (по умолчанию 0.05с)
    """
    try:
        total = float(total_seconds)
    except Exception:
        total = 0.0
    
    if total <= 0:
        return
    
    try:
        step = max(0.01, float(step_seconds))
    except Exception:
        step = 0.05
    
    end = time.time() + total
    while True:
        remaining = end - time.time()
        if remaining <= 0:
            break
        time.sleep(min(step, remaining))
