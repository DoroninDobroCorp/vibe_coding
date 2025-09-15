 # Windsurf Bot — RU / EN
 
 Этот проект — Telegram‑бот, который отправляет ваши сообщения в приложение `Windsurf Desktop` и возвращает ответ, когда он готов. На macOS «готовность» определяется двумя независимыми способами: по визуальной стабилизации контента и по «пиксельной» кнопке Send/Stop.
 
 This project is a Telegram bot that sends your messages to the `Windsurf Desktop` app and returns the reply when it is ready. On macOS, readiness is detected using two independent methods: visual stability of the content and the pixel‑based Send/Stop button.
 
 ---
 
 ## RU — Возможности
 - Отправка сообщений в активное окно Windsurf из Telegram.
 - Адресация по окнам на macOS: `[ #N ] текст` (по индексу из `/windows`) или `[ @часть_заголовка ] текст` (по подстроке заголовка).
 - Два детектора готовности (macOS):
   - Визуальная стабилизация (по умолчанию): фиксация «остановки движения» в области ответа по разнице последовательных скриншотов.
 
## EN — Features
- Send messages to the active Windsurf window from Telegram.
- macOS window targeting: `[ #N ] text` (by index from `/windows`) or `[ @title_substring ] text` (by substring).
- Two readiness detectors (macOS):
  - Visual stability (default): detect “no motion” in the reply area via screenshot difference.
  - Pixel button: detect Send/Stop by average color of the bottom‑right region.
- `/status` diagnostics: runtime telemetry incl. `response_stabilized_by = visual | pixel`.
- Utilities: `/windows`, `/model`, `/git`, `/whoami`.
 
---
 ---
 
 ## RU — Требования и права
 - Python 3.10+.
 - Установленный Windsurf Desktop (видимое окно).
 - macOS: включите права для приложения, из которого запускаете бота (Terminal/IDE):
   - System Settings → Privacy & Security → Screen Recording
   - System Settings → Privacy & Security → Accessibility
 
 ## EN — Requirements & Permissions
 - Python 3.10+.
 - Windsurf Desktop installed (window visible).
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
 3) Запустите приложение Windsurf Desktop.
 4) Запустите бота:
 ```bash
 python bot.py
 ```
 5) Напишите боту в Telegram — он отправит текст в Windsurf и вернёт ответ.
 
 ## EN — Install & Run
 1) Install dependencies:
 ```bash
 pip install -r requirements.txt
 ```
 2) Create `.env` from `.env.sample` and fill in variables.
 3) Launch Windsurf Desktop.
 4) Run the bot:
 ```bash
 python bot.py
 ```
 5) Send a message to the bot in Telegram. It forwards to Windsurf and returns the reply.
 
 ---
 
 ## RU — Команды Telegram
 - `/start` — краткая помощь.
 - `/status` — диагностика и параметры.
 - `/windows` — список окон Windsurf (macOS).
 - `/model` — управление моделью Gemini (list/set/current).
 - `/git` — git‑команды (root/status/commit/push) — доступ ограничен по user_id.
 - `/whoami` — показать ваш Telegram user_id.
 
 ## EN — Telegram Commands
 - `/start` — quick help.
 - `/status` — diagnostics and runtime parameters.
 - `/windows` — list Windsurf windows (macOS).
 - `/model` — manage Gemini model (list/set/current).
 - `/git` — git commands (root/status/commit/push) — access limited by user_id.
 - `/whoami` — show your Telegram user_id.
 
 ---
 
 ## RU — Детекторы готовности (macOS)
 - Визуальная стабилизация (по умолчанию):
   - берём мини‑скриншоты области контента окна; считаем среднюю разницу с предыдущим кадром;
   - если разница ниже порога на протяжении N секунд — считаем, что ответ готов;
   - затем копируем весь текст окна и возвращаем новый «суффикс» относительно baseline.
 - Пиксельная кнопка:
   - берём небольшой регион в правом нижнем углу;
   - по усреднённому цвету определяем `send` (синяя) / `stop` (яркая/белая);
   - как только видим `send` — считаем готово, копируем полный текст и извлекаем суффикс.
 
 ## EN — Readiness Detectors (macOS)
 - Visual stability (default):
   - take small screenshots of the content area; compute mean difference to previous frame;
   - if difference stays below a threshold for N seconds — reply is ready;
   - copy the entire text and return the new suffix relative to the baseline.
 - Pixel button:
   - sample the bottom‑right region;
   - detect `send` (blue) / `stop` (bright/white) by average color;
   - when `send` is seen — copy full text and extract the suffix.
 
 ---
 
 ## RU — Конфигурация (.env)
 - Обязательные:
   - `TELEGRAM_BOT_TOKEN` — токен бота.
 - Опциональные:
   - `WINDSURF_WINDOW_TITLE` — подстрока заголовка окна (best‑effort).
   - Тайминги:
     - `RESPONSE_WAIT_SECONDS` — пауза после отправки перед ожиданием (по умолчанию 7.0)
     - `RESPONSE_MAX_WAIT_SECONDS` — максимум ожидания ответа (по умолчанию 45)
     - `RESPONSE_POLL_INTERVAL_SECONDS` — интервал опроса (по умолчанию 0.8)
     - `RESPONSE_STABLE_MIN_SECONDS` — минимальная «тишина» для стабилизации (по умолчанию 1.6)
   - Вставка/копирование:
     - `PASTE_RETRY_COUNT`, `COPY_RETRY_COUNT`, `KEY_DELAY_SECONDS`
   - Фокус:
     - `USE_APPLESCRIPT_ON_MAC=1`, `FRONTMOST_WAIT_SECONDS`, `FOCUS_RETRY_COUNT`
   - Пиксельная кнопка:
     - `USE_UI_BUTTON_DETECTION=0|1`
     - `SEND_BTN_REGION_RIGHT`, `SEND_BTN_REGION_BOTTOM`, `SEND_BTN_REGION_W`, `SEND_BTN_REGION_H`
     - `SEND_BTN_BLUE_DELTA`, `SEND_BTN_WHITE_BRIGHT`
   - Визуальная стабилизация (по умолчанию включена):
     - `USE_VISUAL_STABILITY=1`
     - `VISUAL_REGION_TOP`, `VISUAL_REGION_BOTTOM`
     - `VISUAL_SAMPLE_INTERVAL_SECONDS`, `VISUAL_DIFF_THRESHOLD`, `VISUAL_STABLE_SECONDS`
   - Git:
     - `GIT_ALLOWED_USER_IDS`, `GIT_WORKDIR`
 
 ## EN — Configuration (.env)
 - Required:
   - `TELEGRAM_BOT_TOKEN` — bot token.
 - Optional:
   - `WINDSURF_WINDOW_TITLE` — window title substring (best‑effort).
   - Timings:
     - `RESPONSE_WAIT_SECONDS` (default 7.0)
     - `RESPONSE_MAX_WAIT_SECONDS` (default 45)
     - `RESPONSE_POLL_INTERVAL_SECONDS` (default 0.8)
     - `RESPONSE_STABLE_MIN_SECONDS` (default 1.6)
   - Paste/copy:
     - `PASTE_RETRY_COUNT`, `COPY_RETRY_COUNT`, `KEY_DELAY_SECONDS`
   - Focus:
     - `USE_APPLESCRIPT_ON_MAC=1`, `FRONTMOST_WAIT_SECONDS`, `FOCUS_RETRY_COUNT`
   - Pixel button:
     - `USE_UI_BUTTON_DETECTION=0|1`
     - `SEND_BTN_REGION_RIGHT`, `SEND_BTN_REGION_BOTTOM`, `SEND_BTN_REGION_W`, `SEND_BTN_REGION_H`
     - `SEND_BTN_BLUE_DELTA`, `SEND_BTN_WHITE_BRIGHT`
   - Visual stability (enabled by default):
     - `USE_VISUAL_STABILITY=1`
     - `VISUAL_REGION_TOP`, `VISUAL_REGION_BOTTOM`
     - `VISUAL_SAMPLE_INTERVAL_SECONDS`, `VISUAL_DIFF_THRESHOLD`, `VISUAL_STABLE_SECONDS`
   - Git:
     - `GIT_ALLOWED_USER_IDS`, `GIT_WORKDIR`
 
 ---
 
 ## RU — Советы и отладка
 - Если фиксация срабатывает слишком рано — увеличьте `VISUAL_STABLE_SECONDS` или немного поднимите `VISUAL_DIFF_THRESHOLD`.
 - Если слишком поздно — уменьшите `VISUAL_STABLE_SECONDS` или снизьте `VISUAL_DIFF_THRESHOLD`.
 - Команда `/status` показывает `response_stabilized_by` (visual|pixel) и базовую телеметрию.
 
 ## EN — Tips & Troubleshooting
 - If stabilization triggers too early — increase `VISUAL_STABLE_SECONDS` or slightly raise `VISUAL_DIFF_THRESHOLD`.
 - If too late — decrease `VISUAL_STABLE_SECONDS` or lower `VISUAL_DIFF_THRESHOLD`.
 - `/status` shows `response_stabilized_by` (visual|pixel) and basic telemetry.
