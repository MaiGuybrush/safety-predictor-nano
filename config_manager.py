import yaml
import os

class ConfigManager:
    def __init__(self, config_path="config.yaml"):
        self.config_path = config_path
        self.last_mtime = 0
        self.config = self.load_config()

    def check_for_updates(self):
        try:
            current_mtime = os.path.getmtime(self.config_path)
            if current_mtime > self.last_mtime:
                self.config = self.load_config()
                self.last_mtime = current_mtime
                return True
        except FileNotFoundError:
            pass
        return False

    def load_config(self):
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file {self.config_path} not found.")
        
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.last_mtime = os.path.getmtime(self.config_path)
            return yaml.safe_load(f)

    def get(self, key, default=None):
        return self.config.get(key, default)
