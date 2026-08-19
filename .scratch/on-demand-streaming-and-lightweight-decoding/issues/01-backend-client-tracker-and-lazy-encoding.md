# 01 — 後端連線計數器與主迴圈延遲 JPEG 編碼

Type: task
Status: unclaimed
Labels: ready-for-agent, Kind/Feature

## Goal
在 `web_ui.py` 建立執行緒安全的活躍視訊客戶端計數機制，並在 `main.py` 主迴圈中實現隨選延遲編碼（Lazy JPEG Encoding），消除無人觀看時 ~100Hz 的 JPEG 壓縮與影像縮放負載。

## Details
- `web_ui.py`:
  - 建立全域計數器 `ACTIVE_VIDEO_CLIENTS` 與 Lock，提供 `is_streaming_active() -> bool`。
  - 在 `gen_frames` (Grid) 與 `gen_single_stream_frames` (單路) 進入時計數 +1，`finally:` (斷線時) 計數 -1。
- `main.py`:
  - 主迴圈檢查 `web_ui.is_streaming_active()`，若為 False 則跳過 `compose_grid` 與 `cv2.imencode`。
- 撰寫單元測試驗證連線建立/中斷時的計數器與狀態切換。
