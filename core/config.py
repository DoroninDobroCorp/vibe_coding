"""Централизованная конфигурация проекта из .env файла."""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def _env_int(name: str, default: int) -> int:
    """Безопасно читает int из ENV с fallback на default."""
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    """Безопасно читает float из ENV с fallback на default."""
    try:
        return float(os.getenv(name, default))
    except Exception:
        return default


def _env_bool(name: str, default: str = "0") -> bool:
    """Безопасно читает bool из ENV (0/false/False считается False)."""
    return os.getenv(name, default) not in ("0", "false", "False")


class Config:
    """Централизованный конфигурационный класс для всех параметров проекта."""
    
    # === Telegram ===
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_API_ID: int = _env_int("TELEGRAM_API_ID", 0)
    TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")
    
    # === Windsurf Window ===
    WINDSURF_WINDOW_TITLE: str = os.getenv("WINDSURF_WINDOW_TITLE", "Windsurf")
    WINDSURF_PROCESS_MATCH: str = os.getenv("WINDSURF_PROCESS_MATCH", "Windsurf")
    WINDSURF_ALT_PROCESS_NAMES: str = os.getenv(
        "WINDSURF_ALT_PROCESS_NAMES", 
        "Electron,Windsurf Helper,Windsurf Helper (Renderer)"
    )
    WINDSURF_APP_NAME: str = os.getenv("WINDSURF_APP_NAME", "Windsurf")
    
    # === Gemini API ===
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # === Remote Controller ===
    REMOTE_CONTROLLER_URL: str = os.getenv("REMOTE_CONTROLLER_URL", "")
    
    # === Core Automation ===
    RESPONSE_WAIT_SECONDS: float = _env_float("RESPONSE_WAIT_SECONDS", 15.0)
    RESPONSE_MAX_WAIT_SECONDS: float = _env_float("RESPONSE_MAX_WAIT_SECONDS", 0)
    RESPONSE_POLL_INTERVAL_SECONDS: float = _env_float("RESPONSE_POLL_INTERVAL_SECONDS", 0.5)
    RESPONSE_STABLE_MIN_SECONDS: float = _env_float("RESPONSE_STABLE_MIN_SECONDS", 5.0)
    PASTE_RETRY_COUNT: int = _env_int("PASTE_RETRY_COUNT", 2)
    COPY_RETRY_COUNT: int = _env_int("COPY_RETRY_COUNT", 2)
    KEY_DELAY_SECONDS: float = _env_float("KEY_DELAY_SECONDS", 0.2)
    USE_APPLESCRIPT_ON_MAC: bool = _env_bool("USE_APPLESCRIPT_ON_MAC", "1")
    FRONTMOST_WAIT_SECONDS: float = _env_float("FRONTMOST_WAIT_SECONDS", 3.0)
    FOCUS_RETRY_COUNT: int = _env_int("FOCUS_RETRY_COUNT", 3)
    
    # === Visual Region ===
    VISUAL_REGION_TOP: int = _env_int("VISUAL_REGION_TOP", 100)
    VISUAL_REGION_BOTTOM: int = _env_int("VISUAL_REGION_BOTTOM", 150)
    VISUAL_SAMPLE_INTERVAL_SECONDS: float = _env_float("VISUAL_SAMPLE_INTERVAL_SECONDS", 0.5)
    VISUAL_DIFF_THRESHOLD: float = _env_float("VISUAL_DIFF_THRESHOLD", 5.0)
    VISUAL_STABLE_SECONDS: float = _env_float("VISUAL_STABLE_SECONDS", 2.0)
    USE_VISUAL_STABILITY: bool = _env_bool("USE_VISUAL_STABILITY", "1")
    
    # === Echo Filter & Copy Fallback ===
    ECHO_FILTER_ENABLED: bool = _env_bool("ECHO_FILTER_ENABLED", "1")
    ECHO_PREFIX_LEN: int = _env_int("ECHO_PREFIX_LEN", 24)
    ECHO_MAX_DELTA: int = _env_int("ECHO_MAX_DELTA", 64)
    ECHO_LEN_RATIO: float = _env_float("ECHO_LEN_RATIO", 1.4)
    USE_COPY_SHORT_FALLBACK: bool = _env_bool("USE_COPY_SHORT_FALLBACK", "1")
    
    # === Ready Pixel (главный триггер) ===
    USE_READY_PIXEL: bool = _env_bool("USE_READY_PIXEL", "1")
    READY_PIXEL_X: int = _env_int("READY_PIXEL_X", -1)
    READY_PIXEL_Y: int = _env_int("READY_PIXEL_Y", -1)
    READY_PIXEL_R: int = _env_int("READY_PIXEL_R", 165)
    READY_PIXEL_G: int = _env_int("READY_PIXEL_G", 171)
    READY_PIXEL_B: int = _env_int("READY_PIXEL_B", 166)
    READY_PIXEL_TOL: int = _env_int("READY_PIXEL_TOL", 4)
    READY_PIXEL_TOL_PCT: float = _env_float("READY_PIXEL_TOL_PCT", -1.0)
    READY_PIXEL_REQUIRED: bool = _env_bool("READY_PIXEL_REQUIRED", "1")
    READY_PIXEL_COORD_MODE: str = os.getenv("READY_PIXEL_COORD_MODE", "top")
    READY_PIXEL_DX: int = _env_int("READY_PIXEL_DX", 0)
    READY_PIXEL_DY: int = _env_int("READY_PIXEL_DY", 0)
    READY_PIXEL_PROBE_INTERVAL_SECONDS: float = _env_float("READY_PIXEL_PROBE_INTERVAL_SECONDS", 0.5)
    READY_PIXEL_AVG_K: int = _env_int("READY_PIXEL_AVG_K", 3)
    READY_PIXEL_REQUIRE_TRANSITION: bool = _env_bool("READY_PIXEL_REQUIRE_TRANSITION", "1")
    READY_PIXEL_STABLE_SECONDS: float = _env_float("READY_PIXEL_STABLE_SECONDS", 0.8)
    READY_PIXEL_TRANSITION_TIMEOUT_SECONDS: float = _env_float("READY_PIXEL_TRANSITION_TIMEOUT_SECONDS", 0)
    READY_PIXEL_SRC: str = os.getenv("READY_PIXEL_SRC", "cap")
    
    # === Answer/Input focus points ===
    INPUT_ABS_X: int = _env_int("INPUT_ABS_X", 1050)
    INPUT_ABS_Y: int = _env_int("INPUT_ABS_Y", 725)
    ANSWER_ABS_X: int = _env_int("ANSWER_ABS_X", 1087)
    ANSWER_ABS_Y: int = _env_int("ANSWER_ABS_Y", 349)
    COPY_CLICK_X: int = _env_int("COPY_CLICK_X", 1256)
    COPY_CLICK_Y: int = _env_int("COPY_CLICK_Y", 675)
    
    # === Copy Drag ===
    COPY_DRAG_START_X: int = _env_int("COPY_DRAG_START_X", 1260)
    COPY_DRAG_START_Y: int = _env_int("COPY_DRAG_START_Y", 655)
    COPY_DRAG_END_X: int = _env_int("COPY_DRAG_END_X", 915)
    COPY_DRAG_END_Y: int = _env_int("COPY_DRAG_END_Y", 65)
    COPY_DRAG_HOLD_SECONDS: float = _env_float("COPY_DRAG_HOLD_SECONDS", 5.0)
    
    # === Click coordinates ===
    CLICK_ABS_X: int = _env_int("CLICK_ABS_X", 0)
    CLICK_ABS_Y: int = _env_int("CLICK_ABS_Y", 0)
    CLICK_WINPCT: str = os.getenv("CLICK_WINPCT", "")
    RIGHT_CLICK_X_FRACTION: float = _env_float("RIGHT_CLICK_X_FRACTION", 0.5)
    RIGHT_CLICK_Y_OFFSET: int = _env_int("RIGHT_CLICK_Y_OFFSET", 80)
    CLICK_BEFORE_PASTE: bool = _env_bool("CLICK_BEFORE_PASTE", "1")
    
    # === Debugging ===
    SAVE_VISUAL_DEBUG: bool = _env_bool("SAVE_VISUAL_DEBUG", "0")
    SAVE_VISUAL_SAMPLES: bool = _env_bool("SAVE_VISUAL_SAMPLES", "1")
    SAVE_READY_ONLY_ON_MATCH: bool = _env_bool("SAVE_READY_ONLY_ON_MATCH", "0")
    SAVE_READY_HYPOTHESES: bool = _env_bool("SAVE_READY_HYPOTHESES", "1")
    SAVE_VISUAL_DIR: str = os.getenv("SAVE_VISUAL_DIR", "debug")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "DEBUG")
    DETAILED_AUTOMATION_LOG: bool = _env_bool("DETAILED_AUTOMATION_LOG", "1")
    TRIM_AFTER_PROMPT: bool = _env_bool("TRIM_AFTER_PROMPT", "1")
    
    # === UI Button Detection ===
    USE_UI_BUTTON_DETECTION: bool = _env_bool("USE_UI_BUTTON_DETECTION", "0")
    SEND_BTN_REGION_RIGHT: int = _env_int("SEND_BTN_REGION_RIGHT", 84)
    SEND_BTN_REGION_BOTTOM: int = _env_int("SEND_BTN_REGION_BOTTOM", 58)
    SEND_BTN_REGION_W: int = _env_int("SEND_BTN_REGION_W", 54)
    SEND_BTN_REGION_H: int = _env_int("SEND_BTN_REGION_H", 36)
    SEND_BTN_BLUE_DELTA: int = _env_int("SEND_BTN_BLUE_DELTA", 40)
    SEND_BTN_WHITE_BRIGHT: int = _env_int("SEND_BTN_WHITE_BRIGHT", 200)
    
    # === CPU Detection ===
    USE_CPU_READY_DETECTION: bool = _env_bool("USE_CPU_READY_DETECTION", "1")
    CPU_READY_THRESHOLD: float = _env_float("CPU_READY_THRESHOLD", 6.0)
    CPU_READY_STABLE_SECONDS: float = _env_float("CPU_READY_STABLE_SECONDS", 20.0)
    CPU_SAMPLE_INTERVAL_SECONDS: float = _env_float("CPU_SAMPLE_INTERVAL_SECONDS", 1.0)
    
    # === Fulltext Stabilization ===
    USE_FULLTEXT_STABILIZATION: bool = _env_bool("USE_FULLTEXT_STABILIZATION", "0")
    
    # === WS Model UI ===
    WSMODEL_PROBE_X: int = _env_int("WSMODEL_PROBE_X", 1179)
    WSMODEL_PROBE_Y: int = _env_int("WSMODEL_PROBE_Y", 728)
    WSMODEL_CONFIRM_SAFE_X: int = _env_int("WSMODEL_CONFIRM_SAFE_X", 1130)
    WSMODEL_CONFIRM_SAFE_Y: int = _env_int("WSMODEL_CONFIRM_SAFE_Y", 695)
    WSMODEL_RESTORE_CLIPBOARD: bool = _env_bool("WSMODEL_RESTORE_CLIPBOARD", "1")
    
    # === Change Project ===
    CHANGE_FINAL_PROBE_X: int = _env_int("CHANGE_FINAL_PROBE_X", 1210)
    CHANGE_FINAL_PROBE_Y: int = _env_int("CHANGE_FINAL_PROBE_Y", 15)
    
    # === Git ===
    GIT_ALLOWED_USER_IDS: str = os.getenv("GIT_ALLOWED_USER_IDS", "")
    GIT_WORKDIR: str = os.getenv("GIT_WORKDIR", "")
    
    # === AppleScript ===
    OSASCRIPT_TIMEOUT_SECONDS: float = _env_float("OSASCRIPT_TIMEOUT_SECONDS", 2.0)
    
    # === ENV Reload ===
    ENV_RELOAD_INTERVAL_SECONDS: float = _env_float("ENV_RELOAD_INTERVAL_SECONDS", 99999.0)


# Singleton instance
config = Config()
