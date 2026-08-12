# 03 — 主程式整合 VideoHandler 與非同步推論迴圈

**What to build:**
重構 `main.py` 的 `video` 模式，將原先同步阻塞的播放邏輯替換為 `VideoHandler` 驅動。主迴圈改為從 `VideoHandler` 獲取最新影格送入 YOLO 推論，並將檢測結果非同步寫回 `VideoHandler` 疊加顯示。

**Blocked by:** 01-video-handler-core.md, 02-web-ui-stream-tuning.md

**Status:** completed

- [x] 在 `main.py` 中引入並初始化 `VideoHandler`
- [x] 處理動態熱重載，當 `mode` 或 `video_path` 變更時正確重啟 `VideoHandler`
- [x] 主迴圈非同步獲取影格推論並更新 `video_handler.update_detections()`
- [x] 確保應用程式結束 (KeyboardInterrupt) 時可安全停止 `VideoHandler`
