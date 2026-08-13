# 02 — Background Inference Thread & SSE Feed Endpoint

**What to build:** 在 RTSP 模式下啟動獨立的背景推論執行緒（daemon thread），以 Round-Robin 方式持續對各路串流執行 YOLO 物件偵測，並將結果包含串流標籤與原始畫面尺寸寫入全域 `web_ui.LATEST_DETECTIONS`。同時在 `web_ui.py` 新增 `/detections_feed` 端點，以 Server-Sent Events (SSE) 格式將有更新的偵測結果推送至瀏覽器。

**Blocked by:** 01 — 需要伺服器端解耦與端點基礎結構確立。

**Status:** ready-for-agent

- [ ] `main.py` 新增背景推論執行緒 `_inference_worker()`，以獨立迴圈執行 Round-Robin 推論，完全不阻塞主 Relay 迴圈。
- [ ] 推論結果寫入全域字典 `web_ui.LATEST_DETECTIONS`，包含 `stream_url`, `stream_index`, `label`, `detections`, `frame_w`, `frame_h`, `ts` 欄位。
- [ ] 熱重載（更新 `config.yaml`）時，推論執行緒能透過引用動態更新串流列表，不產生競爭或死鎖。
- [ ] `web_ui.py` 新增 `/detections_feed` 路由，回傳 `mimetype='text/event-stream'`，以 ~20Hz 頻率檢查並推送 JSON 格式的偵測事件。
- [ ] 撰寫單元測試 `test_sse_detections.py`，驗證 `LATEST_DETECTIONS` 結構與 `/detections_feed` SSE 端點輸出格式。
- [ ] 開啟瀏覽器 DevTools Network 頁籤，確認 `/detections_feed` 建立 `text/event-stream` 連線並持續收到事件。
