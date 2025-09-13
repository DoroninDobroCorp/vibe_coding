# Windsurf Bot

[//]: # (to run use: taskkill /f /im python.exe; Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'z:\Dev\vibe\vibe_coding'; python bot.py")

A bot for interacting with Windsurf Desktop via Telegram.

## Requirements

- Python 3.10+
- Windsurf Desktop (application installed and window visible)

## Installation

1. *Install dependencies*:
   ```bash
   pip install -r requirements.txt
2. Create a .env file based on .env.sample.
3. macOS: grant permissions
   - System Settings > Privacy & Security > Screen Recording (enable for Terminal/IDE)
   - System Settings > Privacy & Security > Accessibility (enable for Terminal/IDE)

## Usage
1. Launch Windsurf Desktop.
2. Run the bot locally:
```bash
python bot.py
```
3. Send a message to the bot in Telegram — it will be forwarded to Windsurf. The response will be copied from Windsurf and sent back to the bot. Optional: if GEMINI_API_KEY is set, you can post-process messages on your own.

### Commands
/start - Start working with the bot.  
/status — Diagnostics and runtime parameters.

## Platform notes

macOS

- The bot activates Windsurf via AppleScript (can be disabled by env flag) and interacts via Accessibility using hotkeys (Command+V, Command+C, etc.).  
- Ensure both Screen Recording and Accessibility permissions are granted for the app you use to run the bot (Terminal, iTerm, IDE).

Windows

- Uses `pywinauto` for window focus and `pyautogui` for key sequences. Make sure Windsurf window is visible.

## Configuration (.env)

Essential:

- `TELEGRAM_BOT_TOKEN` — Telegram bot token.
- `WINDSURF_WINDOW_TITLE` — optional title (best effort).

Optional:

- `GEMINI_API_KEY` — your Gemini API key (if you plan to do AI post-processing yourself).
- `RESPONSE_WAIT_SECONDS` — seconds to wait for AI reply in Windsurf after sending (default 7.0).
- `PASTE_RETRY_COUNT` — retries for paste operation (default 2).
- `COPY_RETRY_COUNT` — retries for copy operation (default 2).
- `KEY_DELAY_SECONDS` — delay between key presses (default 0.2).
- `USE_APPLESCRIPT_ON_MAC` — whether to activate Windsurf via AppleScript on macOS (1/0, default 1).

## Diagnostics

Use `/status` to see:

- platform, windows automation availability, Windsurf process list
- success/failed send counters and last error
- current runtime parameters (wait time, retry counts)
