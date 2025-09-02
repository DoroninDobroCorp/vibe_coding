# Windsurf Bot

[//]: # (to run use: taskkill /f /im python.exe; Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'z:\Dev\vibe\vibe_coding'; python bot.py")

A bot for interacting with Windsurf Desktop via Telegram.

## Requirements

- Python 3.10+
- Tesseract-OCR (for OCR)
- Windsurf Desktop (open window)

## Installation

1. *Install dependencies*:
   ```bash
   pip install -r requirements.txt
2. *Install Tesseract-OCR*:

*Windows*: Download from the official website https://github.com/UB-Mannheim/tesseract/wiki   
*macOS*: brew install tesseract   
*Linux*: sudo apt install tesseract-ocr
3. Create a .env file based on .env.example.
4. *For macOS/Linux*:   
Ensure the bot has screen recording permissions:
macOS: System Settings > Privacy & Security > Screen Recording
Linux: Run with sudo or add the user to the video group.

## Usage
1. Launch Windsurf Desktop.
2. Run the bot locally:
```bash
python bot.py
```
3. First, perform calibration, only after that you can work with Windsurf.
4. Send a message to the bot in Telegram — it will be forwarded to Windsurf. The response will be summarized using AI and sent back to the bot. If AI is not connected, the bot will receive the first 100 characters of the response.

### Commands
/start - Start working with the bot.   
/calibrate_input — Calibrate the input field.   
/calibrate_button — Calibrate the send button.   
/confirm_button — Calibrate the confirmation button.   
/calibrate_response — Calibrate the response area.   
/status — Check calibration status.   
/full — Get the full response.
/auto_accept — Toggle automatic response acceptance ("Continue" buttons, etc.)

## Automatic Response Acceptance Feature

The bot can automatically click "Continue", "Accept" and similar buttons in the Windsurf interface. To use this feature:

1. Ensure all dependencies from requirements.txt are installed
2. Install Google Chrome (required for WebDriver)
3. Use the /auto_accept command to enable/disable the feature

The function works in the background and automatically clicks buttons with text starting with "continue" (case-insensitive).

### Notes on Automatic Acceptance:
- Requires screen recording permissions
- Only works when the Windsurf window is visible
- The automatic click method can be changed in the settings


