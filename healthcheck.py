import time
import logging
import platform
import os
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger("healthcheck")


def main():
    logger.info("Starting healthcheck...")

    # Check environment variables presence (not values)
    for var in [
        "TELEGRAM_BOT_TOKEN",
        "WINDSURF_WINDOW_TITLE",
        "GEMINI_API_KEY",
        "RESPONSE_WAIT_SECONDS",
        "PASTE_RETRY_COUNT",
        "COPY_RETRY_COUNT",
        "KEY_DELAY_SECONDS",
        "USE_APPLESCRIPT_ON_MAC",
    ]:
        logger.info(f"ENV {var} is set: {'yes' if os.getenv(var) is not None else 'no'}")

    # Import core modules
    try:
        # optional: ai processor
        try:
            from ai_processor import ai_processor  # noqa: F401
            logger.info("ai_processor imported OK (optional)")
        except Exception:
            logger.info("ai_processor not available (optional)")

        from windsurf_controller import desktop_controller
        logger.info("windsurf_controller imported OK")
    except Exception as e:
        logger.error(f"core import failed: {e}")
        return 1

    # Optional UI probe (set RUN_UI_CHECK=1 to enable)
    if os.getenv("RUN_UI_CHECK") in ("1", "true", "True"):
        try:
            is_windows = platform.system() == 'Windows'
            result = desktop_controller.send_message_sync("healthcheck")
            logger.info(f"send_message_sync returned: {result} (is_windows={is_windows})")
        except Exception as e:
            logger.error(f"send_message_sync raised exception: {e}")
            return 1

    logger.info("Sleeping 10s to watch for runtime errors...")
    time.sleep(10)
    logger.info("Healthcheck finished with no errors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
