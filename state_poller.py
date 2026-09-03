"""state_poller.py - 外部設備狀態同步模組

提供：
1. 背景輪詢執行緒 (Daemon Thread)，定期以 HTTP GET 獲取 MES/PLC 狀態。
2. JSON 巢狀路徑解析 (e.g. data.equipment.status)。
3. 異常防護與平滑降級 (fallback_value)。
4. 執行緒安全快取與 TTL 支援 (供 Webhook 推送與推論引擎讀取)。
"""

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

logger = logging.getLogger("system")


def extract_json_path(data: Any, path: str) -> Any:
    """從巢狀字典/陣列中根據點分隔路徑提取值 (e.g. "data.status" 或 "data.equipment.0.name")。"""
    if not path or not path.strip():
        return data
    tokens = path.strip().split(".")
    curr = data
    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        if isinstance(curr, dict):
            if tok in curr:
                curr = curr[tok]
            else:
                return None
        elif isinstance(curr, list):
            try:
                idx = int(tok)
                if 0 <= idx < len(curr):
                    curr = curr[idx]
                else:
                    return None
            except ValueError:
                return None
        else:
            return None
    return curr


class StatePoller:
    """外部狀態同步器：管理背景輪詢與 Webhook 快取。"""

    def __init__(self, external_states_config: Optional[Dict[str, Any]] = None):
        self.lock = threading.Lock()
        self._states: Dict[str, Dict[str, Any]] = {}
        self._config: Dict[str, Any] = external_states_config or {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def update_config(self, external_states_config: Dict[str, Any]):
        """動態更新外部狀態來源設定。"""
        with self.lock:
            self._config = external_states_config or {}

    def update_state(self, source: str, status: Any, ttl_seconds: Optional[int] = None):
        """手動或透過 Webhook 更新指定來源之狀態，可選帶入 TTL (秒)。"""
        if not source:
            return
        now = time.time()
        expires_at = (now + float(ttl_seconds)) if ttl_seconds is not None and float(ttl_seconds) > 0 else None
        with self.lock:
            self._states[str(source)] = {
                "value": status,
                "expires_at": expires_at,
                "updated_at": now,
                "source_type": "webhook" if ttl_seconds is not None else "manual",
            }

    def get_state(self, source: str, default: Any = None) -> Any:
        """取得指定來源之當前狀態，若過期則清除並回傳預設值。"""
        with self.lock:
            entry = self._states.get(str(source))
            if not entry:
                return default
            if entry.get("expires_at") and time.time() > entry["expires_at"]:
                self._states.pop(str(source), None)
                return default
            return entry.get("value", default)

    def get_current_states(self) -> Dict[str, Any]:
        """取得所有非過期來源之當前狀態字典 (source -> value)。"""
        now = time.time()
        result = {}
        with self.lock:
            expired = []
            for src, entry in self._states.items():
                exp = entry.get("expires_at")
                if exp and now > exp:
                    expired.append(src)
                else:
                    result[src] = entry.get("value")
            for exp_src in expired:
                self._states.pop(exp_src, None)
        return result

    def poll_source_once(self, source_name: str, cfg: Dict[str, Any]):
        """執行單次 HTTP GET 輪詢並更新狀態。"""
        url = cfg.get("url")
        if not url:
            return

        method = str(cfg.get("method", "GET")).upper()
        timeout = max(1, int(cfg.get("timeout_seconds", 2)))
        json_path = cfg.get("json_path", "")
        fallback = cfg.get("fallback_value", "UNKNOWN")

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Argus-StatePoller/1.0", "Accept": "application/json"}
            )
            req.get_method = lambda: method
            with urllib.request.urlopen(req, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                body = response.read().decode(charset)
                try:
                    parsed = json.loads(body)
                    extracted = extract_json_path(parsed, json_path)
                    val = extracted if extracted is not None else fallback
                except (json.JSONDecodeError, UnicodeDecodeError):
                    val = body.strip() or fallback

                with self.lock:
                    current_entry = self._states.get(source_name)
                    if current_entry and current_entry.get("source_type") == "webhook":
                        exp = current_entry.get("expires_at")
                        if exp and time.time() < exp:
                            return

                    self._states[source_name] = {
                        "value": val,
                        "expires_at": None,
                        "updated_at": time.time(),
                        "source_type": "poll",
                    }
        except Exception:
            # 輪詢異常平滑降級為 fallback_value
            with self.lock:
                current_entry = self._states.get(source_name)
                if current_entry and current_entry.get("source_type") == "webhook":
                    exp = current_entry.get("expires_at")
                    if exp and time.time() < exp:
                        return

                self._states[source_name] = {
                    "value": fallback,
                    "expires_at": None,
                    "updated_at": time.time(),
                    "source_type": "fallback",
                }

    def start(self):
        """啟動背景輪詢 Daemon 執行緒。"""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="StatePollerThread", daemon=True)
        self._thread.start()

    def stop(self):
        """停止背景輪詢執行緒。"""
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _run_loop(self):
        """輪詢主迴圈。"""
        last_polled: Dict[str, float] = {}
        while self._running and not self._stop_event.is_set():
            now = time.time()
            with self.lock:
                configs_snapshot = dict(self._config)

            for src, cfg in configs_snapshot.items():
                if not isinstance(cfg, dict):
                    continue
                interval = max(1, int(cfg.get("interval_seconds", 5)))
                last = last_polled.get(src, 0.0)
                if now - last >= interval:
                    self.poll_source_once(src, cfg)
                    last_polled[src] = now

            self._stop_event.wait(timeout=0.5)


# 全域單例實例，供 Web UI 與主迴圈共用
GLOBAL_STATE_POLLER = StatePoller()
