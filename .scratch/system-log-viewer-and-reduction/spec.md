Status: ready-for-agent

# Spec: 系統日誌導向檔案、高頻 HTTP 日誌減量與 Web UI 日誌檢視器

**關聯 PRD**：`docs/prd/system_log_viewer_and_reduction_prd.md`  
**標籤**：`ready-for-agent`, `logging`, `web-ui`, `monitoring`, `Kind/Feature`

---

## Problem Statement

目前 Argus Safety Predictor Nano 在日誌與可觀測性（Observability）上存在以下問題：

1. **終端機輸出未持久化**：系統核心事件（如開機模型同步、串流重連、心跳狀態、推論錯誤等）透過 `print()` 或模組 logger 輸出至終端機，一旦使用者以背景服務執行或關閉終端機，關鍵除錯資訊無法在檔案中查閱。
2. **模型同步失敗原因被靜默**：當使用者在 Web UI 按下「同步模型」或開機自動同步失敗時，後端 [`model_sync.py`](file:///D:/Projects/argus/safty-predictor-nano/model_sync.py) 為了隔離錯誤將例外直接裝入回傳字典，前端僅提取成功與失敗筆數顯示（如 `FAIL: 1`），且未印出任何錯誤堆疊或詳細原因，維運人員無法得知失敗根因（例如 API Key 錯誤、端點無法連線或模型不存在）。
3. **高頻 HTTP 存取日誌淹沒終端機**：Web UI 每 5 秒主動輪詢 `/model_info` 與 `/sync_status`，Flask/Werkzeug 預設以 INFO 層級輸出所有 `HTTP 200` 請求，造成終端機日誌以極高頻率刷屏，淹沒真正重要的業務日誌與警告。
4. **邊緣裝置缺乏直接查閱 Log 的 UI 管道**：在無螢幕（Headless）樹莓派環境中，現場工程師若要檢查日誌必須透過 SSH 連線並手動 cat/tail 檔案，缺乏在 Web UI 上直接快速檢視系統狀態與歷程的介面。

---

## Solution

1. **系統日誌雙軌輸出與持久化**：
   - 建立系統主日誌檔（預設 `logs/system.log`），採用雙軌輸出架構：同時輸出至終端機 Console（`stdout`）與支援每日自動輪替的日誌檔（`TimedRotatingFileHandler`），並沿用 `log_backup_count` 保留歷史記錄。
   - 後端所有模組（[`model_sync.py`](file:///D:/Projects/argus/safty-predictor-nano/model_sync.py)、[`failover_ums_client.py`](file:///D:/Projects/argus/safty-predictor-nano/failover_ums_client.py)、[`stream_handler.py`](file:///D:/Projects/argus/safty-predictor-nano/stream_handler.py)、[`main.py`](file:///D:/Projects/argus/safty-predictor-nano/main.py)）統一使用該系統 logger，確保模型同步失敗、推論異常、斷線重連等訊息皆被完整記錄。
2. **Werkzeug HTTP 日誌減量與全域日誌等級控制**：
   - 將 Flask/Werkzeug 存取日誌預設等級調整為 `WARNING`，過濾正常 `200 OK` 的高頻輪詢存取，僅在發生 `4xx`、`5xx` 或伺服器異常時記錄。
   - 在 `config.yaml` 提供全域 `log_level` 設定（支援 `DEBUG`、`INFO`、`WARNING`、`ERROR`，預設 `INFO`）。
3. **Web UI 日誌檢視器 (Log Viewer Modal)**：
   - 在 Web UI 頂部導覽列新增 `[ 日誌檢視 LOGS ]` 按鈕。
   - 點擊彈出終端機黑底風格的 Modal 檢視器，支援下拉切換日誌來源（系統主日誌 `system.log`、效能日誌 `performance.log`、偵測日誌 `detections.log`）。
   - 提供安全受控的後端讀取端點（`GET /api/logs?file=<type>&lines=200`），支援即時手動重新整理、自動捲動至底部與一鍵複製日誌。
4. **模型同步錯誤提示補強**：
   - 後端同步失敗時在日誌記錄 `[ModelSync Error]` 與具體錯誤訊息。
   - 前端同步失敗時，按鈕呈現紅色警示並附加 Title 懸停提示（Tooltip），且於瀏覽器 DevTools Console 輸出詳細錯誤資訊。

---

## User Stories

1. 作為現場維運工程師，我希望系統的所有重要事件（包含開機同步、串流狀態、心跳與推論警告）能同時輸出在終端機並自動寫入 `logs/system.log`，以便在背景執行時也能隨時追溯歷史問題。
2. 作為現場維運工程師，我希望在 `config.yaml` 中能夠自訂 `system_log_file` 路徑與全域 `log_level`（如 DEBUG/INFO/WARNING/ERROR），以便依不同環境需求調整日誌詳細度與存放位置。
3. 作為現場維運工程師，我希望系統日誌檔能跟隨 `log_backup_count` 設定進行每日自動輪替與過期刪除，以便避免邊緣裝置 SD 卡空間被日誌耗盡。
4. 作為現場維運工程師，我希望 Flask/Werkzeug 不再每 5 秒在終端機刷出 `/model_info` 與 `/sync_status` 的 `200 OK` 存取記錄，以便終端機保持清爽且重要訊息不被淹沒。
5. 作為現場維運工程師，我希望當 HTTP 請求出現 404 或 500 等異常狀態碼時，Werkzeug 仍能記錄警告或錯誤訊息，以便排查 API 故障。
6. 作為現場維運工程師，我希望在 Web UI 點擊「同步模型」若發生失敗時，能在後端 `logs/system.log` 中直接查看到具體的失敗原因（例如 API Key 錯誤、端點逾時、找不到模型），以便快速診斷。
7. 作為現場維運工程師，我希望在 Web UI 頂部工具列點擊「[ 日誌檢視 LOGS ]」時，能彈出直觀的終端機樣式視窗，直接在瀏覽器查閱最新日誌，省去使用 SSH 登入裝置下指令的時間。
8. 作為現場維運工程師，我希望在 UI 日誌檢視器中可以自由切換檢視 `system.log`、`performance.log` 與 `detections.log` 三種日誌檔，以便全方位監控系統運作。
9. 作為現場維運工程師，我希望在 UI 日誌檢視器中可以手動點擊「重新整理」取得最新 N 行內容，並可勾選「自動捲動至底部 (Auto-scroll)」，以便在觀察即時行為時自動對焦最新訊息。
10. 作為現場維運工程師，我希望在 UI 日誌檢視器提供「一鍵複製」按鈕，以便將錯誤記錄複製並回報給開發團隊。
11. 作為前端使用者，我希望當在 UI 按下「同步模型」回傳失敗（`FAIL: X`）時，按鈕能以紅色醒目顯示，並支援滑鼠懸停顯示具體錯誤摘要，以便第一時間掌握異常狀態。
12. 作為系統開發者，我希望 `/api/logs` 端點具備嚴格的白名單與路徑安全檢查，禁止任何路徑穿越（Path Traversal）攻擊，以確保系統安全性。

---

## Implementation Decisions

### 1. 系統日誌核心與雙軌架構 (`stats_logger.py` & `main.py`)
- 在 `stats_logger.py` 中擴充或建立專屬的 `SystemLogger` / 統一日誌配置器：
  - 支援從 `config.yaml` 讀取 `system_log_file`（預設 `logs/system.log`）、`log_level`（預設 `INFO`）與 `log_backup_count`（預設 `3`）。
  - 配置 `StreamHandler(sys.stdout)` 輸出至 Console，並附加 `TimedRotatingFileHandler` 寫入檔案。
  - 格式化格式：`%(asctime)s [%(levelname)s] [%(name)s] %(message)s`。
- 調降 Werkzeug 存取日誌等級：
  ```python
  import logging
  logging.getLogger('werkzeug').setLevel(logging.WARNING)
  ```
- 統整核心模組日誌輸出：
  - 在 `model_sync.py` 發生失敗時，呼叫 `logger.error(f"[ModelSync] 目標 {name} ({version}) 同步失敗: {e}")`。
  - 在 `main.py` 開機同步與推論循環中，將原本零散的 `print()` 轉換為統一日誌紀錄。

### 2. 組態管理與向下相容 (`config_manager.py` & `config.yaml.example`)
- 在 `config.yaml` 新增日誌相關欄位：
  ```yaml
  # 9. 日誌與效能記錄設定 (Logging)
  system_log_file: "logs/system.log"       # 系統主要運作與錯誤日誌路徑
  log_file: "logs/performance.log"         # CPU/RAM/推論速度效能日誌路徑
  detection_log_file: "logs/detections.log" # 物件偵測事件 Log 路徑
  log_level: "INFO"                       # 全域日誌等級: DEBUG / INFO / WARNING / ERROR
  log_interval_seconds: 60                 # 效能統計寫入間隔 (秒)
  log_backup_count: 3                      # 日誌歷史檔案保留天數
  ```
- `ConfigManager` 提供取得與安全回退方法。

### 3. 日誌讀取 API 端點 (`web_ui.py`)
- 新增 `GET /api/logs`：
  - 參數：
    - `file`: 指定日誌類型（只允許白名單：`system`、`performance`、`detections`，預設 `system`）。
    - `lines`: 欲讀取之末尾行數（整數，預設 200，上限 1000）。
  - 安全性處理：
    - 嚴格映射至 config 中對應的合法檔案路徑，禁止任何 `../` 路徑穿越。
    - 若日誌檔案尚未建立，優雅回傳空字串或初始提示訊息，不拋出 500 錯誤。
  - 回傳 JSON 格式：
    ```json
    {
      "status": "ok",
      "file_type": "system",
      "file_path": "logs/system.log",
      "lines": 200,
      "content": "2026-08-20 11:30:00 [INFO] [System] 系統啟動成功\n..."
    }
    ```

### 4. 前端 UI 日誌檢視器與錯誤提示強化 (`templates/index.html`)
- **頂部工具列按鈕**：新增 `[ 日誌檢視 LOGS ]`（點擊觸發 `openLogViewerModal()`）。
- **日誌檢視 Modal 視窗**：
  - 採用綠黑終端機電競科技風格（與既有 UI 一致）。
  - 頂部工具列：
    - 日誌來源下拉選單（`系統日誌 (system.log)`、`效能記錄 (performance.log)`、`偵測記錄 (detections.log)`）。
    - 「重新整理」按鈕與「自動捲動 (Auto-scroll)」核取方塊。
    - 「複製內容」按鈕（帶有短暫 Copied! 視覺反饋）。
    - 關閉按鈕（`✕` / `ESC` 鍵支援）。
  - 日誌文字顯示區：等寬字體（monospace）、自帶滾動條與深底色樣式。
- **模型同步按鈕回饋強化**：
  - 當 `data.failed.length > 0` 時，按鈕文字變更為紅色並設定 `title` 懸停提示第一筆錯誤訊息（例如 `title="同步失敗: 所有 UMS 端點皆連線失敗"`）。
  - 點擊失敗狀態可提示使用者點開日誌檢視器查閱完整 Log。

---

## Testing Decisions

- **良好測試原則**：
  - 專注於外部行為驗證，包含端點 HTTP 狀態碼、回傳 JSON 結構、檔案安全過濾、日誌等級抑制效果，不依賴內部臨時實作變數。
- **測試模組與涵蓋範圍**：
  1. `test_system_logger_and_reduction.py`：
     - 驗證 `SystemLogger` 正確建立 Console StreamHandler 與 TimedRotatingFileHandler。
     - 驗證 Werkzeug Logger 等級設為 WARNING。
     - 驗證 `model_sync.py` 失敗時能正確記錄 Error Log 到 Logger。
  2. `test_web_ui_logs_api.py`：
     - 驗證 `/api/logs` 端點在各合法 `file` 參數下回傳狀態與結構。
     - 驗證非法檔案參數或路徑穿越嘗試會被安全拒絕或回傳白名單內容。
     - 驗證檔案不存在時回傳空內容且不崩潰（200 OK）。
- **既有測試範例 (Prior Art)**：
  - 參考 `test_stats_logger.py`（測試 RotatingFileHandler 輪替與清理）。
  - 參考 `test_sse_detections.py` 與 `test_web_ui_ums_endpoints.py`（使用 Flask `test_client()` 測試 API 格式與安全回傳）。

---

## Out of Scope

1. 即時 WebSocket / SSE 日誌串流推送（初期採用高效率的 API 按需拉取 + 輪詢/手動重新整理，避免邊緣裝置長連線資源負擔）。
2. 在 UI 上提供日誌下載為 `.zip` 或伺服器端清空刪除日誌檔案的操作（避免現場操作人員誤刪關鍵證據日誌）。
3. 支援任意目錄結構的任意自訂日誌檔案瀏覽（嚴格限制只讀取白名單內的 3 個合法記錄檔）。

---

## Further Notes

- Raspberry Pi 5 邊緣裝置常使用 SD 卡作為儲存介質，預設 `log_level: INFO` 與調降 Werkzeug 輪詢輸出，既能保留完整排錯軌跡，又可顯著減少磁碟 I/O 與避免 Flash 壽命過度損耗。
