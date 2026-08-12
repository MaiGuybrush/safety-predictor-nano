# 02 — Web UI 串流產生器頻率調優

**What to build:**
將 `web_ui.py` 中的 MJPEG 串流產生間隔由 `0.1s` 調降至 `0.03s`，解除 10 FPS 發送限制，支援更高影格率（最高 ~33 FPS）的畫面流暢輸出。

**Blocked by:** None — can start immediately

**Status:** completed

- [x] 修改 `web_ui.py` 中 `gen_frames()` 的 `time.sleep` 間隔至 `0.03` 秒
- [x] 確保 `/video_feed` 串流輸出順暢無延遲
