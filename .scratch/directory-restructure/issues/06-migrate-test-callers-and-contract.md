# 06 — 測試與工具鏈調用點更新並刪除舊相容墊片 (Migrate Test Callers & Contract)

Gitea Issue: #73
Type: task
Status: resolved
Blocked by: 05

## Question
如何更新 `tests/` 下所有測試與 `scripts/` 工具呼叫直接匯入 `argus.*` 領域模組，並在確認無相依後安全刪除根目錄轉發墊片？

## Tasks
- [x] 更新 `tests/unit/`, `tests/integration/`, `tests/e2e/` 中的所有 import 語法為 `from argus.<domain> import ...`。
- [x] 更新 `scripts/generate_screenshots.py` 與其他工具腳本的 import。
- [x] 移除根目錄所有過渡期轉發墊片檔案。
- [x] 於根目錄建立標準薄入口 `main.py`（轉發至 `argus.main.main`）。
- [x] 執行全套 `pytest` 測試確認全數 272+ 個測試綠燈通過。

## Answer
1. **測試匯入與 Mock 目標全量遷移至 `argus.*`**:
   - 全量掃描並轉換 41 個測試與守護檔案（包含 `tests/conftest.py`、`tests/unit/`、`tests/integration/`、`tests/e2e/`）。
   - 包含靜態 `from/import` 語法轉換（如 `from argus.core.config_manager import ConfigManager`、`from argus.web import web_ui`）。
   - 包含動態字串與 patch 目標重構（如 `patch('argus.web.web_ui.load_config')`、`patch('argus.main.model_sync')`、`patch('argus.vision.inference_engine.YOLO')` 等），杜絕相容墊片移除後的隱形 Import/Attribute 錯誤。
2. **工具鏈腳本對齊**:
   - `scripts/generate_screenshots.py`: 模板路徑優先解析 `src/argus/web/templates/`。
   - `scripts/ask_and_report.bat` & `scripts/ask_and_report.sh`: 將直接呼叫 `report_issue.py` 升級為標準薄入口 CLI 命令 `python main.py --report-issue`，保持跨平台一致性。
3. **安全刪除根目錄 17 個過渡期相容墊片**:
   - 移除了 `compliance_engine.py`, `config_manager.py`, `diagnostic_collector.py`, `event_producer.py`, `failover_ums_client.py`, `grid_composer.py`, `inference_engine.py`, `issue_service_client.py`, `model_sync.py`, `report_issue.py`, `retention_cleaner.py`, `state_poller.py`, `stats_logger.py`, `stream_handler.py`, `ums_config.py`, `video_handler.py`, `web_ui.py`。
4. **根目錄標準薄入口**:
   - 根目錄保留乾淨的 `main.py`，作為 PyInstaller 單一二進位打包與 CLI 執行的標準薄入口，內部轉發至 `argus.main.main` 與 `argus.integration.report_issue.run_cli`。
5. **測試驗證**:
   - 在無任何根目錄墊片的情況下，全套 272 個測試（單元、整合、E2E）全數綠燈通過，耗時 50.60 秒。
