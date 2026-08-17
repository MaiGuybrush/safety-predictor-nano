# Effort: RTSP Hot-Reload Crash Fix & Stream Reconnection Protection

## Notes
修復動態重載時 `engine_cache` tuple key 引發的 `TypeError` 主程序崩潰，並強化 `StreamHandler` 重連資源釋放。

## Decisions so far
- 合併為單一 Ticket，完整覆蓋從 `main.py` 型別修復、`stream_handler.py` 資源釋放到回歸測試。

## Map
- [01-fix-hot-reload-and-stream-reconnect.md](file:///D:/Projects/argus/safty-predictor-nano/.scratch/rtsp-hot-reload-fix/issues/01-fix-hot-reload-and-stream-reconnect.md)
