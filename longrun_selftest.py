import os
import subprocess
import sys
import time
import logging
import asyncio

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger('longrun')


def run_bot_once(seconds: int = 5) -> bool:
    env = os.environ.copy()
    env['BOT_RUN_SECONDS'] = str(seconds)
    # уникальное имя сессии для Telethon, чтобы не конфликтовать с фоновым ботом
    env['TELETHON_SESSION_NAME'] = f"windsurf_telethon_bot_selftest_{int(time.time()*1000)}"
    logger.info(f"Starting telethon_bot.py for {seconds}s...")
    try:
        proc = subprocess.run([
            sys.executable, 'telethon_bot.py'
        ], env=env, capture_output=True, text=True, timeout=seconds + 15)
        if proc.returncode != 0:
            logger.error(f"telethon_bot.py exited with code {proc.returncode}\nSTDOUT:\n{proc.stdout[-1000:]}\nSTDERR:\n{proc.stderr[-1000:]}")
            return False
        else:
            # echo only tails to avoid spam
            out_tail = proc.stdout.splitlines()[-10:]
            err_tail = proc.stderr.splitlines()[-10:]
            if out_tail:
                logger.info("telethon_bot stdout tail:\n" + "\n".join(out_tail))
            if err_tail:
                logger.info("telethon_bot stderr tail:\n" + "\n".join(err_tail))
            return True
    except subprocess.TimeoutExpired as e:
        logger.error(f"telethon_bot.py timeout: {e}")
        return False
    except Exception as e:
        logger.exception(f"telethon_bot.py failed: {e}")
        return False


async def run_selftest_once() -> bool:
    import selftest_telethon as st  # local import to reuse functions
    try:
        ok = await st.run_once()
        return bool(ok)
    except Exception as e:
        logger.exception(f"selftest run_once failed: {e}")
        return False


def main():
    cycles = int(os.getenv('LONGRUN_CYCLES', '3'))
    bot_seconds = int(float(os.getenv('LONGRUN_BOT_SECONDS', '5')))
    skip_bot = (os.getenv('LONGRUN_SKIP_BOT', '0').lower() in ('1', 'true', 'yes'))
    delay = float(os.getenv('LONGRUN_DELAY_SECONDS', '5'))

    ok_all = True
    def _do_cycle(i: int, total: int | None):
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        if total:
            logger.info(f"===== Cycle {i}/{total} @ {ts} =====")
        else:
            logger.info(f"===== Cycle {i} (infinite) @ {ts} =====")
        ok_bot = True
        if not skip_bot:
            ok_bot = run_bot_once(bot_seconds)
        ok_self = asyncio.run(run_selftest_once())
        ok = ok_bot and ok_self
        logger.info(f"Cycle {i}: bot_ok={ok_bot}, selftest_ok={ok_self}")
        return ok

    if cycles <= 0:
        i = 0
        while True:
            i += 1
            ok = _do_cycle(i, None)
            ok_all = ok_all and ok
            time.sleep(max(0.0, delay))
    else:
        for i in range(1, cycles + 1):
            ok = _do_cycle(i, cycles)
            ok_all = ok_all and ok
            time.sleep(max(0.0, delay))

    if ok_all:
        logger.info("Longrun selftest: OK (all cycles passed)")
        return 0
    else:
        logger.error("Longrun selftest: FAILED (one or more cycles failed)")
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
