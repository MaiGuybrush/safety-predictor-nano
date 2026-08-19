# 02 — 組態綱要擴充與 REST API 持久化 (Config Schema & Zone REST API)

**What to build:**
擴充 `config_manager.py` 與 `web_ui.py`，使 ROI 區域設定支援持久化儲存 `trigger_mode` 與 `sensitivity` 參數。`GET /zone/<stream_url>` 與 `POST /zone/<stream_url>` 端點正確序列化與保存設定至 `config.yaml`，並透過 atomic file replacement 確保後端主迴圈能立即熱重載套用。

**Blocked by:** 01 — 核心幾何判定引擎與相交模式支援 (Core Geometry & Intersect Mode Engine)

**Status:** resolved

- [x] `config_manager.save_zone(stream_url, polygon, zone_name=None, trigger_mode="center", sensitivity=0.0)` 支援寫入擴充欄位至 `config.yaml`
- [x] `config_manager.get_zone(stream_url)` 回傳包含 `trigger_mode` 與 `sensitivity` 完整屬性
- [x] `GET /zone/<path:stream_url>` 端點正確回傳 `trigger_mode` 與 `sensitivity`（缺失時提供安全預設值）
- [x] `POST /zone/<path:stream_url>` 端點正確接收並保存 `trigger_mode` 與 `sensitivity`
- [x] 單元測試 `test_config_manager.py` 與 `test_zone_endpoint.py` 完整驗證持久化與 API 合約

## Answer
擴充了 `ConfigManager.save_zone()` 支援 `trigger_mode` 與 `sensitivity` 的 YAML 持久化，並在 `web_ui.py` 的 `/zone/<stream_url>` GET 與 POST API 端點中完整處理了兩項參數的讀取、寫入與預設值賦予。單元測試 `test_config_manager.py` 與 `test_zone_endpoint.py` 全數通過。
