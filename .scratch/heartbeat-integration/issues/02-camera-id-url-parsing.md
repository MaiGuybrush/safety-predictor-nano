# Issue 02: ConfigManager Camera ID 自動解析與優先序

**Role:** ready-for-agent

**What to build:**
更新 `safety-predictor-nano/config_manager.py` 的 `get_stream_configs()` 方法，引入 `parse_camera_id`，依據優先序（Explicit `camera_id` > URL 解析 `cam-xxx` > `label` > `f"stream{idx}"`）指派每條串流的 `camera_id`。

**Acceptance criteria:**
- [x] 若 config 未指定 `camera_id` 但 RTSP URL 包含 `cam-xxx`，自動解析為 `camera_id`。
- [x] 若 config 明確指定 `camera_id`，即使 URL 另有 `cam-xxx`，仍以 config 為準。
- [x] 若皆無，則依序使用 `label` 與 `stream{idx}`。
- [x] `test_config_manager.py` 測試覆蓋所有解析分支。
