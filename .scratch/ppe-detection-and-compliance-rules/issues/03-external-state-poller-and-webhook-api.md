# Issue 03: External State Poller & Webhook API

Type: task
Status: resolved
Blocked by: 01

## Description
實作外部狀態同步機制：
1. **`state_poller.py`**：
   - 建立 Daemon 輪詢執行緒，依配置週期性發送 HTTP GET 請求至 MES/PLC API。
   - 支援解析 JSON 巢狀路徑（如 `data.status`）。
   - 逾時與連線異常時自動套用 `fallback_value`。
   - 維護全域執行緒安全快取 `CURRENT_EXTERNAL_STATES`。
2. **`web_ui.py` REST API**：
   - 開放 `POST /api/external_state` 接收外部系統主動推送（支援 TTL）。
   - 開放 `GET /api/compliance_status` 供外部查詢當前狀態。

## Acceptance Criteria
- 輪詢過程異常不影響推論主流程。
- Webhook 接收狀態後即刻更新快取。
- 完成單元測試 `test_state_poller.py`。

## Answer
已完成 `state_poller.py` 模組實作與 `web_ui.py` REST API 端點串接：
1. **`StatePoller` 核心模組**：
   - 背景 Daemon 輪詢執行緒，依配置週期發送 HTTP GET 請求。
   - 支援 `extract_json_path` 點分隔多層巢狀 JSON 解析（如 `data.equipment.0.status`）。
   - 異常平滑降級：連線失敗或逾時自動套用 `fallback_value`，不中斷主程式。
   - 執行緒安全快取與 TTL 逾期清除機制。
2. **Web UI REST API 端點**：
   - `POST /api/external_state`：支援外部 Webhook 即刻推送狀態並附帶 `ttl_seconds`。
   - `GET /api/compliance_status`：提供外部查詢目前所有設備狀態快照與合規總覽。
3. **測試驗證**：
   - 新增 `tests/test_state_poller.py`，完整測試 JSON Path 解析、記憶體快取與 TTL、網路異常降級及 Flask API 端點；全專案單元測試全數 PASS。
