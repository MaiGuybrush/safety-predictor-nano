# Spec: ROI 觸發模式擴充 (Intersect 模式與 Sensitivity 參數，集中後端判定架構)

## Problem Statement

目前 Argus Safety Predictor Nano 在判定偵測物件（如人員、設備）是否進入 ROI 多邊形警戒區時，面臨兩大核心限制：

1. **判定規則缺乏彈性與提早預警能力**：
   - 目前系統僅支援單一的「偵測框中心點（Center Point）判定」。在平視或斜角監控視角下，當人員的肢體或堆高機的車身、貨叉剛穿過警戒邊界時，只要中心點仍在區域外，系統便不會發出警報，造成防護盲區與反應延遲。
   - 無法針對不同危險等級的區域配置靈敏度（Sensitivity / Overlap Ratio）門檻，無法滿足「高危險區一碰邊界就報警」或「一般管制區重疊達到特定比例才報警」的現場客製化需求。
2. **前後端分散計算的架構風險**：
   - 先前前端全螢幕畫布自行在 JavaScript 端重複實作 Ray-Casting 幾何判定，容易因前後端演算法與浮點數精度微小差異導致「前端亮紅框但後端沒告警」或「後端發了事件日誌但前端畫布沒亮紅框」的不一致問題，且增加了低效能終端設備的運算負擔。

## Solution

採用**後端集中判定（Single Source of Truth）**與**即時熱生效（Hot Reload）**架構，全面擴充 ROI 區域入侵判定機制：

1. **支援多種觸發模式 (`trigger_mode`)**：
   - `center`（預設值，向後完全相容）：偵測框中心點落入多邊形內時觸發。
   - `intersect`（相交/重疊模式）：偵測框與多邊形產生幾何交集時觸發。
2. **支援敏感度參數 (`sensitivity`)**：
   - 數值範圍 `0.0` ~ `1.0`（預設 `0.0`）。
   - 在 `intersect` 模式下，`sensitivity` 代表「重疊面積佔偵測框面積的最小比例門檻」（Overlap Ratio = $\frac{\text{Area}(\text{Bbox} \cap \text{ROI})}{\text{Area}(\text{Bbox})}$）：
     - `sensitivity = 0.0`：只要偵測框任一頂點、邊線或局部與 ROI 多邊形相交（重疊面積 $> 0$），即刻判定為入侵（最敏感、提早預警）。
     - `sensitivity > 0.0`（如 `0.3`）：需有 $30\%$ 以上目標面積進入 ROI 才判定為入侵。
3. **後端集中計算與前端輕量化（Zero-Duplication Architecture）**：
   - 後端推論迴圈在推論完成後，利用既有 OpenCV 底層高效能幾何運算完成 `trigger_mode` 與 `sensitivity` 判定。
   - 判定結果作為布林旗標 `in_zone: true / false` 直接附加在每筆偵測資料中，透過 SSE `/detections_feed` 即時推送到瀏覽器。
   - 前端 Web UI Canvas 不需重複實作複雜的多邊形相交運算，直接讀取 `det.in_zone` 進行紅綠框切換與多邊形動態高亮，確保**視覺呈現與事件日誌 100% 同步**。
4. **即時熱重載生效（Hot Reload Apply）**：
   - 使用者在 Web UI 儲存 ROI 後，設定即時原子化寫入 `config.yaml`，後端主迴圈與推論執行緒在下一次推論抽樣時（< 0.2 秒）立即套用新設定，無需重啟服務。

## User Stories

1. As a safety manager, I want the system to support an `intersect` trigger mode for high-hazard zones, so that an intrusion alarm is fired the instant any part of a worker's bounding box touches the boundary.
2. As a site operator, I want to configure a `sensitivity` threshold (from 0.0 to 1.0) for the `intersect` mode, so that I can fine-tune between rapid early alarms and false-alarm prevention.
3. As a monitoring technician, I want to keep existing camera zones running in `center` mode by default, so that current operational behavior is not broken when upgrading.
4. As a safety operator watching fullscreen camera view, I want all detection boxes to reflect backend `in_zone` decisions instantly (turning danger red with `[ALARM]` tags) without client-side calculation discrepancy.
5. As a safety operator watching fullscreen camera view, I want the ROI polygon itself to dynamically illuminate in translucent red with `[ ROI: <NAME> - INTRUSION ]` whenever any detection has `in_zone: true`.
6. As an administrator editing camera zones in Web UI, I want to select the trigger mode (`center` vs `intersect`) and adjust sensitivity in the ROI edit panel, with changes applying immediately upon clicking Save.
7. As a backend event consumer, I want `EventStart` and `EventFrame` events to be generated immediately upon boundary intersection in `intersect` mode, so that external alarm systems receive low-latency alerts.
8. As a site technician, when I set `sensitivity = 0.0` in `intersect` mode, I want the system to alert even if only a tiny corner or edge of the bounding box enters the polygon.
9. As a site technician, when I set `sensitivity = 0.5` in `intersect` mode, I want the system to suppress alerts until at least half of the object's bounding box area is inside the danger zone.
10. As a monitoring technician, I want streams without any configured ROI zones to remain unaffected and continue normal detection processing without extra performance overhead.
11. As a low-power client browser user (e.g. tablet or thin client), I want the client not to run heavy geometric intersection math in JavaScript, ensuring smooth 60fps canvas rendering.
12. As a developer, I want all zone API endpoints (`GET /zone/<stream_url>` and `POST /zone/<stream_url>`) to return and accept `trigger_mode` and `sensitivity` fields with sensible defaults.

## Implementation Decisions

### 1. Configuration & Data Schema (`config_manager.py` & `config.yaml`)
- `config.yaml` 中的 `zones` 結構擴充：
  ```yaml
  zones:
    rtsp://127.0.0.1:8554/cam1:
      polygon:
        - [0.2, 0.2]
        - [0.8, 0.2]
        - [0.8, 0.8]
        - [0.2, 0.8]
      zone_name: "機台危險區"
      trigger_mode: "intersect"   # "center" (default) | "intersect"
      sensitivity: 0.0            # float: 0.0 ~ 1.0 (default 0.0)
  ```
- `config_manager.py` 的 `save_zone` 方法增加 `trigger_mode="center"` 與 `sensitivity=0.0` 參數，若未提供則使用預設值。

### 2. Backend Intrusion Evaluation & Enrichment (`event_producer.py` & `main.py`)
- **判定核心 (`event_producer.py`)**：
  - 擴充 `_is_inside_zone(det, polygon, frame_w, frame_h, trigger_mode="center", sensitivity=0.0)`。
  - 當 `trigger_mode == "center"`：保持原 `cv2.pointPolygonTest` 判定中心點。
  - 當 `trigger_mode == "intersect"`：
    - 將偵測框轉換為 OpenCV 多邊形頂點 `[[x1, y1], [x2, y1], [x2, y2], [x1, y2]]`。
    - 使用 OpenCV `cv2.intersectConvexConvex` 或凸多邊形/多邊形裁剪算法計算相交多邊形與面積。
    - 若相交面積 $> 0$ 且 $\frac{\text{相交面積}}{\text{偵測框面積}} \ge \text{sensitivity}$，判定為 True。
- **偵測結果屬性附加 (`main.py`)**：
  - 在主推論迴圈完成 YOLO 推論與格式化後，為每筆偵測結果賦予 `det["in_zone"] = _is_inside_zone(...)`。
  - 推入全域 `web_ui.LATEST_DETECTIONS`，供 SSE `/detections_feed` 廣播至所有前端客戶端。

### 3. SSE Protocol & Frontend Client Rendering (`web_ui.py` & `templates/index.html`)
- **SSE Payload 格式**：
  ```json
  {
    "0": {
      "stream_url": "rtsp://127.0.0.1:8554/cam1",
      "detections": [
        {
          "xyxy": [120, 200, 240, 400],
          "conf": 0.88,
          "label": "person",
          "in_zone": true
        }
      ],
      "frame_w": 1920,
      "frame_h": 1080,
      "ts": 1724040000.123
    }
  }
  ```
- **前端畫布渲染 (`drawCanvas()`)**：
  - 前端移除 client 端幾何重複判定，直接以 `det.in_zone === true` 作為告警狀態依據。
  - 若任一可見物件的 `det.in_zone === true`，啟動 `[ALARM]` 紅色標籤、多邊形半透明紅色高亮與全螢幕外框呼吸燈。

### 4. REST API Contract & UI Controls
- `GET /zone/<stream_url>`：回傳包含 `polygon`, `zone_name`, `trigger_mode`, `sensitivity` 的 JSON 物件。
- `POST /zone/<stream_url>`：接收並儲存包含 `trigger_mode` 與 `sensitivity` 的 JSON 負載。
- 在 Web UI 的全螢幕 ROI 劃設面板與右側 Detail 檢查器中加入：
  - **觸發模式下拉選單**：`[ 中心點判定 (Center) ]` / `[ 邊界相交判定 (Intersect) ]`。
  - **敏感度調整滑桿**：提供 0% ~ 100%（即 0.0 ~ 1.0）設定滑桿與即時數值標籤（在 Intersect 模式下啟用）。

## Testing Decisions

- **Good Test Criteria**: 測試著重於外部可觀察行為（物件進入、邊緣相交、部分重疊時是否觸發告警事件、SSE payload 中的 `in_zone` 欄位正確性、API 回傳與設定檔保存），不綁定內部私有變數。
- **Seams**:
  1. **Seam 1: `event_producer.process_detections` 整合測試**
     - 測試在 `center` 模式下，中心點在外但邊緣重疊時不產生事件。
     - 測試在 `intersect` 模式且 `sensitivity=0.0` 下，邊緣剛碰觸多邊形時立即產生 `EventStart`。
     - 測試在 `intersect` 模式且 `sensitivity=0.5` 下，重疊面積小於 50% 時不觸發、大於等於 50% 時觸發。
  2. **Seam 2: `main.py` 推論輸出與 SSE `LATEST_DETECTIONS` 測試**
     - 測試推論後產生的每筆 detection 均正確包含 `in_zone: True/False` 布林屬性。
  3. **Seam 3: `web_ui` `/zone/<stream_url>` API 與 `config_manager` 測試**
     - 測試 `GET` 與 `POST` 正確傳遞並持久化 `trigger_mode` 與 `sensitivity`。
  4. **Seam 4: 前端 HTML 模板與控制項驗證 (`test_web_ui_fullscreen_alarm.py`)**
     - 測試前端模板包含觸發模式與靈敏度控制項，並驗證 `drawCanvas` 正確消費 `det.in_zone` 旗標。

## Out of Scope

- 多個 ROI 區域之間的布林邏輯組合（如 Zone A AND Zone B）。
- 基於物體歷史軌跡與運動向量的動態提早預報（如 1 秒後預測碰撞）。
- 多邊形之間的凹多邊形複雜鏤空扣除（Donut Polygons）。

## Further Notes

- 所有預設值（`trigger_mode="center"`, `sensitivity=0.0`）均確保與現有配置完全相容，既有部署升級後不會產生任何行為漂移。
