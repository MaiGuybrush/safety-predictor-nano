# ADR-015：導入 `argus-agent` Heartbeat 登錄與 RTSP URL Camera ID 自動解析

| 欄位 | 內容 |
|------|------|
| **狀態** | 已接受 (Accepted) |
| **日期** | 2026-08-16 |
| **決策者** | 開發團隊 |
| **相關 ADR** | [ADR-006](ADR-006-per-stream-model-assignment.md)、[ADR-008](ADR-008-round-robin-inference-scheduling.md)、[ADR-014](ADR-014-argus-eventlog-integration.md) |
| **相關 Spec** | [heartbeat-integration/spec.md](../../.scratch/heartbeat-integration/spec.md) |

---

## 情境與問題

1. **AP 在線狀態與事件路徑登錄**：Argus 系統要求所有廠區邊緣運行的 AI AP 需定期向本機 `argus-agent` 的 Local API (`/api/ai-ap/heartbeat`) 發送 Heartbeat，讓 agent 自動記錄並每 5 分鐘統一上報至中央 `argus-api`。先前 safety-predictor-nano 已支援輸出 ARGUS JSONL 事件（ADR-014），但尚未導入 Heartbeat 服務向 agent 註冊其 `apName`、`instance`、`cameraId` 及 `eventOutputPath`。
2. **Camera ID 自動解析**：先前 ADR-014 採 `camera_id = cfg.get("camera_id") or label or f"stream{idx}"`，無法自動從標準 Argus RTSP 串流路徑（如 `rtsp://.../cam-0eb40kwvs74z` 或 `?src=cam-0eb40kwvs74z`）中提取 `cam-` 識別碼，需要人工在 `config.yaml` 每條 stream 手動填寫 `camera_id`。

---

## 決策選項與決策

### 1. Heartbeat 模組歸屬：放入共用套件 `argus-eventlog`

**決策：** 在 `argus-eventlog` 套件中新增 `src/argus_eventlog/heartbeat.py`，匯出 `HeartbeatService` 與 `start_heartbeat` 輔助函式，版本號升級至 `0.1.2`。`safety-predictor-nano` 直接 `from argus_eventlog import HeartbeatService`。

**理由：** 與 `argus-eventlog` 零依賴/共用事件標準的理念一致。Heartbeat 規格（探測候選埠 8080, 8082~8090、讀取 `agent.yaml`、背景執行緒定期回報、失敗不中斷主流程）是所有 Argus AI AP 的通用規範，抽成共用模組可讓其他消費專案（如 AIVision_GUI、HOP 等）直接複用，避免各自重複實作造成行為分歧。

### 2. 多串流 Heartbeat 回報拓撲：Per-stream 獨立註冊

**決策：** 每個啟用中的 RTSP 串流（或 video）獨立註冊一個 Heartbeat 實例：
- `apName`: 來自 `config.yaml` 的 `heartbeat.ap_name`（預設 `"SafetyNano"`）
- `instance`: 該串流解析後的 `camera_id`
- `cameraId`: 該串流解析後的 `camera_id`
- `version`: 來自 `config.yaml` 的 `heartbeat.version`（預設 `"0.1.0"`）
- `eventOutputPath`: 該串流對應的事件目錄（`<base_dir>/<camera_id>/events`）

**理由：** Argus agent 以 `apName + instance` 為唯一識別鍵，並透過 `eventOutputPath` 定位特定鏡頭的事件日誌。若整個 process 僅回報單一 heartbeat，agent 與中央系統無法得知該裝置上各獨立鏡頭的事件目錄與鏡頭對應狀態。Per-stream 回報讓每條串流在 Argus 系統上具有完整的可觀察性與事件歸檔能力。

### 3. Camera ID 解析優先序（Fallback Chain）

**決策：** 統一解析優先順序：
1. `config.yaml` 明確設定的 `camera_id`
2. 從 RTSP URL 萃取出的 `cam-xxx`（支援路徑 `/cam-xxx` 與 query 參數 `?src=cam-xxx`）
3. `config.yaml` 的 `label`
4. 最終保底：RTSP 模式為 `f"stream{idx}"`，Video 模式為 `"video"`

**理由：** 既保持使用者在 config 中顯式指定的最高覆寫權力，又能在未填寫時無縫自動識別標準 Argus RTSP URL 格式，減少手動設定負擔，同時保留 `label` 與 `stream{idx}` 保底避免衝突。

### 4. 設定檔結構設計

**決策：** `config.yaml` 增加 `heartbeat` 設定區塊：
```yaml
heartbeat:
  enabled: true
  ap_name: SafetyNano
  interval_seconds: 60
  version: 0.1.0
  # agent_port: 8080  # 選填，若未指定則自動探測
```

**理由：** 集中且清晰地管理 Heartbeat 相關行為，支援啟用/停用開關、自訂 AP 名稱、回報頻率與版本號，方便維運調整。

### 5. 生命週期與熱重載管理

**決策：** 由 `main.py` 統一管理 Heartbeat 服務列表 `heartbeat_services: list[HeartbeatService]`。在開機與 `config.yaml` 熱重載時，先停止舊的 Heartbeat 服務，再為當前串流啟動新的 Heartbeat 服務；程式中斷退出（`KeyboardInterrupt`）時統一調用 `stop()`。

**理由：** 與現有 `StreamHandler`、`VideoHandler` 的熱重載與優雅停機生命週期完全對齊，確保串流增減時 heartbeat 狀態即時同步，不留孤兒背景執行緒。

---

## 影響與驗證

1. **向下相容性**：若未配置 `heartbeat:` 區段，系統自動使用預設值啟用；若環境無 `argus-agent` 或網路中斷，Heartbeat 背景回報失敗僅記錄 log，絕不影響即時推論與串流主流程。
2. **測試覆蓋**：
   - `argus-eventlog`：新增 `tests/test_heartbeat.py`，測試 `HeartbeatService` 的 payload 構建、自動探測機制與重試邏輯。
   - `safety-predictor-nano`：更新 `test_config_manager.py` 驗證 URL 解析優先序，新增整合測試驗證開機與熱重載時 Heartbeat 正確啟動與停止。
