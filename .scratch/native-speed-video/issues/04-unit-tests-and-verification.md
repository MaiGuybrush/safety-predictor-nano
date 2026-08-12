# 04 — 自動化單元測試與動態熱重載驗證

**What to build:**
建立 `tests/test_video_handler.py` 單元測試套件，驗證 Thread-Safe 快取、模擬 `VideoCapture` 讀取與 EOF 倒帶循環，確保全套單元測試 100% 通過。

**Blocked by:** 03-main-orchestration-integration.md

**Status:** completed

- [x] 撰寫 `test_update_and_get_detections` 驗證 Thread-Safe 拷貝隔離
- [x] 撰寫 `test_video_play_loop` 模擬背景讀取與停止邏輯
- [x] 執行 `python -m unittest discover tests` 全套測試通過
