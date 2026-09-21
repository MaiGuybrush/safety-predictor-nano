# 01 — 測試執行緒隔離與超時守護 (Pytest Teardown & Timeout Guard)

Gitea Issue: #68
Type: task
Status: resolved
Blocked by: None

## Question
如何建立或擴充 `tests/conftest.py` 與 `pytest.ini`，加入行程清理 fixture 與資源釋放機制，確保測試結束後釋放 OpenCV/Flask/背景執行緒與網路連線資源，徹底解決測試全數通過後行程在 0% CPU 懸掛未退出的問題？

## Tasks
- [x] 建立或更新 `pytest.ini`，配置標準測試參數與測試發現路徑。
- [x] 於 `tests/conftest.py` 增加 session/function 級別 teardown hook，自動清理殘留的背景執行緒、串流與連線池。
- [x] 執行 `pytest` 驗證所有測試通過後，Python 行程能立即正常結束並回傳代碼 0。

## Answer
1. **問題根因**：
   - `stream_handler.py` 中 `StreamHandler.start()` 建立之 capture 執行緒未設定 `daemon=True`。在 `test_runtime_resilience.py` 中呼叫 `build_stream_units` 啟動了 StreamHandler 但未呼叫 `stop()`，導致後續持續在 OpenCV/FFmpeg 逾時重試迴圈中運作。
   - `test_web_ui_floating_save_e2e.py` 中之 `ServerThread` 亦未標記 `daemon=True`。
   - Python 行程在 pytest 執行完成時會調用 `threading._shutdown()` 逐一 `join()` 所有非守護 (non-daemon) 執行緒，因而導致進程在 0% CPU 下無限懸掛等待。

2. **實作解決方案**：
   - 建立 `pytest.ini`，統一配置 `testpaths = . tests`、`python_files = test_*.py` 與告警過濾規則。
   - 建立 `tests/conftest.py`（與根目錄委派 `conftest.py`）：
     - `resource_teardown_guard` autouse fixture：在每個測試前後監控執行緒，清理 `web_ui.ACTIVE_VIDEO_CLIENTS`、`event_producer._state`、停止 `GLOBAL_STATE_POLLER`，並將測試期間產生的殘留子執行緒自動標註為 `daemon=True`。
     - `pytest_sessionfinish` hook：執行 `gc.collect()`，全面巡檢並確保所有子執行緒均為 daemon，並啟動 5 秒退出守護看門狗 (`PytestExitWatchdog`) 防止 native C 擴充阻塞。
   - 修正 `stream_handler.py` 與 `test_web_ui_floating_save_e2e.py` 之執行緒為 `daemon=True`，並於 `test_runtime_resilience.py` 加入 `finally: unit["handler"].stop()`。
   - 全量 272 項測試全數綠燈通過（55.52s），pytest 行程立即正常結束並回傳代碼 0。
