# 01 — 本地影片解耦處理器 (VideoHandler) 核心實作

**What to build:**
建立專屬的 `VideoHandler` 類別，實現背景 Daemon 執行緒讀取影片檔案、解析影片原始 FPS (`CAP_PROP_FPS`)、動態計算時間補償維持 1.0x 原速播放，以及 Thread-Safe 的檢測框快取更新機制。

**Blocked by:** None — can start immediately

**Status:** completed

- [x] 新增 `VideoHandler` 類別並實現 `start()` 與 `stop()` 執行緒生命週期管理
- [x] 讀取影片檔原始 FPS (`CAP_PROP_FPS`)，實作 `frame_interval - elapsed` 動態時間補償
- [x] 實作 `update_detections()` 與 `get_latest_detections()` 並以 `threading.Lock` 確保 Thread-Safety
- [x] 實作 EOF 自動倒帶循環播放 (`CAP_PROP_POS_FRAMES = 0`)
