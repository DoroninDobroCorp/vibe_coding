#!/usr/bin/env python3
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(name)s - %(message)s')

try:
    from windsurf_controller import desktop_controller
    print("Import successful")
    
    print("Testing send_message_sync...")
    result = desktop_controller.send_message_sync('test message')
    print(f"Result: {result}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
