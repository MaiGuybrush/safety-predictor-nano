Status: done

# 05 — main.py 整合：EventWriterService 生命週期 + 兩模式共用 producer 呼叫

**What to build:** 把 04 的 `event_producer` 接進既有的 RTSP round-robin worker 跟 video 模式主迴圈，並管理全域唯一的 `EventWriterService`。

**Blocked by:** 01（bugfix 後才能安全共用單一實例）、02（camera_id/severity/tolerance 設定）、04（`event_producer` 核心）

- [x] 檔頭設定 `argus_eventlog.writer.DEFAULT_PROG = "SafetyNano"`
- [x] `main()` 開頭建立唯一一個 `EventWriterService()` 並 `start()`；`KeyboardInterrupt` 分支 `stop()`；不隨 config 熱重載重建
- [x] 抽出共用函式 `format_detections(raw_detections) -> list[dict]`，取代 RTSP worker 跟 video 主迴圈裡兩份重複的格式化程式碼，兩處都改呼叫這個函式
- [x] `build_stream_units()` 依 fallback 鏈（`camera_id` → `label` → `f"stream{idx}"`）把每個 unit 的 `camera_id` 存進 `unit["camera_id"]`
- [x] RTSP worker：格式化完後呼叫 `event_producer.process_detections(unit_idx, unit.get("camera_id", "unknown"), formatted, w, h, config.get("event_severity", {}), config.get("event_absence_tolerance", 2))`
- [x] video 模式主迴圈：`camera_id = config.get("camera_id") or "video"`，同樣呼叫 `event_producer.process_detections("video", camera_id, formatted, w, h, ...)`
- [x] `requirements.txt` 新增 `-e C:\projects\innolux\argus-eventlog`
- [x] `test_engine_cache.py` 既有測試跑過（`pytest` 全綠），`camera_id` 欄位不影響既有斷言（該測試不做 dict 全等比對）

## Comments

- 實作於本次 `/grill-me` session。
