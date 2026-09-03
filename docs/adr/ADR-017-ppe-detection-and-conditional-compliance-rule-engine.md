# ADR-017：人員裝備防護 (PPE) 檢測與條件式工安合規規則引擎架構

| 欄位 | 內容 |
|------|------|
| **狀態** | 已接受 (Accepted) |
| **日期** | 2026-09-03 |
| **決策者** | 開發團隊 |
| **相關 ADR** | [ADR-006](ADR-006-per-stream-model-assignment.md)、[ADR-007](ADR-007-engine-instance-cache.md)、[ADR-008](ADR-008-round-robin-inference-scheduling.md)、[ADR-009](ADR-009-sse-over-websocket-detection-channel.md)、[ADR-010](ADR-010-client-side-canvas-detection-overlay.md)、[ADR-014](ADR-014-argus-eventlog-integration.md) |
| **相關 Spec** | [.scratch/ppe-detection-and-compliance-rules/spec.md](../../.scratch/ppe-detection-and-compliance-rules/spec.md) |

---

## 情境與問題

目前 Argus Safety Predictor Nano 具備基礎目標偵測與 ROI 電子圍籬入侵判定功能。在實際導入製造業廠房與工程現場時，面臨以下工安監管瓶頸：

1. **PPE 防護裝備辨識缺失**：無法判定人員是否配戴安全帽 (`helmet`) 或反光背心 (`vest`)，且現場人員彎腰、側身或肢體交錯遮擋時極易產生演算法誤報或漏報。
2. **缺乏複合條件式工安合規判定**：現場工安規則具有情境依賴性（例如：「機台處於維護狀態」且「人員進入開門作業」時，現場**必須同時具備**「三角錐/安全護欄」與「完整 PPE 著裝」）。單一目標出現與否不足以作為告警依據。
3. **缺乏外部設備狀態整合**：邊緣裝置無法即時獲知上層 MES / PLC / SCADA 的機台運轉或保養狀態，導致無法動態啟用相應的工安防護等級。

---

## 決策選項與決策

### 1. 模型推論架構：單一客製 YOLO 模型端到端輸出

**決策：** 採用單一客製 YOLO 模型同時輸出所有類別（`person`, `head`, `helmet`, `no_helmet`, `vest`, `no_vest`, `cone`, `guardrail`），不採用兩階段（Two-stage Crop）或多模型並行（Ensemble）。

**理由：**
- **邊緣端算力極限**：Raspberry Pi 5 採純 CPU 推論，多模型或動態 Crop 次級分類器會造成顯著的 CPU 負載與延遲暴增。
- **架構最簡 (Ponytail 原則)**：單一模型維護性最好、推論開銷固定，能維持 2~5 FPS 的穩定即時性。

---

### 2. PPE 判定機制：雙模策略 (Dual-Mode) 與類別映射 (Class Mapping)

**決策：** 
- 支援 **`direct_negative`**（直接依模型輸出之 `no_helmet` / `no_vest` 告警）與 **`head_anchor`**（偵測到 `head` 時以空間包含度比對 `helmet`，兼顧彎腰與防遮擋誤判）兩種策略，可於 `config.yaml` 依 Zone 彈性設定。
- 提供 `ppe_class_mapping` 配置，將不同開源或自訓模型的類別標籤無痛映射至系統內部標準類別。

**理由：** 兼顧俯視遠景（適合負類別直出）與密集遮擋視角（適合頭部錨點包含度比對），且使用者更換第三方模型時無需修改程式碼。

---

### 3. 複合工安規則：邊緣端輕量宣告式規則引擎 (Declarative Rule Engine)

**決策：** 在 `config.yaml` 採用宣告式條件矩陣結構（`when (Zone + 設備狀態 + 目標)` $\rightarrow$ `require (三角錐/護欄 + PPE)` $\rightarrow$ `on_violation (等級 + 類別)`），後端以高效 Python `dict/set` 集合運算進行評估。

**理由：** 零自訂直譯器（Zero-parser），運算耗時小於 0.1ms，不佔用邊緣 CPU 資源，且結構化欄位易於在 Web UI 製作表單與維護。

---

### 4. 外部狀態同步：雙軌同步（背景輪詢 Polling + Webhook 接收）與 TTL 故障安全

**決策：**
- 建立 Daemon 輪詢執行緒，週期性查詢外部 MES/PLC HTTP GET API，將狀態寫入記憶體快取。
- 開放 `POST /api/external_state` 接收外部系統 Webhook 主動推送。
- 引入 TTL 自動超時過期機制，當連線逾時或未在時限內更新時，狀態自動降級為預設值 (`UNKNOWN` / `fallback_value`)。

**理由：** 工廠現場外部系統改造成本高，支援主動查詢現有 API 可直接落地，同時具備 Fail-Safe 防護避免狀態永久卡死。

---

### 5. 事件與視覺呈現：沿用標準管道與前端雙色動態渲染

**決策：**
- 違規事件由 `event_producer.py` 封裝為標準 `argus-eventlog`（`EventStart / EventEnd`），自動附帶違規瞬間之清晰原始影像快照 (`snapshot`) 與 ROI 多邊形資料。
- 前端 Web UI 畫布即時渲染：合規物件綠框 (`#00e676`)、違規人員紅色閃爍框 (`#ff1744`) 附帶原因標籤，全螢幕 Zone 徽章動態顯示工安狀態。

**理由：** 無縫沿用現有 UMS 上傳與錄影通道，前端與後端判定透過 SSE 實現 100% 同步。

---

## 影響與驗證

1. **效能影響**：新增之幾何關聯、外部輪詢與規則評估均為極輕量運算（CPU 增加 < 1%），推論迴圈保持流暢。
2. **向下相容性**：既有未設定 PPE 或工安規則的 Zone 與 Stream 保持原行為運作，完全向後相容。
3. **驗證方式**：
   - 單元測試：`test_compliance_engine.py`、`test_state_poller.py`、`test_config_manager.py`。
   - 整合測試：`test_compliance_e2e.py` 驗證推論、狀態輪詢、規則觸發與快照產出。
