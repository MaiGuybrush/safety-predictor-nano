# 03 — 推論結果屬性附加與前端即時告警渲染 (SSE Detection Enrichment & Frontend Alarm)

**What to build:**
後端推論迴圈（`main.py`）在完成推論後，自動利用 `event_producer._is_inside_zone` 評估每筆偵測框是否落入/相交於目前串流之 ROI，並為每筆 detection 標記 `in_zone: true / false`。透過 SSE `/detections_feed` 將帶有 `in_zone` 的偵測結果即時推送給前端。前端全螢幕 Canvas（`drawCanvas()`）直接消費 `det.in_zone`，動態呈現紅色警示框（`#ff3333`）、`[ALARM]` 標籤、多邊形高亮與全螢幕紅色呼吸燈脈衝。

**Blocked by:** 01 — 核心幾何判定引擎與相交模式支援, 02 — 組態綱要擴充與 REST API 持久化

**Status:** resolved

- [x] `main.py` 在推論後為每筆 detection 加入 `in_zone: bool` 屬性
- [x] `web_ui.LATEST_DETECTIONS` 及 `/detections_feed` SSE payload 包含 `in_zone` 旗標
- [x] 前端 `templates/index.html` 的 `drawCanvas()` 直接讀取 `det.in_zone` 決定告警視覺樣式
- [x] 移除前端 JavaScript 重複的 Ray-Casting 幾何計算，達成 Single Source of Truth
- [x] 單元測試 `test_sse_detections.py` 與 `test_web_ui_fullscreen_alarm.py` 驗證資料流與畫布告警行為

## Answer
在 `main.py`（RTSP 與 Video 推論迴圈）中完成了 `det["in_zone"]` 幾何狀態標記與 SSE payload 封裝；在 `templates/index.html` 的 `drawCanvas()` 中改為直接讀取 `det.in_zone` 觸發全螢幕告警反饋與多邊形高亮，實現 Single Source of Truth。單元測試 `test_sse_detections.py` 與 `test_web_ui_fullscreen_alarm.py` 全數通過。
