 # Windsurf Bot — RU / EN

Этот проект — Telegram‑бот, который отправляет ваши сообщения в приложение `Windsurf Desktop` и возвращает ответ, когда он готов. Поддерживаются macOS и Windows. На macOS готовность определяется ТОЛЬКО опорным пикселем (READY_PIXEL).

This project is a Telegram bot that sends your messages to the `Windsurf Desktop` app and returns the reply when it is ready. macOS and Windows are supported. On macOS, readiness is detected ONLY by a READY_PIXEL.

---

## RU — Возможности
- Отправка сообщений в активное окно Windsurf из Telegram.
- Адресация по окнам на macOS: `[ #N ] текст` (по индексу из `/windows`) или `[ @часть_заголовка ] текст` (по подстроке заголовка).
- Готовность ответа (macOS):
  - READY_PIXEL: проверка заданной точки экрана по RGB/допуску. ENV перечитывается динамически в цикле. Никаких кликов по этой точке не выполняется.
- Копирование ответа делается из правой панели через протяжку с автоскроллом (без `Cmd+A`), затем очистка шума.
- Клик‑фокус в панель ответа перед вставкой: используется только `ANSWER_ABS_X/Y`.
- Фильтрация эхо исходного запроса, вырезка ответа по последнему вхождению промпта.
- Telegram‑статус и диагностика: `/status`, `/windows`, `/model`, `/whoami`.
- Корректное оповещение об ошибке отправки в Telegram при неуспехе (до ожидания READY_PIXEL).

> ⚠️ Ограничения (временные):
> - Тестирование через Telethon (скрипт `telethon_bot.py`) сейчас не поддерживается.
> - Полноценная поддержка нескольких окон Windsurf (адресная отправка в конкретное окно) пока не работает.

## EN — Features
- Send messages to the active Windsurf window from Telegram.
- macOS window targeting: `[ #N ] text` or `[ @title_substring ] text`.
- Reply readiness (macOS):
  - READY_PIXEL: check a screen point against target RGB within tolerance. ENV is reloaded dynamically. No clicks on that point are performed.
- Answer is copied from the right panel via mouse drag with autoscroll (no `Cmd+A`), then cleaned.
- Focus click before paste: use `ANSWER_ABS_X/Y` only.
- Echo filtering and prompt‑suffix extraction.
- Telegram diagnostics: `/status`, `/windows`, `/model`, `/whoami`.
- Proper Telegram error reporting if sending fails (before READY_PIXEL waiting).

> ⚠️ Limitations (temporary):
> - Testing via Telethon (`telethon_bot.py`) is not supported at the moment.
> - Full multi‑window support (targeted sending into a specific window) is currently not working.

---

## RU — Требования и права
- Python 3.10+.
- Установленный Windsurf Desktop (видимое окно).
- macOS: выдайте права Terminal/IDE:
  - System Settings → Privacy & Security → Screen Recording
  - System Settings → Privacy & Security → Accessibility

## EN — Requirements & Permissions
- Python 3.10+.
- Windsurf Desktop installed (visible window).
- macOS: grant permissions to your Terminal/IDE:
  - System Settings → Privacy & Security → Screen Recording
  - System Settings → Privacy & Security → Accessibility

---

## RU — Установка и запуск
1) Установите зависимости:
```bash
pip install -r requirements.txt
```
2) Создайте `.env` на основе `.env.sample` и заполните переменные.
3) Запустите Windsurf Desktop.
4) Запустите бота:
```bash
python bot.py
```
5) Напишите боту в Telegram.

## EN — Install & Run
1) Install dependencies:
```bash
pip install -r requirements.txt
```
2) Create `.env` from `.env.sample` and fill in variables.
3) Run Windsurf Desktop.
4) Start the bot:
```bash
python bot.py
```
5) Send a message to the bot.

---

## RU — Команды Telegram
- `/start` — краткая помощь.
- `/status` — диагностика и параметры (включая телеметрию READY_PIXEL и копирования).
- `/windows` — список окон Windsurf (macOS).
- `/model` — управление моделью Gemini (list/set/current).
- `/whoami` — показать ваш Telegram user_id.

## EN — Telegram Commands
- `/start` — quick help.
- `/status` — diagnostics and parameters (including READY_PIXEL and copy telemetry).
- `/windows` — list Windsurf windows (macOS).
- `/model` — manage Gemini model (list/set/current).
- `/whoami` — show your Telegram user_id.

---

## RU — Поведение по платформам
- **macOS**
- Перед вставкой клик‑фокус в область ответа: только `ANSWER_ABS_X/Y`.
- Вставка с верификацией через `Cmd+V` с ретраями. `Cmd+L` не используется (чтобы не уводить фокус).
- Ожидание готовности: READY_PIXEL (строго при `READY_PIXEL_REQUIRED=1`).
- Копирование из правой панели протяжкой вниз/вверх с автоскроллом; очистка текста и анти‑эхо.

**Windows**
- Поиск процесса и видимого окна Windsurf, `set_focus()`.
- Вставка с верификацией; копирование ответа из правой панели через протяжку.
- Очистка текста и анти‑эхо.

## EN — Platform Behavior
- **macOS**
- Focus click into the answer area before paste: `ANSWER_ABS_X/Y` only.
- Paste with verification via `Cmd+V` retries. No `Cmd+L` (to avoid focus stealing).
- Wait for readiness: READY_PIXEL (strict when `READY_PIXEL_REQUIRED=1`).
- Copy from the right panel by drag with autoscroll; clean the text and filter echo.

**Windows**
- Find Windsurf process/window, `set_focus()`.
- Paste verification; copy answer from the right panel by drag.
- Clean text and echo filter.

---

## RU — Конфигурация (.env)
Минимум:
- `TELEGRAM_BOT_TOKEN` — токен бота.

Ключевое для macOS:
- READY_PIXEL (строгая готовность):
  - `USE_READY_PIXEL=1`
  - `READY_PIXEL_X`, `READY_PIXEL_Y`
  - `READY_PIXEL_R`, `READY_PIXEL_G`, `READY_PIXEL_B`
  - `READY_PIXEL_TOL` и/или `READY_PIXEL_TOL_PCT`
  - `READY_PIXEL_REQUIRED=1` — бот отправит ответ в Telegram только при совпадении контрольной точки.
- Фокус перед вставкой:
  - `ANSWER_ABS_X`, `ANSWER_ABS_Y` — приоритетные пиксели для клика по панели ответа.
  - Fallback: правая треть окна + `VISUAL_REGION_TOP/BOTTOM`.
- Правый‑клик таргетинг (резерв):
  - `CLICK_WINPCT=x_pct,y_pct` или `CLICK_ABS_X/Y`, `RIGHT_CLICK_X_FRACTION`, `RIGHT_CLICK_Y_OFFSET`.

Диагностика и логирование:
- `LOG_LEVEL=DEBUG` — подробные логи.
- Снимки отладки (по умолчанию выключены):
  - `SAVE_VISUAL_DEBUG=0|1`, `SAVE_VISUAL_SAMPLES=0|1`, `SAVE_READY_ONLY_ON_MATCH=0|1`, `SAVE_READY_HYPOTHESES=0|1`.

## EN — Configuration (.env)
Minimal:
- `TELEGRAM_BOT_TOKEN` — bot token.

Key macOS settings:
- READY_PIXEL (strict readiness):
  - `USE_READY_PIXEL=1`
  - `READY_PIXEL_X/Y`
  - `READY_PIXEL_R/G/B`
  - `READY_PIXEL_TOL` and/or `READY_PIXEL_TOL_PCT`
  - `READY_PIXEL_REQUIRED=1` — only send to Telegram when the checkpoint matches.
- Focus before paste:
  - `ANSWER_ABS_X`, `ANSWER_ABS_Y` — preferred click coordinates for the answer panel.
  - Fallback: right third of the window + `VISUAL_REGION_TOP/BOTTOM`.
- Right‑panel targeting (fallback):
  - `CLICK_WINPCT=x_pct,y_pct` or `CLICK_ABS_X/Y`, `RIGHT_CLICK_X_FRACTION`, `RIGHT_CLICK_Y_OFFSET`.

Diagnostics and logging:
- `LOG_LEVEL=DEBUG` — verbose logs.
- Debug images (disabled by default):
  - `SAVE_VISUAL_DEBUG=0|1`, `SAVE_VISUAL_SAMPLES=0|1`, `SAVE_READY_ONLY_ON_MATCH=0|1`, `SAVE_READY_HYPOTHESES=0|1`.

---

## RU — Советы
- Если READY_PIXEL «не попадает» — проверьте `last_ready_pixel` в `/status` и корректируйте RGB/допуск.
- Если фокус уходит не туда — задайте `ANSWER_ABS_X/Y` или отрегулируйте `VISUAL_REGION_TOP/BOTTOM`.
- Не коммитьте `.env` с токенами: добавьте его в `.gitignore`.

## EN — Tips
- If READY_PIXEL doesn’t match — inspect `/status` → `last_ready_pixel`, adjust RGB/tolerance.
- If focus misbehaves — set `ANSWER_ABS_X/Y` or tune `VISUAL_REGION_TOP/BOTTOM`.
- Do not commit `.env` with secrets — add it to `.gitignore`.
