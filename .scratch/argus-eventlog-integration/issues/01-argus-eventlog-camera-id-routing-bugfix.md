Status: done

# 01 — 修 argus-eventlog：`_write()` 依 record 自己的 camera_id 路由

**What to build:** 修改外部 repo `C:\projects\innolux\argus-eventlog\src\argus_eventlog\writer.py`，讓多鏡頭單一 process 共用一個 `EventWriterService` 時，事件寫進正確的鏡頭資料夾。詳見 `docs/adr/ADR-014-argus-eventlog-integration.md` 決策 5。

**Blocked by:** None — can start immediately

- [x] `EventWriterService._write()`：`camera_id` 改成 `getattr(record, 'camera_id', None) or self.camera_id`；`ccd_no` 的動態 fallback 最後一層改成 `camera_id`（而非 `self.ccd_no`）
- [x] `pyproject.toml` 版本號 `0.1.0` → `0.1.1`；`src/argus_eventlog/__init__.py` 的 `__version__` 同步更新
- [x] `tests/test_writer.py` 新增回歸測試：單一 `EventWriterService` 實例、送兩筆不同 `camera_id` 的 record，斷言各自落在自己 `camera_id` 的資料夾（不是 service 初始化時的 `camera_id`）
- [x] 既有 `test_event_lifecycle_writes_daily_and_event_files` 測試不受影響（`pytest` 全綠，2 passed）

## Comments

- 實作於本次 `/grill-me` session，直接由同一位 agent 完成，見 ADR-014。
