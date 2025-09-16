import os
import sys
import time
import logging
import subprocess
from typing import Optional

try:
    import psutil
except Exception:
    psutil = None  # fallback: supervisor will always spawn

logging.basicConfig(level=logging.INFO, format='%(levelname)s - supervisor - %(message)s')
logger = logging.getLogger('supervisor')


def _is_bot_running() -> bool:
    """Проверяет, запущен ли процесс telethon_bot.py (любой сессии)."""
    if psutil is None:
        return False
    try:
        for p in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmd = p.info.get('cmdline') or []
                cmdline = ' '.join(cmd).lower() if isinstance(cmd, list) else str(cmd).lower()
                if 'telethon_bot.py' in cmdline:
                    return True
            except Exception:
                continue
    except Exception:
        return False
    return False


def _spawn_bot(env: dict) -> subprocess.Popen:
    """Стартует telethon_bot.py в том же интерпретаторе Python."""
    py = sys.executable
    session_name = env.get('TELETHON_SESSION_NAME') or 'windsurf_telethon_bot'
    logger.info(f"Starting telethon_bot.py (session={session_name}) ...")
    return subprocess.Popen([py, 'telethon_bot.py'], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def main():
    env = os.environ.copy()
    env.setdefault('TELETHON_SESSION_NAME', 'windsurf_telethon_bot')
    # Параметры супервизора
    delay = float(env.get('SUPERVISOR_DELAY_SECONDS', '5'))
    run_seconds = float(env.get('SUPERVISOR_RUN_SECONDS', '0'))
    start_time = time.time()

    child: Optional[subprocess.Popen] = None

    try:
        while True:
            # Выход по таймеру (для самопроверки на 10 сек)
            if run_seconds > 0 and (time.time() - start_time) >= run_seconds:
                logger.info("Supervisor time limit reached, exiting...")
                if child and child.poll() is None:
                    try:
                        child.terminate()
                    except Exception:
                        pass
                break

            # Если бот уже запущен (кем-то ещё) — просто ждём
            if _is_bot_running():
                logger.debug("telethon_bot.py is already running, waiting...")
                time.sleep(max(0.5, delay))
                continue

            # Если нашего дочернего процесса нет/умер — запустим
            if child is None or child.poll() is not None:
                child = _spawn_bot(env)

            # Читаем хвост логов дочернего процесса без блокировки
            try:
                if child and child.stdout:
                    for _ in range(4):  # немного построчно, чтобы не заспамить
                        line = child.stdout.readline()
                        if not line:
                            break
                        line_s = line.strip()
                        if line_s:
                            logger.info(f"bot> {line_s}")
            except Exception:
                pass

            time.sleep(max(0.5, delay))
    finally:
        if child and child.poll() is None:
            try:
                child.terminate()
            except Exception:
                pass


if __name__ == '__main__':
    main()
