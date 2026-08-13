# 03 — Client Canvas Detection Bounding Box & Fullscreen UI

**What to build:** 升級 Web UI 前端視訊顯示區塊，點擊 Grid 中的任一路影像即可開啟全螢幕覆蓋層（Modal），影像切換至獨立端點 `/video_feed/<stream_id>`，並開啟 SSE (`EventSource`) 連線訂閱 `/detections_feed`。前端使用 HTML5 `<canvas>` 依真實影像與顯示比例即時計算座標，繪製綠線標籤偵測框；點擊全螢幕任意位置即可關閉回到 Grid 概覽視圖。

**Blocked by:** 01, 02 — 需要單路影像端點與 SSE 偵測事件頻道就緒。

**Status:** ready-for-agent

- [ ] `templates/index.html` 新增全螢幕覆蓋層 Modal（CSS `position: fixed; z-index: 9999`），內含 `<img id="fullscreen-img">` 與絕對定位的 `<canvas id="fullscreen-canvas">`。
- [ ] 點擊 Grid 中的影像會觸發全螢幕 Modal 開啟，動態將 `fullscreen-img` 的 `src` 設為 `/video_feed/<stream_id>`。
- [ ] JavaScript 建立 `EventSource('/detections_feed')` 連線，監聽並解析 SSE 事件 JSON 資料。
- [ ] JavaScript 依據 `img.clientWidth` / `img.clientHeight` 與 SSE 中的 `frame_w` / `frame_h` 計算縮放率，於 `<canvas>` 上繪製綠線矩形框與黑底標籤（類別 ID + 信心度）。
- [ ] 點擊全螢幕覆蓋層任意處即可關閉 Modal 並恢復原本視圖。
- [ ] 手動驗證：RTSP 模式下點擊單路開啟全螢幕，畫面流暢且標注框精確對齊目標物體；切換至 video 模式，功能無異常。
