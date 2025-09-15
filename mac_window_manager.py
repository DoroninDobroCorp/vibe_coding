import logging
import subprocess
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class MacWindowManager:
    """Утилита для работы с окнами Windsurf на macOS через AppleScript/Accessibility.
    Требует включенный доступ в "Универсальный доступ" для терминала/процесса Python.
    """

    def _osascript(self, script: str) -> subprocess.CompletedProcess:
        return subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)

    def list_window_titles(self) -> List[str]:
        script = (
            'tell application "System Events" to tell process "Windsurf" to get name of windows'
        )
        res = self._osascript(script)
        if res.returncode != 0:
            return []
        # AppleScript может возвращать {"Title1", "Title2"} или строку при одном окне
        out = res.stdout.strip()
        if out.startswith("{") and out.endswith("}"):
            items = [s.strip().strip('"') for s in out[1:-1].split(",")]
            return items
        return [out.strip('"')] if out else []

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
