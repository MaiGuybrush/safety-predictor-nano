Status: ready-for-agent

# PRD: UMS API 多端點備援設定與無感容錯切換 (Failover)

**專案**：Argus Safety Predictor Nano  
**狀態**：Ready for Agent  
**標籤**：`ready-for-agent`, `ums`, `failover`, `web-ui`, `resilience`

---

## Problem Statement

Argus Safety Predictor Nano 目前僅支援單一 `ums_base_url` 連線端點。在工廠與企業生產網路環境（如 OA、FAB 1、FAB 3、FAB 6、FAB 7、FAB 8、FAB T6、FAB TS1、FAB T1、FAB T2、FAB T3 等廠區），UMS API Proxy 伺服器均部署有主備雙端點（`src1` 與 `src2`）以提供高可用性。

當主要代理伺服器（Primary Endpoint）因網路偶發性中斷、主機重開機維護、或代理伺服器回傳 5xx 錯誤時，邊緣裝置（如 Raspberry Pi 5）會直接遭遇連線失敗，無法取得模型清單或同步最新模型權重，且無法自動切換至備援端點（Backup Endpoint）。此外，現有 Web UI 進階設定僅提供單一輸入框，現場維運工程師無法直接挑選廠區快捷設定，也無法在 UI 上直觀設定多組端點並檢視各端點的獨立連線狀態。

---

## Solution

在系統中導入 UMS 多端點設定架構與透明請求層級容錯機制（Request-time Failover）：

1. **設定檔支援多端點清單**：`config.yaml` 支援 `ums_base_urls: [url1, url2, ...]` 清單格式，同時完全向下相容舊有單一字串 `ums_base_url` 與環境變數 `UMS_BASE_URL`。
2. **無感容錯切換客戶端 (`FailoverUmsClient`)**：建立相容 `UmsApiClient` 介面的代理封裝類別，在 API 呼叫（模型清單獲取、權重檔案下載、健康度測試）時依序嘗試可用端點。遇逾時（5~10 秒）或 5xx 錯誤時自動透明切換至次一備援端點，並記錄記憶當前有效之 Active 端點。
3. **Web UI 廠區快捷選單與動態端點管理**：
   - 提供「廠區/網段快捷選單」，選取廠區（如 FAB 1、FAB 3、OA 等）後自動帶入該廠區專屬的 `src1` 與 `src2` 端點。
   - 提供動態增刪與排序多組端點輸入框。
   - 「測試連線」端點依序檢測所有配置的端點，並在 UI 上清晰回傳各端點的個別連線狀態與取得之模型數。
4. **完整說明文件同步**：更新使用者操作手冊，提供清晰的多端點配置導引與廠區 URL 對照說明。

---

## User Stories

1. 作為現場維運工程師，我希望在 `config.yaml` 中配置多組 UMS 代理伺服器端點（`ums_base_urls`），以便主要端點故障時系統能自動連線備援端點。
2. 作為現場維運工程師，我希望若既有設定檔仍使用舊版單一 `ums_base_url` 字串，系統能自動相容並正常運作，以便無痛升級。
3. 作為現場維運工程師，我希望在 Web UI 上可以透過下拉選單直接選取設備所在的廠區（例如 FAB 1、FAB 3、OA 等），以便系統自動帶入該廠區對應的主備 UMS 端點，省去手動輸入長網址的時間與打錯風險。
4. 作為現場維運工程師，我希望在 Web UI 可以自由新增、修改與刪除自訂的備援 UMS 端點，以便因應非預設廠區或臨時測試代理伺服器的需求。
5. 作為現場維運工程師，我希望在 Web UI 點擊「[ 測試連線 ]」時，系統能同時/依序檢測所有配置的端點，並清楚標示各端點的連線狀態（如 `src1: 成功`、`src2: 連線逾時`），以便我排查現場網路狀況。
6. 作為現場維運工程師，我希望在模型同步或日常運作時，若主要端點斷線，系統能在背後無感自動切換至備援端點完成模型下載，以便邊緣推論服務不受單點網路故障影響。
7. 作為現場維運工程師，我希望系統在發生備援端點切換時能在日誌記錄警告訊息，以便追蹤與排查主要伺服器的連線異常。
8. 作為系統開發者，我希望所有多端點切換與重試邏輯統一封裝在專案內部的 `FailoverUmsClient` 中，以便 `model_sync.py` 與 `web_ui.py` 呼叫時保持乾淨且不依賴外部套件改動。
9. 作為系統開發者，我希望在單一端點連線逾時（Timeout）時能迅速嘗試下一組端點，避免過長等待阻礙開機流程或 UI 互動反應。
10. 作為系統管理員，我希望透過環境變數 `UMS_BASE_URL` 設定以逗號分隔的多組端點時，系統亦能正確解析為備援端點清單。
11. 作為操作手冊讀者，我希望在快速上手指南與系統設定章節中能查閱到多端點備援配置方式與廠區 URL 對照表，以便正確操作介面。

---

## Implementation Decisions

### 1. 組態結構與相容層設計 (`config_manager.py` & `config.yaml`)
- `config.yaml` 引入 `ums_base_urls: list[str]` 欄位：
  ```yaml
  ums_base_urls:
    - "http://10.26.11.108/umsapiproxy/fab4ums"  # src1
    - "http://10.26.11.109/umsapiproxy/fab4ums"  # src2
  ums_api_key: "ums_xxxxxxxxxxxxxxxx"
  ```
- `ConfigManager.get_ums_base_urls()` 統一提供標準化 URL 清單：
  1. 優先檢查環境變數 `UMS_BASE_URL`（支援逗號分隔或單一 URL）。
  2. 若無，檢查 `config.yaml` 中的 `ums_base_urls`（列表）。
  3. 若無，檢查舊版 `ums_base_url`（字串）並轉為單元素列表。
  4. 若皆無，Fallback 至預設 OA 端點清單。
- `save_config()` 儲存時，將 Web UI 傳入的多組端點序列化為 `ums_base_urls` 清單寫入。

### 2. 封裝 `FailoverUmsClient` 模組
- 建立封裝類別，介面完整實作 `UmsApiClient` 常用方法：
  - `fetch_my_models()`
  - `download_version(version_id, dest_dir)`
  - `test_connection(timeout)`
- **容錯重試機制**：
  - 內部維護 `base_urls` 陣列與當前 `active_index`。
  - 單次呼叫嘗試當前端點，若拋出連線異常（如 `ConnectionError`、`Timeout`、HTTP 5xx 等），自動記錄 Warning log 並依序嘗試下一組端點。
  - 當某一備援端點成功回應時，更新 `active_index` 記憶為後續優先端點。
  - 若所有端點皆嘗試失敗，拋出彙整錯誤訊息（包含所有端點的失敗原因）。

### 3. Web UI 廠區預設選單與動態表單 (`templates/index.html`)
- 在「進階系統參數」中新增「廠區預設快速選單 (FAB PRESETS)」：
  - 包含 OA 辦公網段、FAB 1、FAB 3、FAB 6、FAB 7、FAB 8、FAB T6、FAB TS1、FAB T1、FAB T2、FAB T3。
  - 選取後自動動態替換並渲染對應的 `ums_base_urls` 輸入框。
- 動態端點清單介面：
  - 每列包含端點輸入框與刪除按鈕。
  - 提供 `「+ 新增備援端點」` 按鈕。
- 測試連線反饋：
  - 呼叫 `/api/ums/test_connection`，後端回傳包含 `endpoints: [{url, status, models_count, error}]` 的詳細測試結果。
  - UI 分別以狀態徽章（Badge/Label）呈現每個端點的獨立檢測結果。

### 4. 後端 API 端點擴充 (`web_ui.py`)
- `/api/ums/test_connection` (POST)：
  - 支援接收 `base_urls: list[str]` 或 `base_url: str`。
  - 逐一測試各端點連線能力，回傳整體狀態與個別端點詳細結果。
- `/api/ums/models` (GET)：
  - 改用 `FailoverUmsClient`，具備跨端點自動容錯擷取專案與模型結構。

### 5. 模型同步模組適配 (`model_sync.py`)
- `sync_all()` 建立 client 時改用 `FailoverUmsClient`，於開機同步及手動觸發同步時均具備透明容錯能力。

---

## Testing Decisions

### 測試原則
- **黑盒行為測試為主**：專注於驗證外部可觀察行為（設定解析、容錯切換順序、API 回傳結構、設定檔寫回），不綁定內部私有變數。
- **網路異常模擬**：透過 Mock / 假 Client 模擬主要端點 Timeout/500 與備援端點 200 OK 之情境，驗證容錯切換是否無痛完成且回報正確。

### 受測模組與測試項目
1. **`test_config_manager.py`**：
   - 驗證 `ums_base_urls` 列表之讀取與寫回。
   - 驗證舊版 `ums_base_url` 單一字串之向下相容轉換。
   - 驗證環境變數 `UMS_BASE_URL` 逗號分隔多端點解析。
2. **`test_model_sync.py`**：
   - 驗證 `FailoverUmsClient` 在主要端點失敗時自動切換至備援端點並成功下載模型。
   - 驗證所有端點皆失敗時正確收集失敗錯誤日誌而不中斷主迴圈。
3. **`test_web_ui_ums_endpoints.py`**：
   - 驗證 `/api/ums/test_connection` 傳入多端點時能回傳個別端點的檢測報告。
   - 驗證 `/api/ums/models` 在主要端點失效時仍能順利回傳模型清單。
4. **`test_web_ui_config_save.py`**：
   - 驗證 Web UI 提交多組 `ums_base_urls` 時，`config.yaml` 格式正確保留且不破壞其他欄位。

### 參考先例 (Prior Art)
- `test_web_ui_ums_endpoints.py`
- `test_model_sync.py`
- `test_config_manager.py`

---

## Out of Scope

- UMS 平台端 API Proxy 的伺服器端配置與負載平衡器架構變更（僅處理邊緣設備端之客戶端切換）。
- 動態 DNS 負載平衡（由廠區現有 IP / 網址架構提供）。
- 離線模型的增量二進位差分同步（目前由 UMS Client 完整下載 artifact 處理）。

---

## Further Notes

- 廠區端點 URL 對照依據 [01-quick-start.md](file:///D:/Projects/argus/safty-predictor-nano/docs/user-manual/src/01-quick-start.md) 表格定義，系統預設以清單形式內建於前端與設定範例中。
