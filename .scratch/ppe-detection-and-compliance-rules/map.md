# Map: 人員裝備防護 (PPE) 與條件式工安合規規則引擎 (PPE Detection & Conditional Compliance Rules)

## Notes
- 基於單一客製 YOLO 模型（Pi 5 CPU 推論優化）。
- 支援 PPE 雙模判定（`direct_negative` 與 `head_anchor`），兼顧低遮擋與複雜遮擋場景。
- 支援外部設備狀態雙軌同步（背景輪詢 GET + Webhook POST）。
- 宣告式工安條件規則矩陣（Zone + 外部狀態 + 現場物件 + 必需 PPE / 阻隔物）。

## Decisions so far
- **架構模型**：單一 YOLO 端到端，不跑二階段次級模型，維持邊緣低延遲。
- **PPE 模式**：支援 `direct_negative` 與 `head_anchor`，提供 class mapping 供使用者自訂模型類別。
- **外部狀態**：Nano 端建立 `StatePoller` 定期輪詢現有 MES/PLC API，並保留 `POST /api/external_state` 接收推送。
- **規則引擎**：採用結構化 YAML 條件矩陣（純 dict/set 比對，運算耗時 < 0.1ms）。
- **事件與 UI**：透過既有 `argus-eventlog` 產生違規事件並附帶現場快照；Web UI 畫布即時標示綠框（合規）與紅框（違規）。
- [01-config-schema-and-class-mapping.md](issues/01-config-schema-and-class-mapping.md) — 擴充 `config.yaml` 與 `ConfigManager`，支援 `ppe_class_mapping`、`external_states`、`compliance_rules` 以及 Zone 的 `ppe_strategy` 與 `required_ppe`。
- [02-core-compliance-engine-and-ppe-association.md](issues/02-core-compliance-engine-and-ppe-association.md) — 建立 `compliance_engine.py`，實作空間包含度、IoU、PPE 雙模比對（`head_anchor`/`direct_negative`）與宣告式工安條件規則矩陣評估。
- [03-external-state-poller-and-webhook-api.md](issues/03-external-state-poller-and-webhook-api.md) — 實作 `state_poller.py` 外部狀態輪詢器（支援 JSON Path 解析、TTL 快取、連線異常降級）與 `POST /api/external_state`、`GET /api/compliance_status` REST API 端點。
- [04-main-loop-and-event-producer-integration.md](issues/04-main-loop-and-event-producer-integration.md) — 整合推論迴圈、`compliance_engine`、`state_poller` 與 `event_producer.process_compliance_events()`，產生標準工安違規事件日誌與截圖快照。
- [05-frontend-ui-and-realtime-canvas-visualization.md](issues/05-frontend-ui-and-realtime-canvas-visualization.md) — 實作 Web UI 全螢幕畫布合規/違規雙色渲染、缺失阻隔物警示橫條、動態工安狀態徽章與 `/detections_feed` SSE 管道擴充。
## Issues
- [x] 01: Config Schema & Class Mapping (`config_manager.py`)
- [x] 02: Core Compliance Engine & PPE Association (`compliance_engine.py`)
- [x] 03: External State Poller & Webhook API (`state_poller.py`, `web_ui.py`)
- [x] 04: Main Loop & Event Producer Integration (`main.py`, `event_producer.py`)
- [x] 05: Frontend UI & Real-time Canvas Visualization (`templates/index.html`, `web_ui.py`)
- [ ] 06: User Manual & Documentation Sync (`docs/user-manual/`)
