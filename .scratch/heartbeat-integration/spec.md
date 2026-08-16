# Spec: argus-agent Heartbeat 整合與 Camera ID 自動解析 (Heartbeat Integration)

## 概述

為滿足 Argus 監控平台對廠區 AI AP 狀態追蹤與事件定位需求，本功能導入：
1. **Heartbeat 服務**：向本機 `argus-agent` 的 Local API (`/api/ai-ap/heartbeat`) 定期登錄 AP 在線狀態、版本、鏡頭 ID 與事件 JSONL 輸出路徑。
2. **Camera ID 自動解析**：從 RTSP URL 萃取 `cam-xxx` 識別碼，依 Fallback 鏈判定每路串流的 `camera_id`。

## 詳細設計

### 1. `argus-eventlog` 套件擴充 (`v0.1.2`)
- 新增 `src/argus_eventlog/heartbeat.py`：
  - `HeartbeatService` 類別：
    - 支援 `agent.yaml` 與候選埠號探測（8080, 8082~8090）
    - 支援 `apName`, `instance`, `version`, `eventOutputPath`, `cameraId`, `interval_seconds`
    - 背景 daemon 執行緒定期 POST `/api/ai-ap/heartbeat`，啟動時立即發送一次
    - 斷線自動重試，失敗僅 log 不中斷主流程
  - `start_heartbeat()` 快速啟動函式
  - `parse_camera_id(raw)` 函式（從 `writer.py` 匯出）
- `__init__.py` 匯出 `HeartbeatService`, `start_heartbeat`, `parse_camera_id`
- `pyproject.toml` 版本更新為 `0.1.2`

### 2. `config_manager.py` Camera ID 解析
- `get_stream_configs()` 支援優先順序：
  `item.get("camera_id")` -> `parse_camera_id(url)` -> `item.get("label")` -> `f"stream{idx}"`
- video 模式：`config.get("camera_id")` -> `"video"`

### 3. `config.yaml` 新增 `heartbeat` 設定
```yaml
heartbeat:
  enabled: true
  ap_name: SafetyNano
  interval_seconds: 60
  version: 0.1.0
  # agent_port: 8080
```

### 4. `main.py` 生命週期整合
- 開機時 (`initialize_runtime` / `main`):
  - 根據 `config.get("heartbeat", {})` 與各串流（或 video）啟動 `HeartbeatService`
  - 記錄於 `heartbeat_services` 清單
- 熱重載時 (`config_mgr.check_for_updates()`):
  - 停止舊的 `heartbeat_services`
  - 重新為活躍串流啟動新的 `HeartbeatService`
- 停機時 (`KeyboardInterrupt`):
  - 停止所有 `heartbeat_services`
