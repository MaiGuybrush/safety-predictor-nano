# 01 — Server MJPEG Relay & Per-Stream Video Endpoints

**What to build:** 將 RTSP 模式下的伺服器端顯示管線改為高流暢度的 MJPEG Relay，完全停止在伺服器端執行 OpenCV 繪框標注，使主迴圈更新速率不再受 YOLO 推論時間阻塞。同時在 `web_ui.py` 新增 `/video_feed/<int:stream_id>` 端點，用於單獨轉發指定串流索引的原始 MJPEG 畫面，供全螢幕檢視使用。

**Blocked by:** None — 可立即開始。

**Status:** ready-for-agent

- [ ] `main.py` 在 RTSP 模式下的主迴圈改為純 MJPEG Relay 模式，不呼叫 `annotate_frame`，將各路原始幀進行純幀 Grid 拼接並編碼為 JPEG（品質 85），寫入 `web_ui.LATEST_FRAME`。
- [ ] `web_ui.py` 新增 `/video_feed/<int:stream_id>` 端點，當接收請求時，生成器僅轉發 `stream_units[stream_id]` 的最新原始幀（編碼品質 85）；若 `stream_id` 越界或無法取幀則回應 `NO_SIGNAL_FRAME`。
- [ ] 在 RTSP 模式下存取 `/video_feed`，瀏覽器呈現無標注的流暢畫面（≥12 FPS）。
- [ ] 存取 `/video_feed/0`、`/video_feed/1`，能獨立看到對應 RTSP 串流的原始畫面。
- [ ] 切換至本地影片（`mode: video`）模式，原有的影片播放與伺服器端標注繪框功能完全不受影響（迴歸驗證）。
