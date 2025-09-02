import json
from pathlib import Path


class Config:
    def __init__(self):
        self.calibration_file = Path("calibration.json")
        self.calibration_data = self.load_calibration()

    def load_calibration(self):
        if self.calibration_file.exists():
            with open(self.calibration_file, "r") as f:
                return json.load(f)
        return {
            "input_box": None,
            "send_button": None,
            "confirm_button": None,
            "response_area": None,
            "window_region": None,
        }

    def save_calibration(self):
        with open(self.calibration_file, "w") as f:
            json.dump(self.calibration_data, f, indent=2)


config = Config()
