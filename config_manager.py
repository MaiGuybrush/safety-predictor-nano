import re
import yaml
import os

from argus_eventlog import parse_camera_id

_STREAM_MODEL_KEY_RE = re.compile(r"^streams\[(\d+)\]\.model$")


class ConfigManager:
    def __init__(self, config_path="config.yaml"):
        self.config_path = config_path
        self.last_mtime = 0
        self.config = self.load_config()

    def check_for_updates(self):
        try:
            current_mtime = os.path.getmtime(self.config_path)
            if current_mtime > self.last_mtime:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f)
                if isinstance(loaded, dict) and loaded:
                    self.config = loaded
                    self.last_mtime = current_mtime
                    return True
        except (FileNotFoundError, PermissionError, yaml.YAMLError):
            pass
        return False

    def load_config(self):
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file {self.config_path} not found.")

        with open(self.config_path, "r", encoding="utf-8") as f:
            self.last_mtime = os.path.getmtime(self.config_path)
            loaded = yaml.safe_load(f)
            if loaded is None or not isinstance(loaded, dict):
                return self.config if hasattr(self, "config") and self.config else {}
            return loaded

    def get(self, key, default=None):
        return self.config.get(key, default)

    def _parse_stream_list(self, raw_list, global_model):
        stream_configs = []
        for idx, item in enumerate(raw_list):
            if isinstance(item, dict):
                url = item.get("url", "")
                if not url or not isinstance(url, str) or not url.strip():
                    continue
                url = url.strip()
                model = item.get("model") or global_model
                label = item.get("label") or ""
                parsed_cam = parse_camera_id(url)
                camera_id = item.get("camera_id") or parsed_cam or label or f"stream{idx}"
                cfg = {
                    "url": url,
                    "model": model,
                    "label": label,
                    "camera_id": camera_id
                }
                if "model_format" in item:
                    cfg["model_format"] = item["model_format"]
                elif "model_format" in self.config:
                    cfg["model_format"] = self.config["model_format"]
                stream_configs.append(cfg)
            elif isinstance(item, str):
                url = item.strip()
                if not url:
                    continue
                parsed_cam = parse_camera_id(url)
                camera_id = parsed_cam or f"stream{idx}"
                cfg = {
                    "url": url,
                    "model": global_model,
                    "label": "",
                    "camera_id": camera_id
                }
                if "model_format" in self.config:
                    cfg["model_format"] = self.config["model_format"]
                stream_configs.append(cfg)
        return stream_configs

    def get_stream_configs(self):
        global_model = self.config.get("model_path", "yolov8n.pt")

        if "streams" in self.config and isinstance(self.config["streams"], list):
            return self._parse_stream_list(self.config["streams"], global_model)

        return []

    def get_ums_targets(self):
        """解析 config 中所有 ums_model 宣告（全域 + per-stream），回傳同步目標清單。

        每個目標為 {"key": "model_path" | "streams[<i>].model", "name": str, "version": "latest" | int}，
        若有宣告 format 則額外包含 "format"。
        沒有宣告 ums_model 時回傳空清單（no-op）。
        """
        targets = []

        global_decl = self.config.get("ums_model")
        if isinstance(global_decl, dict) and global_decl.get("name"):
            target = {
                "key": "model_path",
                "name": global_decl["name"],
                "version": global_decl.get("version", "latest"),
            }
            if "format" in global_decl:
                target["format"] = global_decl["format"]
            elif "model_format" in self.config:
                target["format"] = self.config["model_format"]
            targets.append(target)

        streams = self.config.get("streams")
        if isinstance(streams, list):
            for i, item in enumerate(streams):
                if not isinstance(item, dict):
                    continue
                decl = item.get("ums_model")
                if isinstance(decl, dict) and decl.get("name"):
                    target = {
                        "key": f"streams[{i}].model",
                        "name": decl["name"],
                        "version": decl.get("version", "latest"),
                    }
                    if "format" in decl:
                        target["format"] = decl["format"]
                    elif "model_format" in item:
                        target["format"] = item["model_format"]
                    elif "model_format" in self.config:
                        target["format"] = self.config["model_format"]
                    targets.append(target)

        return targets

    def update_model_paths(self, updates):
        """把同步後的實際路徑寫回 config.yaml 指定欄位，不重建整份 config。

        updates: dict，key 為 "model_path" 或 "streams[<i>].model"，value 為新路徑字串。
        """
        if not updates:
            return

        with open(self.config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        for key, value in updates.items():
            if key == "model_path":
                raw["model_path"] = value
                continue
            m = _STREAM_MODEL_KEY_RE.match(key)
            if not m:
                continue
            idx = int(m.group(1))
            streams = raw.get("streams")
            if isinstance(streams, list) and 0 <= idx < len(streams) and isinstance(streams[idx], dict):
                streams[idx]["model"] = value

        temp_file = self.config_path + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            yaml.dump(raw, f, allow_unicode=True)
        os.replace(temp_file, self.config_path)

        self.config = raw
        self.last_mtime = os.path.getmtime(self.config_path)

    def get_zones(self):
        zones = self.config.get("zones")
        if isinstance(zones, dict):
            return zones
        return {}

    def get_zone(self, stream_url):
        if not stream_url:
            return None
        return self.get_zones().get(stream_url)

    def save_zone(self, stream_url, polygon, zone_name=None):
        if not stream_url:
            return

        with open(self.config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        if "zones" not in raw or not isinstance(raw["zones"], dict):
            raw["zones"] = {}

        if polygon and len(polygon) >= 3:
            zone_data = {"polygon": polygon}
            if zone_name:
                zone_data["zone_name"] = zone_name
            raw["zones"][stream_url] = zone_data
        else:
            raw["zones"].pop(stream_url, None)

        temp_file = self.config_path + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            yaml.dump(raw, f, allow_unicode=True)
        os.replace(temp_file, self.config_path)

        self.config = raw
        self.last_mtime = os.path.getmtime(self.config_path)

    def delete_zone(self, stream_url):
        self.save_zone(stream_url, [])

