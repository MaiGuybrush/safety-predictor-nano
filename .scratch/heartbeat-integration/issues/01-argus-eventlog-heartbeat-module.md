# Issue 01: argus-eventlog Heartbeat 模組與 Camera ID 匯出

**Role:** ready-for-agent

**What to build:**
在 `C:\projects\innolux\argus-eventlog` 新增 `src/argus_eventlog/heartbeat.py`，並於 `__init__.py` 匯出 `HeartbeatService`, `start_heartbeat`, `parse_camera_id`。版本號提升至 `0.1.2`。

**Acceptance criteria:**
- [x] `src/argus_eventlog/heartbeat.py` 實作完整的 `HeartbeatService` 與 `start_heartbeat`。
- [x] 支援 `agent.yaml` 讀取與 `[8080, 8082~8090]` 候選埠自動探測。
- [x] `parse_camera_id` 正常解析 query string (`?src=cam-xxx`) 與 path (`/cam-xxx`)。
- [x] `pyproject.toml` 版本號更新為 `0.1.2`。
- [x] `argus-eventlog` 新增 `tests/test_heartbeat.py` 單元測試並全數通過。
