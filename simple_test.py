print("Starting test...")

try:
    import pyautogui
    print("pyautogui imported")
    
    import pyperclip
    print("pyperclip imported")
    
    from pywinauto import Application
    print("pywinauto imported")
    
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    WINDSURF_WINDOW_TITLE = os.getenv("WINDSURF_WINDOW_TITLE")
    print(f"Window title: {WINDSURF_WINDOW_TITLE}")
    
    # Test window connection
    app = Application(backend="uia").connect(title=WINDSURF_WINDOW_TITLE)
    print("Connected to window")
    
    app.window(title=WINDSURF_WINDOW_TITLE).set_focus()
    print("Window focused")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
