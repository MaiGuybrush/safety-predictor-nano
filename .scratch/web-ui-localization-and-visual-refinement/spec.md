# Spec: Web UI 說明文字中文化與去中括號視覺強調優化 (Web UI Chinese Localization & Visual Accent Polish)

## Problem Statement

在目前 Argus Safety Predictor Nano 的 Web UI 控制面板中，許多章節標題、表單欄位與操作按鈕普遍採用「中英雙語並存」、「中括號包覆」以及「程式碼註解雙斜線」的樣式（例如 `[ 01 // 推論效能參數 (PERFORMANCE) ]`、`[ TOGGLE_CONFIG ]`、`[ 本地檔案 LOCAL ]`、`[ EXECUTE_UPDATE ]`、`信心度門檻 (CONF_THRESHOLD)` 等）。

這種表現方式存在以下問題：
1. **閱讀視覺干擾過重**：大量使用的方括號 `[`、`]` 與雙斜線 `//` 造成介面符號雜亂，降低了文字的可讀性與專業工控介面的清爽度。
2. **中英文夾雜不一致**：欄位標籤與按鈕同時存在中文與大寫英文，未進行系統性整理，影響操作直覺。
3. **缺乏現代化結構視覺層次**：各設定區塊僅依靠括號作為標題區隔，缺乏更直覺的視覺引導（如飾條、序號徽章等）。

在後續雙語切換（i18n）功能正式推出前，亟需將現有介面全面統一為道地的繁體中文，消除中括號干擾，並以更現代化、科技感的樣式進行重點強調。

## Solution

全面重構 Web UI 前端模板（`templates/index.html`）中的靜態文案、按鈕、標籤與動態 JavaScript 狀態字串，達成乾淨繁體中文化與視覺風格升級：

1. **章節標題視覺強調升級**：
   - 徹底移除 `[ 01 // ... ]` 等中括號與雙斜線。
   - 採用 **左側發光邊條（Accent Border）** 搭配 **獨立數字圓角徽章（Badge）**（如 `01`、`02`、`03`、`04`）強化視覺階層感與結構清晰度。
2. **全站按鈕與控制項去括號與繁體中文化**：
   - 面板切換與模型同步按鈕：`[ TOGGLE_CONFIG ]` ➔ `切換面板`、`[ SYNC_MODELS ]` ➔ `同步模型`。
   - 來源與模式選擇：`[ 本地檔案 LOCAL ]` ➔ `本地檔案`、`[ UMS 雲端同步 UMS_SYNC ]` ➔ `UMS 雲端同步`、`+ 新增串流 ADD_STREAM` ➔ `+ 新增串流`。
   - 表單送出：`[ EXECUTE_UPDATE ]` ➔ `儲存並套用設定`。
   - 全螢幕與 ROI 編輯器：按鈕全面消除括號並改為乾淨中文（如 `編輯警戒區`、`封閉多邊形`、`清除區域`、`儲存警戒區`、`關閉全螢幕 ✕`）。
3. **表單欄位標籤精簡**：
   - 移除欄位後綴之冗餘大寫英文（例如 `(MODEL_PATH)` ➔ `模型檔案路徑`、`(CONF_THRESHOLD)` ➔ `信心度門檻`、`(ENABLED)` ➔ `啟用心跳服務`）。
   - 保留產業標準技術縮寫（如 `FPS`、`CPU`、`RTSP`、`UMS`、`ONNX`、`NCNN`、`ROI`、`API Key` 等），避免生硬直譯。
4. **即時狀態與動態文字本地化**：
   - 頂部狀態列：`MODEL` ➔ `模型`、`PATH` ➔ `路徑`、`CORES` ➔ `核心數`。
   - 影像標籤：`● LIVE_FEED` ➔ `● 即時影像`、`● VIDEO_FILE_FEED` ➔ `● 影片來源`。
   - 警戒區狀態：`[ ROI: INACTIVE ]` ➔ `警戒區：未設定`、`[ ROI: ACTIVE ]` ➔ `警戒區：已啟用`、`[ ZONE: ALARM TRIGGERED ]` ➔ `警戒區：觸發告警`。

## User Stories

1. As a 廠區維運人員, I want 瀏覽系統設定面板時看到清晰的中文章節標題（如「01 推論效能參數」）搭配發光飾條與圓角徽章, so that 我能快速識別各個設定區塊且不被方括號與斜線符號干擾。
2. As a 廠區維運人員, I want 在全域模型來源區塊看到簡潔的「本地檔案」與「UMS 雲端同步」選項按鈕, so that 我能一目了然目前所選取的模型載入模式。
3. As a 廠區維運人員, I want 表單欄位標題精簡為純中文（如「信心度門檻」、「模型檔案路徑」）, so that 介面排版更緊湊整齊，不再充斥重複的英文大寫代碼。
4. As a 廠區維運人員, I want 核心技術縮寫（如 FPS、CPU、RTSP、UMS、ONNX、NCNN、ROI、API Key）維持標準英文表示, so that 符合工控與 AI 領域習慣，易於理解無溝通歧義。
5. As a 廠區維運人員, I want 頂部狀態列顯示「模型」、「路徑」、「核心數」等中文名稱, so that 我能快速掌握目前背景推論引擎的運行狀態。
6. As a 廠區維運人員, I want 點擊「儲存並套用設定」按鈕時, so that 表單能精確送出所有配置並維持底層參數欄位名稱不變。
7. As a 廠區維運人員, I want 串流清單與監控列使用「串流 #0」、「串流 #1」等中文標籤, so that 多路鏡頭編號更符合中文使用習慣。
8. As a 廠區維運人員, I want 在串流詳細設定（Stream Detail Inspector）中看到清爽的中文控制項, so that 我能輕鬆設定鏡頭 URL、畫面標籤、鏡頭識別碼與獨立模型覆蓋選項。
9. As a 廠區維運人員, I want 在展開進階系統參數時看到清楚的「UMS API 連線設定 (多端點備援)」、「心跳回報代理 (Heartbeat)」與「事件與日誌記錄」子區塊, so that 進階設定層次分明。
10. As a 廠區維運人員, I want 在開啟全螢幕視窗進行 ROI 警戒區繪製時，看到「編輯警戒區」、「封閉多邊形」、「清除區域」、「儲存警戒區」等明確動作按鈕, so that 警戒區域操作流程順暢直觀。
11. As a 廠區維運人員, I want 警戒區狀態徽章在即時影像與詳細面板上明確顯示「警戒區：未設定」、「警戒區：已啟用」或「警戒區：觸發告警」, so that 我能即時掌握入侵告警與區域生效情形。
12. As a 系統開發者, I want 前端文案與 CSS 樣式結構模組化, so that 未來擴充多國語系／雙語切換（i18n）時能快速掛載字典。

## Implementation Decisions

### 1. 樣式結構與 CSS Class 規範
- 新增/優化 `.section-title`、`.section-badge`、`.section-title-left` 樣式：
  - 透過 `border-left: 3px solid var(--text)`（以及 cyan 區塊的 `var(--cyan)`）提供左側發光飾條。
  - 使用 `.section-badge` 樣式包覆兩位數序號（如 `01`、`02`、`03`、`04`），具備半透明背景與邊框。
- 面板框線標題 `.panel-frame-title` 移除中括號，改為 `系統參數設定`。
- 串流詳細面板標題移除中括號，改為 `串流詳細設定`。

### 2. 靜態文案與標籤替換對照表
- **面板控制按鈕**：
  - `[ TOGGLE_CONFIG ]` ➔ `切換面板`
  - `[ SYNC_MODELS ]` ➔ `同步模型`
  - `[ EXECUTE_UPDATE ]` ➔ `儲存並套用設定`
- **模型來源**：
  - `[ 本地檔案 LOCAL ]` ➔ `本地檔案`
  - `[ UMS 雲端同步 UMS_SYNC ]` ➔ `UMS 雲端同步`
- **串流與預覽操作**：
  - `+ 新增串流 ADD_STREAM` ➔ `+ 新增串流`
  - `[ 全螢幕檢視 FULLSCREEN ↗ ]` ➔ `全螢幕檢視 ↗`
  - `[ 全螢幕 / 編輯 ROI 區域 ]` ➔ `全螢幕 / 編輯警戒區 (ROI)`
  - `[ STREAM #${idx} ]` ➔ `串流 #${idx}`
- **全螢幕 ROI 編輯控制項**：
  - `[ 編輯區域 EDIT_ZONE ]` ➔ `編輯警戒區`
  - `[ 封閉 CLOSE ]` ➔ `封閉多邊形`
  - `[ 清除 CLEAR ]` ➔ `清除區域`
  - `[ 儲存 SAVE ]` ➔ `儲存警戒區`
  - `[ 取消 CANCEL ]` ➔ `取消`
  - `[ EXIT_FULLSCREEN ✕ ]` ➔ `關閉全螢幕 ✕`
  - `ZONE_NAME` placeholder ➔ `警戒區域名稱 (選填)`
  - `中心點 (Center)` ➔ `物件中心點 (Center)`
  - `相交重疊 (Intersect)` ➔ `邊界框相交重疊 (Intersect)`
  - `敏感度:` ➔ `重疊敏感度:`
- **表單欄位標籤精簡**：
  - 移除多餘後綴：`(CONF_THRESHOLD)`、`(MODEL_PATH)`、`(PROJECT)`、`(MODEL)`、`(VERSION)`、`(MODEL_FORMAT)`、`(MODE)`、`(VIDEO_PATH)`、`(FAB PRESETS)`、`(UMS_BASE_URLS)`、`(ENABLED)`、`(SEC)`、`(LABEL)`、`(CAMERA_ID)`、`(OVERRIDE_MODEL)`、`(RESOLVED MODEL)` 等。

### 3. JavaScript 動態更新文字本地化
- 更新 `templates/index.html` 內所有以 JS 動態產生或替換之 textContent / innerText：
  - `sync-status` 狀態文字
  - `preview-stream-title`、`detail-stream-badge`
  - `detail-zone-status`、`zone-status-badge`
  - `modal-title`
  - Canvas 繪圖中的 ROI 標籤與狀態提示

### 4. 保持後端資料傳輸與 Form Field Names 相容性
- 所有 HTML 表單元素之 `name` 與 `id` 屬性（如 `fps_limit`、`cpu_cores`、`conf_threshold`、`model_source`、`model_path`、`ums_model_name`、`ums_model_version`、`model_format`、`mode`、`video_path`、`streams_json`、`ums_base_urls`、`ums_api_key`、`heartbeat_*`、`event_absence_tolerance` 等）嚴格保持不變，確保後端 `web_ui.py` 與 `config_manager.py` 存取相容性為 100%。

## Testing Decisions

- **測試原則**：
  - 聚焦於外部可觀察之使用者介面行為與端對端設定持久化，不破壞既有 API 與 DOM ID。
- **測試模組與 Seams**：
  1. **Seam 1: Web UI 模板渲染與元素驗證 (`test_web_ui_config_save.py`)**：
     - 驗證 `GET /` 回傳包含中文化標題、`.section-badge` 序號徽章、去中括號之按鈕文字。
     - 驗證所有表單控制項 ID 與事件監聽（如 `selectStream`、`applyFabPreset`、`restoreArgusCameraId` 等）均正確存在。
  2. **Seam 2: 表單送出與設定持久化驗證 (`test_web_ui_config_save.py`)**：
     - 驗證中文化後的表單在使用者點擊「儲存並套用設定」時，POST payload 仍能精確被後端解析並寫入 `config.yaml`。
  3. **Seam 3: 全螢幕 ROI 告警與畫布功能驗證 (`test_web_ui_fullscreen_alarm.py`)**：
     - 驗證全螢幕 Modal 畫布與狀態徽章正常運作，幾何運算與動態告警文字相容。
  4. **全套既有單元測試（87+ 測試項目）全數通過**。

## Out of Scope

- 多語系（i18n）動態字典切換選單（此功能後續獨立階段實作）。
- 後端日誌格式與檔案名稱之結構性變更。

## Further Notes

- 整體配色嚴格遵循 Argus 賽博龐克/終端工控介面色彩系統（綠色 `#00ff41`、青色 `#00e5ff`、警告橘黃 `#ffaa00`、危險紅色 `#ff3333`、深黑背景 `#050505`）。
