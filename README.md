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
/model — Manage Gemini model via Telegram:  
  - `/model current` — show current model  
  - `/model list [filter]` — list available models (optionally filtered)  
  - `/model set <name>` — set model, e.g. `gemini-2.5-pro`
  
/git — Manage Git repository (access limited by user_id):  
  - `/git status` — show short status and current branch  
  - `/git commit <message>` — run `git add -A` and `git commit -m <message>`  
  - `/git push [remote] [branch]` — push to remote (default `origin`) and current branch (or specified)  

/whoami — Show your Telegram `user_id` to configure access.

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
- `REMOTE_CONTROLLER_URL` — optional HTTP controller URL (e.g. `http://127.0.0.1:8089`). If set, bot will send messages via remote controller and use its response.
- `GIT_ALLOWED_USER_IDS` — comma-separated Telegram user IDs who can run `/git` commands, e.g. `123456789,987654321`.
- `RESPONSE_WAIT_SECONDS` — seconds to wait for AI reply in Windsurf after sending (default 7.0).
- `PASTE_RETRY_COUNT` — retries for paste operation (default 2).
- `COPY_RETRY_COUNT` — retries for copy operation (default 2).
- `KEY_DELAY_SECONDS` — delay between key presses (default 0.2).
- `USE_APPLESCRIPT_ON_MAC` — whether to activate Windsurf via AppleScript on macOS (1/0, default 1).

## Git via Telegram

You can manage your Git repository directly in Telegram using `/git` commands. For security, only users listed in `GIT_ALLOWED_USER_IDS` can run these commands.

Examples:

```text
/whoami
/git status
/git commit Fix: handle remote controller response
/git push               # defaults: origin <current-branch>
/git push origin main   # explicit
```

## Remote Controller

Run local HTTP controller to interact via REST (useful for remote bots/services):

```bash
python controller_server.py
```

Endpoints:

- `GET /health` — health check
- `GET /windows` — list windows titles (macOS)
- `POST /send` — send message `{ "message": "...", "target": "index:1" | "substring" }` and receive `{ ok, diag, response }`, where `response` is best-effort clipboard content (AI reply)

## Diagnostics

Use `/status` to see:

- platform, windows automation availability, Windsurf process list
- success/failed send counters and last error
- current runtime parameters (wait time, retry counts)
