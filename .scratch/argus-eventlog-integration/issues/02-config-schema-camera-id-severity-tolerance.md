Status: done

# 02 — Config schema：camera_id / event_severity / event_absence_tolerance

**What to build:** `config_manager.py` 新增讀取三個新的可選欄位，供 03～05 使用。

**Blocked by:** None — can start immediately

- [x] `get_stream_configs()` 回傳的每個 stream dict 新增 `"camera_id": item.get("camera_id") or ""`（`streams[]` schema 分支）；`rtsp_streams` 舊版 schema 分支固定給 `""`（該格式沒有 per-stream 欄位可放）
- [x] 全域可選欄位 `camera_id`（`mode=video` 用）、`event_severity`（`{label: severity}`）、`event_absence_tolerance`（int，預設 2）不需要新增 `ConfigManager` 方法，直接用既有 `config.get(...)` 讀（跟 `fps_limit`/`conf_threshold` 一樣的既有慣例）
- [x] `test_config_manager.py` 既有的 dict 相等斷言（`test_legacy_rtsp_streams`、`test_new_streams_schema`）補上新的 `"camera_id"` key，否則會因為回傳 dict 多一個 key 而斷言失敗
- [x] `test_new_streams_schema` 順便補了 `camera_id` 有設定時正確帶出來的斷言（`configs[0]["camera_id"] == "CCD1"`）；沒設定時為空字串（fallback 邏輯留給 05 在 `main.py::build_stream_units()` 做）

## Comments

- 實作於本次 `/grill-me` session。
