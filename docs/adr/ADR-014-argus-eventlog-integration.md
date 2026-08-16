# ADR-014：導入 `argus-eventlog` 輸出 ARGUS JSONL 事件（Argus Eventlog Integration）

| 欄位 | 內容 |
|------|------|
| **狀態** | 已接受 (Accepted) |
| **日期** | 2026-08-16 |
| **決策者** | 開發團隊 |
| **相關 ADR** | [ADR-006](ADR-006-per-stream-model-assignment.md)、[ADR-013](ADR-013-ums-client-model-sync.md) |
| **相關 Spec** | [argus-eventlog-integration/spec.md](../../.scratch/argus-eventlog-integration/spec.md) |

---

## 情境與問題

safety-predictor-nano 目前只把偵測結果寫進純文字 log（`stats_logger.py`）跟丟給 Web UI 即時顯示，沒有結構化的事件記錄。要跟下游系統（MES、告警平台）整合，需要依照公司共用的 ARGUS JSONL spec（`argus-eventlog` 套件，`0.1.x`，零依賴）輸出「事件」而不是逐幀 log —— 一次持續的違規要算一個事件，而不是每次推論都各自成一筆。

---

## 決策選項與決策

### 1. 是否採用 `argus-eventlog`

**決策：採用。** 跟 [ADR-013](ADR-013-ums-client-model-sync.md) 對 `ums-client` 的理由相同：零依賴、已在獨立 repo 完成並測試，供多個專案共用同一份 ARGUS JSONL 格式，避免各專案各自重刻序列化邏輯導致規格漂移。

### 2. 事件生命週期：狀態機，key 為 `(stream, label)`

**決策：** 在偵測迴圈外包一層 producer（`event_producer.py`），比照 `argus-eventlog/README.md` 建議的 `_prev_detected` pattern：某個 `(stream, label)` 首次出現時發 `EventStart`+`EventFrame`，持續出現時每次推論發 `EventFrame`，消失超過 `event_absence_tolerance`（預設 2 次）才發 `EventEnd`。

理由：round-robin 推論排程（[ADR-008](ADR-008-round-robin-inference-scheduling.md)）加上抽樣式推論頻率（`fps_limit`）本身取樣就稀疏，若逐幀嚴格判斷「這幀沒偵測到就立刻結束事件」，單幀漏判會把一段持續違規切成好幾個破碎的 `event_ref`。用容忍幀數換取事件邊界的穩定性。key 用 `(stream, label)` 而非單純 `stream`，讓同一支鏡頭同時出現的多種違規類型（例如同時有 `no_helmet` 跟 `zone_intrusion`）各自獨立追蹤生命週期，不會互相覆蓋彼此的 `event_ref`。

### 3. category / severity 對應策略：category 直接用 model label，severity 走 config 覆寫表

**決策：** `category` 直接使用 ultralytics `Results.names` 給的 class label 字串，不另外維護一份 id→語意的靜態對照表。`severity` 由 `config.yaml` 新欄位 `event_severity: {label: severity}` 覆寫，沒列到的 label fallback `"warning"`。

理由：這個專案的偵測類別會隨換模型而變動（`model_path`/`streams[].model` 本來就可以指向不同模型，見 [ADR-006](ADR-006-per-stream-model-assignment.md)），寫死在程式碼裡的 id→category 對照表換模型就要跟著改、容易過期漏改；直接吃 model 自帶的 label 字串，新模型上線不用動這層整合程式碼。severity 沒有客觀規則可以從 label 字串自動推導，交給設定檔明確覆寫，預設值選 `"warning"`（不漏報也不會過度 critical 洗版）。

### 4. camera_id 來源：config 顯式宣告 + fallback 鏈，不依賴套件的 URL 解析

**決策：** `streams[]` 新增可選欄位 `camera_id`，解析順序 `camera_id` → `label` → `f"stream{idx}"`；`mode=video` 用全域 `camera_id` 欄位，預設 `"video"`。不依賴 `argus-eventlog` 內建的「從 URL 解析 `cam-` 前綴」邏輯。

理由：這個專案的 RTSP URL 格式（如 `rtsp://127.0.0.1:8554/test_stream1`）沒有 `cam-` 前綴慣例，套件的自動解析對這個專案完全用不上，全部會落到套件預設的 `'unknown'`。用 stream index 當最終保底（而非沿用套件的 `'unknown'`）是為了避免多鏡頭都沒填設定時全部撞進同一個資料夾——現在只有 1 條 stream 看不出症狀，但 schema 要先留對。

### 5. `argus-eventlog` 本身的 bugfix：`_write()` 改依 record 自己的 `camera_id` 路由

**決策：** 修改 `argus-eventlog/src/argus_eventlog/writer.py::EventWriterService._write()`，寫入目錄/檔名優先採用 record 自己的 `camera_id` 屬性，`self.camera_id`（服務初始化時固定的值）只當作 record 沒帶 `camera_id` 時的 fallback。修完後整個 process 只需要一個 `EventWriterService` 實例。版本號 `0.1.0` → `0.1.1`。

理由：`EventWriterService._write()` 原本的設計是用「服務初始化時固定的 `camera_id`」決定寫入目錄，前提假設是「每個 process 只服務一支鏡頭」。但所有 `EventWriterService` 實例共用同一個全域 `event_queue`（`queue.Queue`），多個實例的背景執行緒對同一個 queue 呼叫 `get()` 時，哪個實例搶到哪筆 record 是不確定的——多鏡頭同 process 內按照 README 建議「每支鏡頭開一個實例」時，事件會被隨機分派到錯的鏡頭資料夾（JSONL 內容本身的 `camera_id` 欄位沒錯，只是目錄分類會錯位）。safety-predictor-nano 是支援多路 RTSP 串流、單一 process 內同時服務多支鏡頭的第一個消費專案（見 [ADR-008](ADR-008-round-robin-inference-scheduling.md)），這條路徑遲早會撞上；改成單一 writer + 依 record 路由是根治，而不是每個消費專案各自繞開。改動保持向下相容：其他單鏡頭、單 process 的既有消費專案裡，record 帶的 `camera_id` 本來就等於初始化時傳入的值，行為不變。

### 6. RTSP / video 兩種模式共用同一份 producer 呼叫

**決策：** 把 `main.py` 裡兩份幾乎一樣的 detection 格式化程式碼（RTSP round-robin worker、video 模式主迴圈各一份）抽成共用函式 `format_detections()`，兩個呼叫點都呼叫同一個 `event_producer.process_detections()`。

理由：兩條路徑本來就該有一致的事件輸出行為，各自實作一份容易漏改其中一處；抽共用函式比維護兩份平行邏輯划算。

---

## 理由（總結）

1. **重用既有基礎設施**：per-stream 設定的 optional field + fallback 風格（ADR-006）、round-robin 排程（ADR-008）不需改動即可支援事件狀態機的接入點。
2. **對抽樣式推論的現實讓步**：容忍幀數機制承認「這是抽樣偵測、不是逐幀連續追蹤」，用邊界穩定性換取正確性，而不是假裝有更精確的資料。
3. **根治而非繞開套件缺陷**：多鏡頭路由問題直接修在 `argus-eventlog` 裡（單一整合點），不在 safety-predictor-nano 這邊寫 workaround，未來其他消費專案也受益。

---

## 取捨與風險

- **ROI 是全畫面 placeholder**：spec 要求 `EventMeta.roi` 必填，但這個專案目前沒有 ROI/危險區域設定概念（純物件偵測，無畫框 UI）。用整張畫面當 placeholder，語意上不是真正的「監控區域」。真正的 zone 概念需要獨立的設定畫面與 config schema，列為 backlog（見 `.scratch/argus-eventlog-integration/issues/07-roi-zone-config-screen-backlog.md`），非本次範圍。
- **容忍幀數是經驗值，非精確計算**：`event_absence_tolerance` 預設 `2` 是根據「抽樣稀疏」的定性判斷，沒有根據實際 `fps_limit` 動態換算成秒數。若日後 `fps_limit` 落差很大（例如 1 vs 30），同一個預設值在不同部署下的「容忍秒數」差異可能很大，需要時可調整成依 `fps_limit` 動態換算。
- **`argus-eventlog` 尚未發布成遠端 repo**：跟 ADR-013 對 `ums-client` 的既有風險相同，目前仍是 `pip install -e <本機路徑>`，PyInstaller 打包時能否正確收進單一執行檔尚待部署階段驗證，非本 ADR 範圍。
- **severity 覆寫表沒有預設的「已知類別建議值」**：`event_severity` 是空白起點，維運人員需要自己填寫每個 label 的期望 severity，否則全部都是 `"warning"`。
