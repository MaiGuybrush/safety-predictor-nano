# Issue 03: config.yaml 與 main.py Heartbeat 生命週期管理

**Role:** ready-for-agent

**What to build:**
1. `config.yaml` 加入 `heartbeat` 設定區塊。
2. `main.py` 在開機、動態熱重載、以及程式關閉時，管理每路串流的 `HeartbeatService` 實例。

**Acceptance criteria:**
- [x] `config.yaml` 包含 `heartbeat:` 設定區塊。
- [x] 開機時依活躍串流列表啟動對應的 `HeartbeatService`（包含 video 模式）。
- [x] `config.yaml` 變更時，停止舊的 Heartbeat 服務並依新設定重啟。
- [x] 程式退出（`KeyboardInterrupt`）時停止所有 Heartbeat 服務。
- [x] `heartbeat.enabled: false` 時不啟動 Heartbeat 服務。
