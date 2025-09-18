#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Выводит список всех окон macOS через AppleScript (System Events):
- Для каждого процесса печатает его имя и список заголовков окон.
- Можно фильтровать по подстроке через переменную окружения TITLE_FILTER (нечувствительно к регистру).

Запуск:
  python debug/list_all_windows.py

Переменные окружения:
  TITLE_FILTER="windsurf"  — покажет только процессы/окна, где заголовок окна содержит подстроку
  OSASCRIPT_TIMEOUT_SECONDS=2.0 — таймаут на выполнение osascript
"""

import os
import subprocess
from typing import List, Tuple, Dict

# Попробуем использовать Quartz (CGWindowList) как надёжный фоллбэк
try:
    from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionAll, kCGNullWindowID  # type: ignore
    HAVE_QUARTZ = True
except Exception:
    HAVE_QUARTZ = False

OSASCRIPT_TIMEOUT_SECONDS = float(os.getenv("OSASCRIPT_TIMEOUT_SECONDS", "2.0"))
TITLE_FILTER = (os.getenv("TITLE_FILTER") or "").strip().lower()


def _osascript(script: str, timeout_sec: float | None = None) -> Tuple[int, str, str]:
    to = max(0.2, float(timeout_sec if (timeout_sec is not None) else OSASCRIPT_TIMEOUT_SECONDS))
    try:
        cp = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
            timeout=to,
        )
        return cp.returncode, (cp.stdout or ""), (cp.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def list_all_windows() -> List[Tuple[str, List[str]]]:
    """Возвращает список (process_name, [window_titles...]) для всех процессов GUI.
    Использует только System Events.
    """
    script = (
        'tell application "System Events"\n'
        '  set out to ""\n'
        '  set procs to every process\n'
        '  repeat with p in procs\n'
        '    try\n'
        '      set pname to name of p\n'
        '      set n to count windows of p\n'
        '      if n > 0 then\n'
        '        set out to out & "\n=== " & pname & " ===\n"\n'
        '        repeat with i from 1 to n\n'
        '          try\n'
        '            set nm to name of window i of p\n'
        '            set out to out & nm & linefeed\n'
        '          end try\n'
        '        end repeat\n'
        '      end if\n'
        '    end try\n'
        '  end repeat\n'
        '  return out\n'
        'end tell'
    )
    # Попытки с нарастающим таймаутом, если по умолчанию пусто
    timeouts = [OSASCRIPT_TIMEOUT_SECONDS]
    # Если значение по умолчанию слишком маленькое, добавим эскалацию
    if OSASCRIPT_TIMEOUT_SECONDS < 4.0:
        timeouts.append(4.0)
    if OSASCRIPT_TIMEOUT_SECONDS < 8.0:
        timeouts.append(8.0)
    rc = 1
    out = ""
    err = ""
    for to in timeouts:
        rc, out, err = _osascript(script, timeout_sec=to)
        # Прерываем, если что-то осмысленное вернулось
        if rc == 0 and (out or '').strip():
            break
    results: List[Tuple[str, List[str]]] = []
    if rc != 0:
        return results
    block: List[str] = []
    proc_name: str | None = None
    for line in (out or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        s = line.strip()
        if not s:
            continue
        if s.startswith("=== ") and s.endswith(" ==="):
            # завершить предыдущий блок
            if proc_name and block:
                results.append((proc_name, block[:]))
            proc_name = s[4:-4].strip()
            block = []
        else:
            if proc_name is not None:
                block.append(s)
    if proc_name and block:
        results.append((proc_name, block[:]))
    return results


def _merge_grouped(a: List[Tuple[str, List[str]]], b: List[Tuple[str, List[str]]]) -> List[Tuple[str, List[str]]]:
    by_proc: Dict[str, List[str]] = {}
    for src in (a, b):
        for pname, titles in src:
            lst = by_proc.setdefault(pname, [])
            for t in titles:
                if t and t not in lst:
                    lst.append(t)
    # Сортируем заголовки для стабильности
    out: List[Tuple[str, List[str]]] = []
    for pname, lst in by_proc.items():
        out.append((pname, sorted(lst)))
    # Стабильный порядок по имени процесса
    out.sort(key=lambda x: x[0].lower())
    return out


def _cg_list_windows() -> List[Tuple[str, List[str]]]:
    if not HAVE_QUARTZ:
        return []
    try:
        infos = CGWindowListCopyWindowInfo(kCGWindowListOptionAll, kCGNullWindowID) or []
    except Exception:
        return []
    grouped: Dict[str, List[str]] = {}
    try:
        for info in infos:
            try:
                owner = info.get('kCGWindowOwnerName') or ''
                title = info.get('kCGWindowName') or ''
                layer = int(info.get('kCGWindowLayer') or 0)
                if not owner or not title:
                    continue
                # Слой 0 — «обычные» окна, игнорируем панели/всплывающие служебные окна
                if layer != 0:
                    continue
                lst = grouped.setdefault(owner, [])
                if title not in lst:
                    lst.append(title)
            except Exception:
                continue
    except Exception:
        return []
    # В список-формат
    out: List[Tuple[str, List[str]]] = []
    for pname, titles in grouped.items():
        out.append((pname, titles))
    return out


def main() -> int:
    se_data = list_all_windows()  # System Events
    cg_data = _cg_list_windows()  # Quartz fallback — включён всегда
    # Объединим данные из обоих источников
    data = _merge_grouped(se_data, cg_data) if cg_data else se_data
    # Фильтрация по TITLE_FILTER
    if TITLE_FILTER:
        filtered: List[Tuple[str, List[str]]] = []
        for pname, titles in data:
            ft = [t for t in titles if TITLE_FILTER in t.lower()]
            if ft:
                filtered.append((pname, ft))
        data = filtered
    if not data:
        print("(пусто — ни System Events, ни CGWindowList не вернули окна)")
        return 0
    for pname, titles in data:
        print(f"\n=== {pname} ===")
        for i, t in enumerate(titles, start=1):
            print(f"#{i}: {t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
