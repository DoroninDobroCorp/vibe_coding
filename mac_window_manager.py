import logging
import os
import subprocess
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class MacWindowManager:
    """Утилита для работы с окнами Windsurf на macOS через AppleScript/Accessibility.
    Требует включенный доступ в "Универсальный доступ" для терминала/процесса Python.
    """

    def _osascript(self, script: str) -> subprocess.CompletedProcess:
        """Выполнить osascript с таймаутом. Таймаут задаётся OSASCRIPT_TIMEOUT_SECONDS (по умолчанию 2.0s).
        При таймауте возвращаем CompletedProcess с returncode=124 и stderr='timeout'.
        """
        try:
            t = float(os.getenv("OSASCRIPT_TIMEOUT_SECONDS", "2.0"))
        except Exception:
            t = 2.0
        try:
            return subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False, timeout=max(0.2, t))
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(args=["osascript", "-e", script], returncode=124, stdout="", stderr="timeout")

    def list_window_titles(self) -> List[str]:
        app_name = os.getenv("WINDSURF_APP_NAME", "Windsurf").strip() or "Windsurf"
        proc_match = os.getenv("WINDSURF_PROCESS_MATCH", app_name).strip() or app_name
        alt_names = [s.strip() for s in (os.getenv("WINDSURF_ALT_PROCESS_NAMES", "Windsurf Helper,Windsurf Helper (Renderer)").split(",")) if s.strip() and s.strip().lower() != "electron"]
        results: list[str] = []
        seen: set[str] = set()

        def _accumulate_single_or_list(out: str):
            nonlocal results, seen
            out = (out or "").strip()
            if not out:
                return
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
                items = [s for s in (i.strip() for i in items) if s]
                for it in items:
                    if it not in seen:
                        seen.add(it); results.append(it)
            else:
                single = out.strip('"').strip()
                if not single:
                    return
                if "," in single and not single.startswith("{") and not single.endswith("}"):
                    parts = [p.strip().strip('"') for p in single.split(",")]
                    parts = [p for p in parts if p]
                    for it in parts:
                        if it not in seen:
                            seen.add(it); results.append(it)
                else:
                    if single not in seen:
                        seen.add(single); results.append(single)

        # 1) Через System Events — предпочтительный способ без активации приложения
        script1 = f'tell application "System Events" to tell process "{app_name}" to get name of windows'
        res1 = self._osascript(script1)
        if res1.returncode == 0:
            _accumulate_single_or_list(res1.stdout)

        # 2) Перечисление окон по индексу
        script2 = (
            f'tell application "System Events" to tell process "{app_name}"\n'
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
        res2 = self._osascript(script2)
        if res2.returncode == 0:
            out2 = (res2.stdout or "").replace("\r\n", "\n").replace("\r", "\n").strip("\n ")
            for line in out2.split("\n"):
                nm = line.strip()
                if nm and nm not in seen:
                    seen.add(nm); results.append(nm)

        # 3) Фоллбэк по подстроке в имени процесса (охватывает вспомогательные процессы)
        script3 = (
            'tell application "System Events"\n'
            f'  set procs to every process whose name contains "{proc_match}"\n'
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
        res3 = self._osascript(script3)
        if res3.returncode == 0:
            out3 = (res3.stdout or "").replace("\r\n", "\n").replace("\r", "\n").strip("\n ")
            for line in out3.split("\n"):
                nm = line.strip()
                if nm and nm not in seen:
                    seen.add(nm); results.append(nm)

        # 4) Перебор альтернативных имён процессов (без общего 'Electron')
        for alt in alt_names:
            s0 = f'tell application "System Events" to tell process "{alt}" to get name of windows'
            r0 = self._osascript(s0)
            if r0.returncode == 0:
                _accumulate_single_or_list(r0.stdout)

        # 5) PID-based фоллбэк, ограниченный только на процессы, содержащие 'windsurf'
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
                    cmd_l = cmd.lower()
                    if "windsurf" in cmd_l:
                        try:
                            cand_pids.append(int(pid_str))
                        except Exception:
                            pass
                for pid in cand_pids[:30]:
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
                    rcP = self._osascript(sPID)
                    if rcP.returncode == 0:
                        _accumulate_single_or_list(rcP.stdout)
        except Exception:
            pass

        return results

    def list_window_titles_with_debug(self) -> Tuple[List[str], List[str]]:
        app_name = os.getenv("WINDSURF_APP_NAME", "Windsurf").strip() or "Windsurf"
        proc_match = os.getenv("WINDSURF_PROCESS_MATCH", app_name).strip() or app_name
        alt_names = [s.strip() for s in (os.getenv("WINDSURF_ALT_PROCESS_NAMES", "Windsurf Helper,Windsurf Helper (Renderer)").split(",")) if s.strip() and s.strip().lower() != "electron"]
        results: list[str] = []
        seen: set[str] = set()
        dbg: list[str] = []

        def _acc(out: str):
            out = (out or "").strip()
            if not out:
                return
            if out.startswith("{") and out.endswith("}"):
                content = out[1:-1].strip()
                items: List[str] = []
                cur = []
                in_q = False
                prev = ''
                for ch in content:
                    if ch == '"' and prev != '\\':
                        in_q = not in_q; cur.append(ch)
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
                for it in (s for s in (i.strip() for i in items) if s):
                    if it not in seen:
                        seen.add(it); results.append(it)
            else:
                single = out.strip('"').strip()
                if single:
                    if "," in single and not single.startswith("{") and not single.endswith("}"):
                        parts = [p.strip().strip('"') for p in single.split(",")]
                        for it in (p for p in parts if p):
                            if it not in seen:
                                seen.add(it); results.append(it)
                    else:
                        if single not in seen:
                            seen.add(single); results.append(single)

        # Strategy 1 (System Events → process "app_name")
        s1 = f'tell application "System Events" to tell process "{app_name}" to get name of windows'
        r1 = self._osascript(s1)
        dbg.append(f"script1 rc={r1.returncode} raw={(r1.stdout or '').strip()!r}")
        if r1.returncode == 0:
            _acc(r1.stdout)

        # Strategy 2 (enumerate windows)
        s2 = (
            f'tell application "System Events" to tell process "{app_name}"\n'
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
        r2 = self._osascript(s2)
        dbg.append(f"script2 rc={r2.returncode} raw={(r2.stdout or '').strip()!r}")
        if r2.returncode == 0:
            out2 = (r2.stdout or "").replace("\r\n", "\n").replace("\r", "\n").strip("\n ")
            items2 = [line.strip() for line in out2.split("\n") if line.strip()]
            dbg.append(f"script2 parsed={items2}")
            for it in items2:
                if it not in seen:
                    seen.add(it); results.append(it)

        # Strategy 3 (System Events → processes whose name contains proc_match)
        s3 = (
            'tell application "System Events"\n'
            f'  set procs to every process whose name contains "{proc_match}"\n'
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
        r3 = self._osascript(s3)
        dbg.append(f"script3 rc={r3.returncode} raw={(r3.stdout or '').strip()!r}")
        if r3.returncode == 0:
            out3 = (r3.stdout or "").replace("\r\n", "\n").replace("\r", "\n").strip("\n ")
            items3 = [line.strip() for line in out3.split("\n") if line.strip()]
            dbg.append(f"script3 parsed={items3}")
            for it in items3:
                if it not in seen:
                    seen.add(it); results.append(it)

        # Strategy 4: alternative helper process names (no generic 'Electron')
        for alt in alt_names:
            sA = f'tell application "System Events" to tell process "{alt}" to get name of windows'
            rA = self._osascript(sA)
            dbg.append(f"alt:{alt} proc rc={rA.returncode} raw={(rA.stdout or '').strip()!r}")
            if rA.returncode == 0:
                _acc(rA.stdout)

        # Strategy 5: PID-based limited to 'windsurf' in command line
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
                    if "windsurf" in cmd.lower():
                        try:
                            cand_pids.append(int(pid_str))
                        except Exception:
                            pass
                for pid in cand_pids[:30]:
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
                    rP = self._osascript(sPID)
                    dbg.append(f"pid:{pid} rc={rP.returncode} raw={(rP.stdout or '').strip()!r}")
                    if rP.returncode == 0 and (rP.stdout or '').strip():
                        _acc(rP.stdout)
        except Exception:
            pass

        return results, dbg

    def focus_by_index(self, index_one_based: int) -> bool:
        try:
            script = (
                'tell application "Windsurf" to activate\n'
                f'tell application "System Events" to tell process "Windsurf" to perform action "AXRaise" of window {index_one_based}'
            )
            res = self._osascript(script)
            return res.returncode == 0
        except Exception:
            return False

    def focus_by_title_substring(self, substr: str) -> bool:
        titles = self.list_window_titles()
        if not titles:
            return False
        for idx, title in enumerate(titles, start=1):
            if substr.lower() in (title or "").lower():
                return self.focus_by_index(idx)
        return False

    def is_frontmost(self) -> bool:
        script = 'tell application "System Events" to get frontmost of process "Windsurf"'
        res = self._osascript(script)
        return res.returncode == 0 and res.stdout.strip().lower() in ("true", "yes")

    def get_front_window_bounds(self) -> Optional[Tuple[int, int, int, int]]:
        """Возвращает (x, y, w, h) активного окна Windsurf. None при ошибке."""
        try:
            pos = self._osascript('tell application "System Events" to tell process "Windsurf" to get position of window 1')
            size = self._osascript('tell application "System Events" to tell process "Windsurf" to get size of window 1')
            if pos.returncode != 0 or size.returncode != 0:
                return None
            # Ответ вида: "{x, y}" и "{w, h}" или "x, y" без скобок
            def _parse_pair(s: str):
                s = (s or "").strip().strip("{}").strip()
                parts = [p.strip() for p in s.split(",")]
                if len(parts) != 2:
                    return None
                try:
                    return int(float(parts[0])), int(float(parts[1]))
                except Exception:
                    return None
            xy = _parse_pair(pos.stdout)
            wh = _parse_pair(size.stdout)
            if not xy or not wh:
                return None
            return xy[0], xy[1], wh[0], wh[1]
        except Exception as e:
            logger.debug(f"get_front_window_bounds failed: {e}")
            return None
