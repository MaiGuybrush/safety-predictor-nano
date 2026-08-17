# Spec: Web UI Argus Agent 串流 Camera ID 自動帶入與不一致警告 (Web UI Argus Camera ID Auto-fill & Mismatch Warning)

## Problem Statement

在 Argus 系統架構中，當影像來源為 Argus Agent RTSP 串流（URL 中含有 `cam-xxx` 格式之標識，例如 `rtsp://127.0.0.1:8554/cam-0eb40kwvs74z` 或 `http://.../api/stream?src=cam-0eb40kwvs74z`）時，後端心跳（Heartbeat）與事件回報（EventLog）機制高度依賴 `camera_id` 與 URL 中定義的鏡頭識別碼完全一致。

然而在目前 Web UI 的 Master-Detail 設定介面中：
1. **需手動輸入 `camera_id`**：使用者輸入或貼上 Argus Agent 串流 URL 後，仍需人工手動在「鏡頭識別碼 (CAMERA_ID)」欄位鍵入相同的 `cam-xxx`，造成重複操作與輸入錯誤的風險。
2. **缺乏防呆與不一致警示**：若使用者自行修改 `camera_id` 為其他名稱（如 `CCD1` 或任意字串），Web UI 目前未提供任何警告提示。當使用者儲存並部署時，將直接導致後端事件日誌與 Argus 平台/Agent 串接異常。

## Solution

在 Web UI 串流設定介面（Stream Detail Inspector）中導入 **Argus URL 智慧解析、自動填入與一致性防呆警示機制**：
1. **即時 URL 格式解析 (`parseArgusCameraId`)**：
   前端在使用者輸入或變更串流 URL 時，即時依循與後端完全一致的規則（檢查 URL Path 或 Query 參數是否包含 `cam-` 開頭之標識）解析出 `cam-xxx`。
2. **智慧自動帶入 (Smart Auto-fill)**：
   - 當 URL 符合 Argus Agent 格式時，若目前 `camera_id` 為空、或等於先前系統自動解析值，系統自動帶入解析出之 `camera_id`。
   - 若使用者在輸入框中清空 `camera_id`，視為重設，自動重新帶入解析出之 `camera_id`。
3. **即時不一致警示與一鍵還原 (Live Warning & One-click Restore)**：
   - 若 URL 為 Argus Agent 來源，但 `camera_id` 欄位被使用者修改為與解析值不一致之文字，即時在該欄位下方顯示警示訊息：
     `⚠ 警告：若 RTSP 來源為 Argus Agent，修改 camera_id 會導致與 Argus 系統串接異常 (預期: cam-xxx)`
   - 警示區塊內附帶 `[ 還原為 cam-xxx ]` 快捷按鈕，點擊可一鍵將欄位內容復原為正確的 `camera_id` 並解除警告。
4. **載入與切換串流即時校驗**：
   在頁面初次載入或使用者在 Master 清單切換選取不同串流時，立即執行一致性檢驗，若既有儲存之設定不一致亦會立即呈現警示。

## User Stories

1. As a 廠區維運人員, I want 在串流 URL 輸入框貼上 Argus Agent RTSP URL（例如 `rtsp://10.54.10.140:8554/cam-0eb40kwvs74z`）時, so that 系統自動在「鏡頭識別碼 (CAMERA_ID)」欄位填入 `cam-0eb40kwvs74z`，節省手動輸入時間並避免打錯。
2. As a 廠區維運人員, I want 在使用 HTTP query 形式的 Argus 串流（例如 `http://10.54.10.140:8080/api/stream?src=cam-999`）時, so that 系統也能正確解析並自動填入 `cam-999`。
3. As a 廠區維運人員, I want 在輸入一般 RTSP 串流（例如 `rtsp://192.168.1.100/live/ch0`）時, so that 系統不強制帶入 `cam-` 前綴，維持由使用者自由填寫自訂標籤或 ID。
4. As a 廠區維運人員, I want 在當前串流來源為 Argus Agent 時，若我不小心修改了 `camera_id` 為其他名稱（如 `Door_Camera`）, so that 欄位下方能立刻出現醒目的橘黃色警告訊息，提醒我此修改會導致與 Argus 系統串接異常。
5. As a 廠區維運人員, I want 在看到警告訊息時能點擊旁邊的 `[ 還原為 cam-xxx ]` 按鈕, so that 能一鍵將 `camera_id` 復原為 URL 所屬的正確 ID 並消除警告。
6. As a 廠區維運人員, I want 在清空 `camera_id` 欄位文字時, so that 系統自動重新幫我補回 URL 的 `cam-xxx`，不需要重新剪貼 URL。
7. As a 廠區維運人員, I want 在從左側 Master 清單點選切換不同攝影機串流時, so that 右側編輯器立刻反映該串流的 `camera_id` 是否與其 URL 一致，若有不一致立即提示。
8. As a 廠區維運人員, I want 在頁面初次載入既有 `config.yaml` 時, so that 若過去儲存的設定檔中存在不一致的 `camera_id`，在開啟該串流時能被清楚標記警告。
9. As a 系統管理者, I want 前端在送出表單更新 `config.yaml` 時, so that 無論使用者是否自訂 `camera_id`，均能完整被序列化並正確儲存。

## Implementation Decisions

### 1. 前端 URL 解析演算法 (`parseArgusCameraId`)

- 在前端 JavaScript 中實作與後端 Python `_parse_camera_id` 行為一致之解析函式：
  - 檢查字串是否為有效 URL（含 `://`）。
  - 分解 Path 區段：若有任何路徑區段以 `cam-` 開頭（例如 `/live/cam-0eb40kwvs74z` 或 `/cam-123`），提取該區段字串。
  - 分解 Query 參數：若任何 Query 參數值以 `cam-` 開頭（例如 `?src=cam-0eb40kwvs74z`），提取該參數值。
  - 若皆未命中則回傳 `null`。

### 2. 串流資料結構與狀態追蹤

- 在前端 `streamsList` 每一筆串流物件中，記錄當前 `url`、`label`、`camera_id` 以及上次由系統自動帶入的 `auto_camera_id`。
- 當 URL 變更（`onDetailFieldChange('url', val)`）時：
  - 計算 `parsedCam = parseArgusCameraId(val)`。
  - 若 `parsedCam` 存在：
    - 若當前 `camera_id` 為空、或等於 `auto_camera_id`：自動設定 `camera_id = parsedCam`、`auto_camera_id = parsedCam`，並更新輸入框內容。
    - 若當前 `camera_id` 為非空且使用者已修改（`camera_id !== parsedCam`）：保留使用者自訂值，不覆蓋。
  - 呼叫 `validateCameraIdConsistency()` 刷新警告狀態。

### 3. `camera_id` 欄位輸入與還原事件

- 當使用者在 `camera_id` 輸入框鍵入（`onDetailFieldChange('camera_id', val)`）時：
  - 呼叫 `validateCameraIdConsistency()` 檢驗。
- 當使用者在 `camera_id` 輸入框失焦或清空時（`onDetailCameraIdBlur()`）：
  - 若值為空白且 URL 具備 `parsedCam`，自動填回 `parsedCam` 並更新狀態。
- 提供 `restoreCameraId()` 方法：
  - 將輸入框與資料物件之 `camera_id` 設定為 `parsedCam`，並隱藏警告。

### 4. UI 警示元素與樣式設計

- 在 Stream Detail Inspector 的 `detail-input-camid` 容器下方新增專屬警示區塊：
  - ID：`detail-camid-warning`
  - 預設 `display: none`。
  - 觸發警告時顯示橘黃色字體（`color: var(--warn, #ffaa00)`）與邊框背景（`border: 1px dashed var(--warn); background: rgba(255, 170, 0, 0.08); padding: 0.4rem 0.6rem; margin-top: 0.4rem;`）。
  - 內含警告文字：`⚠ 警告：若 RTSP 來源為 Argus Agent，修改 camera_id 會導致與 Argus 系統串接異常 (解析來源: <span id="detail-expected-camid"></span>)`
  - 內含還原按鈕：`<button type="button" class="stream-btn" style="border-color: var(--warn); color: var(--warn);" onclick="restoreArgusCameraId()">[ 還原為預設 ID ]</button>`

### 5. 切換串流與初始載入檢驗

- 在 `selectStream(idx)` 載入串流資料至右側 Detail Inspector 後，呼叫 `validateCameraIdConsistency()` 即時更新警告狀態。

## Testing Decisions

- **測試原則**：
  - 測試聚焦於外部可觀察之行為（HTML 樣式與結構完整性、端點輸入與儲存一致性、解析邊界條件覆蓋）。
- **測試模組與項目**：
  1. `test_web_ui_config_save.py`：
     - 測試首頁 HTML 渲染包含 `detail-camid-warning` 警示容器、`restoreArgusCameraId` 關聯標籤。
     - 測試包含 Argus URL 及自訂/自動帶入 `camera_id` 的 payload 能正確儲存至 `config.yaml`。
  2. `test_config_manager.py`：
     - 確認既有後端 `parse_camera_id` 優先序測試全數通過（Explicit `camera_id` > URL 解析 `cam-xxx` > `label` > `stream{idx}`）。
  3. 全套既有單元測試（67+ 測試項目）回歸驗證。

## Out of Scope

- 強制在後端拒絕儲存不一致的 `camera_id`（維持使用者自訂彈性，僅於 Web UI 提供防呆提示與一鍵修正）。
- 自動修改 RTSP 串流伺服器端之 stream mount point 名稱。

## Further Notes

- UI 警告視覺風格嚴格依循現有 Argus 終端工控介面色彩規範（`--warn: #ffaa00`、`--border: #003b00`）。
- 保持輕量與零額外網路請求，前端解析直接由 JavaScript 完成，保證流暢輸入體驗。
