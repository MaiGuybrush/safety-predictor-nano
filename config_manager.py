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

    def get_stream_configs(self):
        global_model = self.config.get("model_path", "yolov8n.pt")
        
        if "streams" in self.config and isinstance(self.config["streams"], list):
            stream_configs = []
            for item in self.config["streams"]:
                if not isinstance(item, dict):
                    continue
                url = item.get("url", "")
                if not url or not isinstance(url, str) or not url.strip():
                    continue
                url = url.strip()
                model = item.get("model") or global_model
                label = item.get("label") or ""
                stream_configs.append({
                    "url": url,
                    "model": model,
                    "label": label
                })
            return stream_configs
        
        if "rtsp_streams" in self.config and isinstance(self.config["rtsp_streams"], list):
            stream_configs = []
            for url in self.config["rtsp_streams"]:
                if not isinstance(url, str) or not url.strip():
                    continue
                stream_configs.append({
                    "url": url.strip(),
                    "model": global_model,
                    "label": ""
                })
            return stream_configs

        return []

