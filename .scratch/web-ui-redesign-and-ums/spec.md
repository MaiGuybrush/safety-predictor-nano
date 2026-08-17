Status: ready-for-agent

# Spec: Web UI 設定面板重整與 UMS 雲端模型動態整合 (Web UI Redesign & UMS Integration)

> 承接 `web_ui_redesign_plan.md`。整合 `ums-client` 雲端模型管理能力、重構 Web UI 設定面板的分區與動態互動邏輯，並確保 `config.yaml` 參數更新時的非破壞式寫入。

## Problem Statement

當前 Safety Predictor Nano 的 Web UI 設定面板存在以下限制與痛點：
1. **設定欄位未分群且混雜**：運作模式（RTSP 與 Video）、全域推論參數、模型路徑與多行串流輸入框平鋪於單一表單中，缺乏層級概念，使用者難以直觀區分核心設定與進階參數。
2. **缺乏 UMS 雲端模型即時瀏覽與選擇機制**：雖然底層已具備 `ums-client` 同步模組，但使用者在 Web UI 上只能手動文字輸入 `model_path` 或自行修改 `config.yaml`，無法在介面上直接瀏覽 UMS 平台的專案、模型名稱與版本並進行點選。
3. **多路 RTSP 串流以純文字 Textarea 編輯易出錯且無法設定個別屬性**：每路串流的 `label`、`camera_id`、獨立模型覆蓋（Per-stream Model / UMS Model）無法在 UI 上直觀編輯，且表單提交時容易造成每路串流的擴充屬性被重寫遺失。
4. **模式切換未與介面連動**：切換為影片驗證模式時，介面依然顯示 RTSP 串流輸入框；切換為 RTSP 模式時，依然顯示影片路徑，造成使用者認知混亂。
5. **進階系統參數（Heartbeat、UMS 連線金鑰、事件與日誌參數）缺乏介面管理**：部分核心參數仍需手動至終端機編輯 `config.yaml`。

## Solution

在 Flask Web UI 與前端介面上進行全面重構：
1. **語意化分區卡片版面**：將設定面板重整為四大區塊：全域推論效能、全域模型來源（本地/UMS）、運作模式與來源動態配置（RTSP 動態串流卡片 / 影片路徑）、以及可摺疊的進階系統參數（Heartbeat、UMS 連線設定、事件日誌）。
2. **UMS 雲端模型動態連動選單**：後端新增 API 端點連線 UMS 平台獲取模型列表，前端提供「本地檔案 / UMS 雲端」切換開關；選擇 UMS 時動態呈現「專案 (Project) ➔ 模型 (Model) ➔ 版本 (Version)」階層式下拉選單，並支援連線測試。
3. **動態多串流管理卡片**：RTSP 模式下提供結構化串流列表，支援動態「+ 新增串流 / ✕ 刪除」，並能直觀輸入 URL、標籤、鏡頭 ID 及可選的獨立模型覆蓋；切換至影片模式時平滑切換為影片檔案路徑輸入區。
4. **非破壞式 Config 持久化與自動同步**：重構設定檔更新邏輯，完整保留未編輯的欄位與既有串流物件結構。當使用者切換或變更 UMS 模型宣告並儲存時，自動於背景觸發模型同步並回報即時進度。

## User Stories

1. As a 廠區維運人員, I want 在 Web UI 上一目了然看到系統推論效能參數（FPS 限制、CPU 核心數、信心度門檻）, so that 我可以快速調整邊緣推論負載。
2. As a 廠區維運人員, I want 在 Web UI 上切換「本地檔案」與「UMS 雲端模型」兩種來源模式, so that 我可以自由決定使用裝置既有模型或由雲端下載。
3. As a 廠區維運人員, I want 選擇 UMS 模式時能依序從「專案」下拉選單選取專案、從「模型」下拉選單選取模型, so that 我不需要手動記憶並拼寫複雜的模型名稱。
4. As a 廠區維運人員, I want 在 UMS 模型版本選單中選擇 `latest (Active)` 或特定版本號, so that 我可以靈活決定要自動追蹤最新版或是固定使用特定驗證版本。
5. As a 廠區維運人員, I want 在 Web UI 切換「RTSP 多路模式」與「影片驗證模式」時，表單內容即時相應切換, so that 我不會在 RTSP 模式看到無關的影片路徑、也不會在影片模式看到 RTSP 串流列表。
6. As a 廠區維運人員, I want 在 RTSP 模式下以卡片列表方式檢視每路串流，並能動態「新增串流」或「刪除串流」, so that 我不需要手動編輯容易出錯的多行文字。
7. As a 廠區維運人員, I want 為每路 RTSP 串流設定專屬的 `label`（畫面標籤）與 `camera_id`（鏡頭識別碼）, so that 事件記錄與畫面上能明確辨識攝影機來源。
8. As a 廠區維運人員, I want 在特定 RTSP 串流上獨立覆蓋模型設定（可指定個別本地路徑或 UMS 模型）, so that 不同場景的攝影機能運行最適合的專用模型。
9. As a 廠區維運人員, I want 儲存設定時，若變更了 UMS 模型宣告，系統自動於背景觸發下載與模型熱重載, so that 我不用手動重開服務或額外點擊同步按鈕。
10. As a 廠區維運人員, I want 在頂部狀態列隨時看到最近一次模型同步的狀態（如 `OK:1 FAIL:0`）與手動 `[ SYNC_MODELS ]` 按鈕, so that 我能即時掌握雲端模型同步結果。
11. As a 廠區維運人員, I want 在進階設定中填寫並修改 UMS Base URL 與 API Key，並能點擊 `[ 測試連線 ]` 即時驗證, so that 我可以在憑證更換或網路變更時立即確認與 UMS 平台的連線狀況。
12. As a 廠區維運人員, I want 在進階設定中啟用/停用 Heartbeat 心跳服務，並設定 Agent 通訊埠與間隔時間, so that 裝置能配合現場的 Argus Agent 進行健康回報。
13. As a 廠區維運人員, I want 在進階設定中調整事件消失容忍影格數（`event_absence_tolerance`）與日誌寫入間隔, so that 我能依據現場推論取樣率優化事件邊界與效能記錄。
14. As a 系統開發者, I want Web UI 儲存表單時採用非破壞式寫入機制, so that 未包含在表單中的既有設定（如自訂 severity、未異動串流物件屬性）不會被覆蓋清除。
15. As a 系統開發者, I want UMS API 異常或斷網時前端與後端皆能優雅降級並顯示錯誤訊息, so that 介面不會發生 500 崩潰且本機模型推論不受影響。

## Implementation Decisions

### 1. Web UI 版面架構與語意分區

- 設定面板分為四大語意區塊：
  1. **全域推論效能 (Global Performance)**：`fps_limit`、`cpu_cores`、`conf_threshold`。
  2. **全域模型來源設定 (Global Model Source)**：`model_source` 切換（`local` / `ums`），包含本地 `model_path` 輸入框與 UMS 三層連動下拉選單。
  3. **運作模式與來源配置 (Mode & Source Configuration)**：
     - `mode == 'rtsp'`：動態串流列表，每項包含 `url`、`label`、`camera_id`、獨立模型覆蓋開關，以及 `+ 新增串流` 與 `✕ 刪除` 按鈕。
     - `mode == 'video'`：影片路徑 `video_path` 與 `camera_id`。
  4. **進階系統參數 (Advanced Parameters - 可摺疊收合)**：
     - UMS 連線：`ums_base_url`、`ums_api_key`、連線測試按鈕與狀態指示。
     - Heartbeat 心跳：`heartbeat.enabled`、`heartbeat.agent_port`、`heartbeat.ap_name`、`heartbeat.interval_seconds`、`heartbeat.version`。
     - 事件與日誌：`event_absence_tolerance`、`log_interval_seconds`、`log_file`、`detection_log_file`。

### 2. 後端 API 規格與職責劃分

- **`GET /api/ums/models`**：
  - 呼叫 `UmsApiClient` 取得模型清單，將清單依 `project_name` (或 `project_id`) 聚合為階層式 JSON：
    ```json
    {
      "status": "ok",
      "projects": [
        {
          "project_id": 1,
          "project_name": "廠區安全監控",
          "models": [
            {
              "model_id": 10,
              "model_name": "yolo8n",
              "architecture": "YOLOv8",
              "versions": [
                {"version_id": 101, "version_number": 1, "status": "Active", "comment": "Initial"}
              ]
            }
          ]
        }
      ]
    }
    ```
  - 異常處理：捕獲所有例外（憑證錯誤、逾時、網路不可達），回傳 `{"status": "error", "message": "..."}`，HTTP 狀態碼維持 200，防止拋出 500。
- **`POST /api/ums/test_connection`**：
  - 接收 `{"base_url": "...", "api_key": "..."}`，建立臨時 `UmsApiClient` 測試呼叫 `fetch_my_models()`，回傳 `{"status": "ok", "models_count": N}` 或 `{"status": "error", "message": "..."}`。
- **`POST /` (或 `POST /api/config`) 表單持久化**：
  - 讀取當前 `config.yaml` 作為 baseline。
  - 根據提交的資料結構更新對應欄位，保留未編輯的鍵值。
  - 對 `streams` 陣列進行比對：若 URL 存在於既有設定中，保留其既有客製化屬性；支援每項獨立設定 `model` 或 `ums_model`。
  - 若偵測到 UMS 模型設定有變動，儲存後在背景非同步執行 `model_sync.sync_all()`。

### 3. 前端動態互動機制

- **純前端即時切換（無刷新）**：
  - 監聽 `mode` 變更：即時切換 `streams-container` 與 `video-container` 的可見性。
  - 監聽 `model_source` 變更：即時切換 `local-model-box` 與 `ums-model-box` 的可見性。
- **UMS 三層下拉連動**：
  - 頁面載入時非同步請求 `/api/ums/models` 載入快取。
  - 選取 Project ➔ 觸發 Model 下拉選項重繪 ➔ 選取 Model ➔ 觸發 Version 下拉選項重繪（預設選中 `latest`）。
  - 自動回填：若既有 `config.yaml` 宣告了 `ums_model.name`，在模型清單載入後自動反查並選中對應的專案、模型與版本。
- **串流卡片動態增刪**：
  - 使用 JavaScript DOM 操作動態插入/移除串流列，序號自動重編。

## Testing Decisions

- **測試原則**：只驗證外部 API 輸出行為與設定檔讀寫結果，不依賴真實外部 UMS 伺服器連線（採用 Mock 注入手法）。
- **測試模組**：
  1. `test_web_ui_ums_endpoints.py`：
     - 測試 `GET /api/ums/models`：Mock `UmsApiClient.fetch_my_models` 回傳資料，驗證專案階層化 JSON 格式。
     - 測試 `GET /api/ums/models` 失敗情境：Mock 拋出例外，驗證回傳 `status: "error"` 且不拋 500。
     - 測試 `POST /api/ums/test_connection`：驗證連線測試成功與失敗之回應結構。
     - 測試 `POST /` 設定儲存：驗證結構化串流、UMS 宣告、進階參數寫入後 `config.yaml` 內容完整性與未動欄位保留。
  2. 現有單元測試回歸（`test_config_manager.py`、`test_sync_endpoint.py`、`test_zone_endpoint.py` 等）。
- **Prior Art**：參考 `test_sync_endpoint.py` 的 Flask `test_client()` 與 `unittest.mock.patch` 模式。

## Out of Scope

- `ums-client` 套件本身的內部實作修改。
- 影片即時上傳功能（影片驗證模式依然讀取本地檔案路徑）。
- 使用者權限與登入驗證機制（維持局域網直連管理）。

## Further Notes

- UI 視覺風格全面遵循 Argus 科技工控規範：深色背景（`#050505`）、亮綠/亮青高對比邊框（`#00ff41` / `#00e5ff`）、等寬字體與微動畫 hover 效果。
- 儲存 `config.yaml` 時確保 UTF-8 編碼與 `allow_unicode=True`，防止中文標籤亂碼。
