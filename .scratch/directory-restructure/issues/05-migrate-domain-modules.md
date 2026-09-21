# 05 — 領域業務模組搬遷與內部匯入重構 (Migrate Domain Modules)

Gitea Issue: #72
Type: task
Status: resolved
Blocked by: 04

## Question
如何將根目錄 20+ 個業務邏輯 Python 檔案搬遷至 `src/argus/` 內對應領域子套件中，並將各模組內部的互相引用改寫為 `argus.*` 命名空間的標準匯入？

## Tasks
- [x] 搬遷 Core 領域：`config_manager.py`, `main.py` 至 `src/argus/core/` 與 `src/argus/`。
- [x] 搬遷 Capture 領域：`stream_handler.py`, `video_handler.py`, `grid_composer.py` 至 `src/argus/capture/`。
- [x] 搬遷 Vision 領域：`inference_engine.py` 至 `src/argus/vision/`。
- [x] 搬遷 Compliance 領域：`compliance_engine.py` 至 `src/argus/compliance/`。
- [x] 搬遷 Events 領域：`event_producer.py`, `stats_logger.py`, `diagnostic_collector.py`, `retention_cleaner.py` 至 `src/argus/events/`。
- [x] 搬遷 Integration 領域：`failover_ums_client.py`, `model_sync.py`, `state_poller.py`, `issue_service_client.py`, `report_issue.py`, `ums_config.py` 至 `src/argus/integration/`。
- [x] 搬遷 Web 領域：`web_ui.py` 至 `src/argus/web/`。
- [x] 全面更新模組間的 import 語法為 `from argus.<domain> import ...`。
- [x] 保留根目錄相容轉發層（shims），使現有呼叫仍能運作。

## Answer
1. **領域模組搬遷**：
   - `core`: `config_manager.py` 至 `src/argus/core/config_manager.py`，入口主程式置於 `src/argus/main.py`，並以 `src/argus/core/main.py` 提供轉發 re-export。
   - `capture`: `stream_handler.py`, `video_handler.py`, `grid_composer.py` 搬遷至 `src/argus/capture/`。
   - `vision`: `inference_engine.py` 搬遷至 `src/argus/vision/`。
   - `compliance`: `compliance_engine.py` 搬遷至 `src/argus/compliance/`。
   - `events`: `event_producer.py`, `stats_logger.py`, `diagnostic_collector.py`, `retention_cleaner.py` 搬遷至 `src/argus/events/`。
   - `integration`: `failover_ums_client.py`, `model_sync.py`, `state_poller.py`, `issue_service_client.py`, `report_issue.py`, `ums_config.py` 搬遷至 `src/argus/integration/`。
   - `web`: `web_ui.py` 搬遷至 `src/argus/web/`，並加入 `template_folder` 動態退避支援（優先載入套件內 `templates/`，後備根目錄 `templates/`）。
2. **標準 `argus.*` 命名空間匯入**：
   - 全量修改各領域模組內部互相引用，如 `from argus.core.config_manager import ...`、`from argus.capture.stream_handler import ...` 等。
3. **過渡期相容轉發墊片（Shims）**：
   - 根目錄保留 18 個對應 Python 模組作為轉發墊片，採用 `sys.modules[__name__] = _target` 機制，確保全域變數修改（例如 `web_ui.LATEST_FRAME`）與符號匯入無縫相容。
   - 保留 `main.py` 與 `report_issue.py` 的 CLI 直行入口。
4. **驗證結果**：
   - 全套 272 項測試在不改動測試程式碼情況下全數綠燈通過。
   - CLI 與模組呼叫（`python main.py -r --help`、`python -m argus.main -r --help`）運作正常。
