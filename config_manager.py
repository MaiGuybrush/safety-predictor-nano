import re
import yaml
import os

from argus_eventlog import parse_camera_id
import ums_config

DEFAULT_UMS_BASE_URLS = [
    "http://tncimweb1.cminl.oa/umsapiproxy/fab4ums",
    "http://tncimweb2.cminl.oa/umsapiproxy/fab4ums",
]

DEFAULT_PPE_CLASS_MAPPING = {
    "person": "person",
    "head": "head",
    "helmet": "helmet",
    "no_helmet": "no_helmet",
    "vest": "vest",
    "no_vest": "no_vest",
    "cone": "cone",
    "guardrail": "guardrail",
}

_STREAM_MODEL_KEY_RE = re.compile(r"^streams\[(\d+)\]\.model$")


class ConfigManager:
    def __init__(self, config_path="config.yaml", ums_api_config_path=None):
        self.config_path = config_path
        self.ums_api_config_path = ums_api_config_path
        self.last_mtime = 0
        self.config = self.load_config()
        self._ensure_ums_fab()

    def get_ums_api_config(self):
        config_dir = os.path.dirname(os.path.abspath(self.config_path)) if self.config_path else None
        return ums_config.load_ums_api_config(config_dir=config_dir, file_path=self.ums_api_config_path)

    def _ensure_ums_fab(self):
        """當設定檔未配置 ums_fab 時，自動偵測所在廠區（未命中則為 oa）並立即持久化寫回，
        同時清理舊版 ums_base_urls / ums_base_url 欄位。"""
        if not isinstance(self.config, dict):
            return

        modified = False
        ums_fab = self.config.get("ums_fab")
        if ums_fab is None or not str(ums_fab).strip():
            ips = ums_config.get_device_ipv4_addresses()
            ums_api_cfg = self.get_ums_api_config()
            detected_fab = ums_config.detect_fab_from_ips(ips, domain_define=ums_api_cfg.get("domainDefine"))
            self.config["ums_fab"] = detected_fab
            modified = True
        else:
            self.config["ums_fab"] = str(ums_fab).strip().lower()

        if "ums_base_urls" in self.config:
            self.config.pop("ums_base_urls", None)
            modified = True
        if "ums_base_url" in self.config:
            self.config.pop("ums_base_url", None)
            modified = True

        if modified and self.config_path and os.path.isfile(self.config_path):
            try:
                temp_file = self.config_path + ".tmp"
                with open(temp_file, "w", encoding="utf-8") as f:
                    yaml.dump(self.config, f, allow_unicode=True)
                os.replace(temp_file, self.config_path)
                self.last_mtime = os.path.getmtime(self.config_path)
            except Exception:
                pass

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

    def get_ums_fab(self):
        """取得目前設定的廠區代碼（小寫），預設為 'oa'。"""
        return str(self.config.get("ums_fab") or "oa").strip().lower()

    def get_ums_base_urls(self):
        """提供標準化的 UMS 端點 URL 清單。

        優先權：
        1. 環境變數 UMS_BASE_URL / UMS_BASE_URLS（支援逗號分隔）
        2. 根據目前設定的 ums_fab（若無則取 'oa'），自集中組態中查出對應的 api.<fab> 端點列表
        3. Fallback 至預設 OA 端點清單
        """
        env_val = os.environ.get("UMS_BASE_URL") or os.environ.get("UMS_BASE_URLS")
        if env_val and isinstance(env_val, str):
            urls = [u.strip() for u in env_val.split(",") if u.strip()]
            if urls:
                return urls

        ums_fab = self.get_ums_fab()
        ums_api_cfg = self.get_ums_api_config()
        endpoints = ums_config.get_ums_endpoints_for_fab(ums_fab, ums_api_config=ums_api_cfg)
        if endpoints:
            return endpoints

        return list(DEFAULT_UMS_BASE_URLS)

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

    def save_zone(self, stream_url, polygon, zone_name=None, trigger_mode="center", sensitivity=0.0, ppe_strategy=None, required_ppe=None):
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
            if trigger_mode:
                zone_data["trigger_mode"] = str(trigger_mode)
            if sensitivity is not None:
                zone_data["sensitivity"] = float(sensitivity)
            if ppe_strategy:
                zone_data["ppe_strategy"] = str(ppe_strategy)
            if required_ppe is not None and isinstance(required_ppe, list):
                zone_data["required_ppe"] = [str(x) for x in required_ppe]
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

    def get_ppe_class_mapping(self):
        """取得自訂模型類別到標準 PPE 類別的映射字典。
        以 DEFAULT_PPE_CLASS_MAPPING 為基準，並套用使用者自訂映射。
        """
        mapping = dict(DEFAULT_PPE_CLASS_MAPPING)
        raw = self.config.get("ppe_class_mapping")
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(k, str) and isinstance(v, str):
                    mapping[k] = v
        return mapping

    def get_external_states(self):
        """取得外部設備狀態輪詢配置字典 (source_name -> config)。"""
        raw = self.config.get("external_states")
        if not isinstance(raw, dict):
            return {}
        normalized = {}
        for source, cfg in raw.items():
            if not isinstance(cfg, dict):
                continue
            try:
                interval = max(1, int(cfg.get("interval_seconds", 5)))
            except (ValueError, TypeError):
                interval = 5
            try:
                timeout = max(1, int(cfg.get("timeout_seconds", 2)))
            except (ValueError, TypeError):
                timeout = 2
            normalized[str(source)] = {
                "url": str(cfg.get("url", "")),
                "method": str(cfg.get("method", "GET")).upper(),
                "interval_seconds": interval,
                "json_path": str(cfg.get("json_path", "")),
                "timeout_seconds": timeout,
                "fallback_value": str(cfg.get("fallback_value", "UNKNOWN")),
            }
        return normalized

    def get_compliance_rules(self):
        """取得啟用中之複合工安條件規則清單。"""
        raw = self.config.get("compliance_rules")
        if not isinstance(raw, list):
            return []
        rules = []
        for r in raw:
            if not isinstance(r, dict):
                continue
            if not r.get("enabled", True):
                continue
            rules.append(r)
        return rules
    def get_system_log_file(self):
        return self.config.get("system_log_file", "logs/system.log")

    def get_log_level(self):
        return self.config.get("log_level", "INFO")

    def get_log_backup_count(self):
        try:
            return int(self.config.get("log_backup_count", 3))
        except (ValueError, TypeError):
            return 3

    def get_event_retention_days(self):
        try:
            days = int(self.config.get("event_retention_days", 30))
            return days if days >= 1 else 30
        except (ValueError, TypeError):
            return 30

