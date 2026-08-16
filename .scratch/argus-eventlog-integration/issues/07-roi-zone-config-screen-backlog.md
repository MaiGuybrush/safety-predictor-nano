Status: ready-for-agent

# 07 — ROI / 危險區域設定畫面

**What to build:** 目前 `EventMeta.roi`（spec 必填欄位）用整張畫面當 placeholder（`[[0,0],[1,0],[1,1],[0,1]]`），因為專案完全沒有 ROI / 危險區域的概念（純物件偵測，`config.yaml` 沒有 zone schema，Web UI 沒有畫框介面）。

本次 `/grill-me` 已把設計定案，細節見下方「設計定案」。

**Blocked by:** None，但依賴性質上獨立、範疇夠大，不併進 `argus-eventlog-integration` 這次的實作範圍（見 `docs/adr/ADR-014-argus-eventlog-integration.md`「取捨與風險」段）。

## 設計定案

### 範疇 / 資料模型

- per-stream，一條 stream 最多一塊危險區域（optional，可以不設）
- key 用 stream URL 字串，不依賴 ums-client 平行進行中的 `streams[]`／`camera_id` schema（那份尚未 commit，交接文件要求先不要碰；等對方合併後再考慮把 key 換成 `camera_id`）
- `config.yaml` 新增 `zones` 頂層 key：

  ```yaml
  zones:
    "rtsp://127.0.0.1:8554/test_stream1":
      polygon: [[0.1, 0.2], [0.5, 0.2], [0.5, 0.8], [0.1, 0.8]]
      zone_name: "機台危險區"   # optional
  ```

- `polygon` 存正規化 0-1 座標，換算基準是前端 canvas 本身的 `canvas.width`/`canvas.height`（`syncCanvasSize()` 已讓 canvas 精確貼合影像顯示區域），不依賴 SSE 傳來的 `frame_w`/`frame_h`，因為沒有偵測結果時 SSE 可能沒送這兩個值

### 事件語意（`event_producer.py`）

- 限制方案：有設 `zones` 的 stream，detection bbox 中心點沒落在 zone 多邊形內就整個不觸發事件（在既有 per-label 狀態機前面加一層前置過濾，過濾掉的 detection 不進 `_state`）；中心點落在 zone 內才照現有邏輯跑，`category` 維持原本偵測到的 label，**不**強制改成 `"zone_intrusion"` 字串
- 沒設 zone 的 stream：完全維持現況（全畫面 placeholder ROI、任何偵測都觸發，行為不變）
- zone 規則對所有 class 一視同仁，不分白名單／黑名單
- `EventMeta.roi`：有 zone 就填真實座標，沒 zone 維持 `_FULL_FRAME_ROI` placeholder；`zone_name` 有填就一併帶進 `meta`

### 幾何判斷

- bbox 中心點 in polygon，用既有依賴 `cv2.pointPolygonTest`，不新增套件（cv2 已經是 `main.py`/`video_handler.py`/`stream_handler.py` 的既有依賴）

### 前端（`templates/index.html`）

- 沿用 fullscreen live-view 既有 canvas overlay（`fullscreen-canvas`／`syncCanvasSize()`／`drawCanvas()`），不另開新頁面
- 常態顯示：zone 外框跟 bbox 一起疊圖畫出來（樣式跟 bbox 區分開），純檢視模式維持 `pointer-events: none`
- 新增「編輯區域」切換按鈕：按下才切到 `pointer-events: auto`，進入點擊加點模式；再按「完成」/「儲存」/「取消」退回純檢視
- 編輯流程：點擊加點（自由多邊形，不限矩形）→「完成」封閉多邊形 →（可選填 zone 名稱文字框）→「儲存」送出；「清除」重畫
- 進編輯模式時若已有存檔 zone，先載入既有多邊形顯示，不是每次空白開始
- 無獨立 enable/disable 開關：有畫多邊形＝啟用，清除＝停用

### 後端（`web_ui.py`）

- 新增獨立小 endpoint（例如 `POST /zone/<url-encoded-stream-id>`），只讀寫 `config.yaml` 的 `zones` 這個 key，經 `ConfigManager` 局部更新；不動現有 `/` route 那支整包覆寫的大表單 handler

## Comments

- 建立於 argus-eventlog 整合 session，使用者要求把這個明確排除的範圍記錄成代辦 issue，狀態 `ready-for-human`。
- 本次針對 ROI/危險區域再跑一輪 `/grill-me`，設計定案如上，狀態改 `ready-for-agent`，可以直接進 TDD 實作（`event_producer.py`／`config_manager.py`／`web_ui.py`／`templates/index.html` 四處都會動到）。
