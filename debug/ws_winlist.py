#!/usr/bin/env python3
import os
import subprocess
import sys
from typing import List, Tuple

APP_NAME = os.getenv("WINDSURF_APP_NAME", "Windsurf").strip() or "Windsurf"
PROC_MATCH = os.getenv("WINDSURF_PROCESS_MATCH", APP_NAME).strip() or APP_NAME
ALT_PROCESS_NAMES = [s.strip() for s in (os.getenv("WINDSURF_ALT_PROCESS_NAMES", "Electron,Windsurf Helper,Windsurf Helper (Renderer)").split(",")) if s.strip()]
OSASCRIPT_TIMEOUT_SECONDS = float(os.getenv("OSASCRIPT_TIMEOUT_SECONDS", "2.0"))


def _osascript(script: str) -> Tuple[int, str, str]:
    try:
        cp = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
            timeout=max(0.2, OSASCRIPT_TIMEOUT_SECONDS),
        )
        return cp.returncode, (cp.stdout or ""), (cp.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def _parse_osascript_list(out: str) -> List[str]:
    out = (out or "").strip()
    if not out:
        return []
    # AppleScript обычно возвращает либо {"A", "B"} либо одиночную строку
    if out.startswith("{") and out.endswith("}"):
        content = out[1:-1].strip()
        items: List[str] = []
        cur = []
        in_q = False
        prev = ''
        for ch in content:
            if ch == '"' and prev != '\\':
                in_q = not in_q
                cur.append(ch)
            elif ch == ',' and not in_q:
                token = ''.join(cur).strip().strip('"')
                if token:
                    items.append(token)
                cur = []
            else:
                cur.append(ch)
            prev = ch
        token = ''.join(cur).strip().strip('"')
        if token:
            items.append(token)
        return [s for s in (i.strip() for i in items) if s]
    # Иногда список приходит как строка с запятыми
    single = out.strip('"').strip()
    if "," in single and not single.startswith("{") and not single.endswith("}"):
        parts = [p.strip().strip('"') for p in single.split(",")]
        return [p for p in parts if p]
    return [single] if single else []


def list_windows_debug() -> Tuple[List[str], List[str]]:
    results: List[str] = []
    seen = set()
    dbg: List[str] = []

    def acc(out: str):
        nonlocal results, seen
        for it in _parse_osascript_list(out):
            if it and it not in seen:
                seen.add(it); results.append(it)

    # 0) Прямо через приложение
    s0 = f'tell application "{APP_NAME}" to get name of windows'
    rc, out, err = _osascript(s0)
    dbg.append(f"script0 rc={rc} raw={out.strip()!r}")
    if rc == 0:
        acc(out)

    # 1) System Events → process "APP_NAME"
    s1 = f'tell application "System Events" to tell process "{APP_NAME}" to get name of windows'
    rc, out, err = _osascript(s1)
    dbg.append(f"script1 rc={rc} raw={out.strip()!r}")
    if rc == 0:
        acc(out)

    # 2) System Events → enumerate windows (index)
    s2 = (
        f'tell application "System Events" to tell process "{APP_NAME}"\n'
        'set n to count windows\n'
        'set out to ""\n'
        'repeat with i from 1 to n\n'
        '  try\n'
        '    set nm to name of window i\n'
        '    set out to out & nm & linefeed\n'
        '  end try\n'
        'end repeat\n'
        'return out\n'
        'end tell\n'
        'end tell'
    )
    rc, out, err = _osascript(s2)
    dbg.append(f"script2 rc={rc} raw={(out or '').strip()!r}")
    if rc == 0:
        for line in (out or '').replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            nm = line.strip()
            if nm and nm not in seen:
                seen.add(nm); results.append(nm)

    # 3) System Events → processes whose name contains PROC_MATCH
    s3 = (
        'tell application "System Events"\n'
        f'  set procs to every process whose name contains "{PROC_MATCH}"\n'
        '  set out to ""\n'
        '  repeat with p in procs\n'
        '    try\n'
        '      tell p\n'
        '        set n to count windows\n'
        '        repeat with i from 1 to n\n'
        '          try\n'
        '            set nm to name of window i\n'
        '            set out to out & nm & linefeed\n'
        '          end try\n'
        '        end repeat\n'
        '      end tell\n'
        '    end try\n'
        '  end repeat\n'
        '  return out\n'
        'end tell'
    )
    rc, out, err = _osascript(s3)
    dbg.append(f"script3 rc={rc} raw={(out or '').strip()!r}")
    if rc == 0:
        for line in (out or '').replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            nm = line.strip()
            if nm and nm not in seen:
                seen.add(nm); results.append(nm)

    # 4) Альтернативные имена процессов (и как app, и как process)
    for alt in ALT_PROCESS_NAMES:
        sA = f'tell application "{alt}" to get name of windows'
        rcA, outA, errA = _osascript(sA)
        dbg.append(f"alt:{alt} app rc={rcA} raw={(outA or '').strip()!r}")
        if rcA == 0:
            acc(outA)
        sB = f'tell application "System Events" to tell process "{alt}" to get name of windows'
        rcB, outB, errB = _osascript(sB)
        dbg.append(f"alt:{alt} proc rc={rcB} raw={(outB or '').strip()!r}")
        if rcB == 0:
            acc(outB)

    # 5) PID-based фоллбэк: пройдёмся по всем PID, содержащим windsuf/electron
    try:
        ps = subprocess.run(["ps", "-axo", "pid,command"], capture_output=True, text=True, check=False)
        if ps.returncode == 0:
            lines = (ps.stdout or "").splitlines()
            cand_pids: List[int] = []
            for ln in lines:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    pid_str, cmd = ln.split(None, 1)
                except ValueError:
                    continue
                pid_str = pid_str.strip()
                cmd_l = cmd.lower()
                # Heuristics: любые процессы, содержащие windsuf или electron
                if ("windsurf" in cmd_l) or ("electron" in cmd_l):
                    try:
                        cand_pids.append(int(pid_str))
                    except Exception:
                        pass
            # Для каждого pid попробуем получить окна через System Events по unix id
            for pid in cand_pids[:30]:  # разумный лимит
                sPID = (
                    'tell application "System Events"\n'
                    f'  set theProc to first process whose unix id is {pid}\n'
                    '  try\n'
                    '    tell theProc to get name of windows\n'
                    '  on error\n'
                    '    return ""\n'
                    '  end try\n'
                    'end tell'
                )
                rcP, outP, errP = _osascript(sPID)
                dbg.append(f"pid:{pid} rc={rcP} raw={(outP or '').strip()!r}")
                if rcP == 0 and (outP or '').strip():
                    acc(outP)
    except Exception:
        pass

    return results, dbg


def main():
    titles, dbg = list_windows_debug()
    print("\n🪟 Окна Windsurf:")
    if titles:
        for i, t in enumerate(titles, start=1):
            print(f"#{i}: {t}")
    else:
        print("(не найдено)")
    print("\nDebug (AppleScript):")
    for d in dbg[:50]:
        print("•", d)


if __name__ == "__main__":
    sys.exit(main() or 0)
