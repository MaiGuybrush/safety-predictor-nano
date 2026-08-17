# 01 — 修復 RTSP 動態重載 MODEL_INFO 型別錯誤與 StreamHandler 重連資源釋放

**What to build:**
修復當使用者在 Web UI 更新串流或模型設定時，後端 `main.py` 在動態重載分支中因 `engine_cache` key 為 `(model_path, model_format)` tuple 而導致 `", ".join(list(engine_cache.keys()))` 拋出 `TypeError` 造成主迴圈崩潰的問題。同時在 `StreamHandler._capture_frames` 中加入 `cap.release()` 與安全的 URL query 參數拼接，確保重連與動態切換時不會發生連線資源洩漏。

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] 修復 `main.py` 動態更新設定時 `engine_cache` key 解構（比照 `initialize_runtime` 解析 tuple 第一個元素並去重）。
- [x] 強化 `stream_handler.py` 在 `not cap.isOpened()` 時執行 `cap.release()` 釋放前次失敗 Handle。
- [x] 修正 `stream_handler.py` 中 `_open_capture` 的 `?buffer_size` 參數拼接邏輯，避免破壞已有 query 參數之 URL。
- [x] 新增動態更新測試案例，確保 hot-reload 流程能順暢執行不崩潰。

## Answer
已修復 `main.py:380` 在動態重載時解構 `engine_cache` tuple key，並在 `stream_handler.py` 強化 `cap.release()` 與 query delimiter，新增 `test_engine_cache.py` 迴歸測試（88/88 passed）。
