# Tickets: 人員裝備防護 (PPE) 檢測與條件式工安合規規則引擎

## Overview
本文件統整「人員裝備防護 (PPE) 檢測與條件式工安合規規則引擎」之開發工單清單，對應 `.scratch/ppe-detection-and-compliance-rules/issues/`。

---

## Ticket Backlog

### Ticket 01: Config Schema & Class Mapping
* **File**: `.scratch/ppe-detection-and-compliance-rules/issues/01-config-schema-and-class-mapping.md`
* **Target**: `config_manager.py`, `config.yaml`, `test_config_manager.py`
* **Summary**: 擴充設定檔結構，支援 `ppe_class_mapping`, `external_states`, `compliance_rules` 與 `zones` 之 `required_ppe` 及 `ppe_strategy`。

### Ticket 02: Core Compliance Engine & PPE Association
* **File**: `.scratch/ppe-detection-and-compliance-rules/issues/02-core-compliance-engine-and-ppe-association.md`
* **Target**: `compliance_engine.py`, `test_compliance_engine.py`
* **Summary**: 實作核心合規引擎，包含 PPE 雙模判定（`direct_negative` 與 `head_anchor`）、人體包含度幾何演算法、宣告式條件規則評估矩陣。

### Ticket 03: External State Poller & Webhook API
* **File**: `.scratch/ppe-detection-and-compliance-rules/issues/03-external-state-poller-and-webhook-api.md`
* **Target**: `state_poller.py`, `web_ui.py`, `test_state_poller.py`
* **Summary**: 實作外部設備狀態同步機制，包含背景輪詢 Daemon 執行緒、JSON 巢狀解析、逾時 fallback 與 `POST /api/external_state` Webhook 端點。

### Ticket 04: Main Loop & Event Producer Integration
* **File**: `.scratch/ppe-detection-and-compliance-rules/issues/04-main-loop-and-event-producer-integration.md`
* **Target**: `main.py`, `event_producer.py`, `test_compliance_e2e.py`
* **Summary**: 串接推論迴圈、合規比對、`argus-eventlog` 違規事件輸出與原始影像截圖快照。

### Ticket 05: Frontend UI & Real-time Canvas Visualization
* **File**: `.scratch/ppe-detection-and-compliance-rules/issues/05-frontend-ui-and-realtime-canvas-visualization.md`
* **Target**: `templates/index.html`, `web_ui.py`
* **Summary**: Web UI 全螢幕畫布合規綠框 / 違規紅框雙色渲染、違規原因標籤、工安狀態 Badge 與 SSE payload 擴充。

### Ticket 06: User Manual & Documentation Sync
* **File**: `.scratch/ppe-detection-and-compliance-rules/issues/06-user-manual-and-documentation-sync.md`
* **Target**: `docs/user-manual/`
* **Summary**: 更新 mdBook 使用者操作手冊，補齊 PPE 設定、條件規則與全螢幕監控說明，並執行 `mdbook build` 驗證。
