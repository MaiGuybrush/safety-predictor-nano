Status: ready-for-agent

# Spec: argus-eventlog 整合 — 偵測到事件時輸出 ARGUS JSONL

> 承接 `/grill-me` 對談定案的設計（見本次 session 逐輪 Q&A）。`argus-eventlog` 本身（`C:\projects\innolux\argus-eventlog`）是另一個零依賴的共用套件，格式規格為 ARGUS JSONL spec v0.0.1；本 spec 涵蓋「怎麼把它接進 safety-predictor-nano」，以及對 `argus-eventlog` 本身的一個必要 bugfix。

## Problem Statement

safety-predictor-nano 目前只把偵測結果（`cls` int、`conf`、`xyxy`）寫進純文字 log（`stats_logger.py`）跟丟給 Web UI 即時顯示，沒有結構化的事件記錄。要跟其他系統（如 MES、告警平台）整合，需要依照公司共用的 ARGUS JSONL spec 輸出事件檔案，讓下游系統能解析「什麼時候發生了什麼事件」而不只是逐幀 log。

## Solution

在偵測迴圈（`main.py` 的 RTSP round-robin worker 與 video 模式主迴圈）新增一層「偵測結果 → argus-eventlog 事件」的狀態機 producer（`event_producer.py`），比照 `argus-eventlog/README.md` 建議的 `_prev_detected` pattern：某個 (stream, label) 組合首次出現時發 `EventStart`+`EventFrame`，持續出現時每次推論都發 `EventFrame`，消失超過容忍幀數後發 `EventEnd`。全域只維護一個 `EventWriterService` 實例（見下方 argus-eventlog bugfix），由它把事件寫成 JSONL。

## User Stories

1. As a 使用這套系統的下游整合方, I want 模型偵測到東西時能拿到符合 ARGUS JSONL spec 的事件檔, so that 我不用自己寫一份 parser 去啃 `detections.log` 的純文字格式。
2. As a 裝置維運人員, I want 同一個持續中的違規只算一個事件（一個 `event_ref`）, so that 事件記錄不會被抽樣稀疏的推論頻率切成一堆破碎的短事件。
3. As a 開發者, I want category 直接用模型自己的 class label（不用另外維護一份 id→語意對照表）, so that 換模型、換 class 定義時不用回來改這層整合程式碼。
4. As a 裝置維運人員, I want 可以在 `config.yaml` 幫特定 label 覆寫 severity, so that 不同違規類型可以有不同告警等級，不用全部都是同一個預設值。
5. As a 裝置維運人員, I want 每個 RTSP stream 可以在 `config.yaml` 宣告自己的 `camera_id`, so that 多鏡頭時事件檔案分得清楚是哪支鏡頭，不用全部落到同一個 `unknown` 資料夾。
6. As a 開發者, I want `argus-eventlog` 在多鏡頭、單一 process 共用一個 `EventWriterService` 時，事件寫進「這筆事件自己宣告的 camera_id」對應的資料夾, so that 不會因為套件內部用「服務初始化時固定的 camera_id」決定路徑，而把 A 鏡頭的事件寫進 B 鏡頭的資料夾。
7. As a 開發者, I want RTSP 跟 video 兩種模式共用同一份 detection 格式化與事件送出邏輯, so that 不用維護兩份幾乎一樣的程式碼（既有的重複）。

## Implementation Decisions

### `argus-eventlog` bugfix（Out-of-repo，但這次一併處理）：`_write()` 依 record 自己的 `camera_id` 路由

**問題**：`EventWriterService._write()` 原本用 `self.camera_id`（服務初始化時固定的值）決定寫入目錄；但所有 `EventWriterService` 實例共用同一個全域 `event_queue`，多個實例的背景執行緒對同一個 `queue.Queue` 呼叫 `get()` 時，哪個實例搶到哪筆 record 是不確定的 → 多鏡頭同 process 內開多個實例時，事件可能被寫進錯的鏡頭資料夾（JSONL 內容本身的 `camera_id` 欄位沒錯，只是目錄分類會錯位）。

**決策**：改成整個 process 只開一個 `EventWriterService`；`_write()` 的 `camera_id`/`ccd_no` 改成優先讀 record 自己的 `camera_id` 屬性，`self.camera_id`/env var 只當作 record 沒帶 `camera_id` 時的 fallback（向下相容其他只有單鏡頭、單 process 的既有消費專案，例如 `EventWriterService(camera_id="CCD1")` 搭配單一 writer 執行緒的用法完全不受影響）。

```python
# writer.py::_write()
camera_id: str = getattr(record, 'camera_id', None) or self.camera_id
ccd_no: str = os.environ.get('AIVISION_CCD_NO') or os.environ.get('CCD_NO') or camera_id
```

版本號 `0.1.0` → `0.1.1`（bugfix，非 spec 變更，不影響 JSONL 格式本身）。

### Config schema 新增（延續 ADR-006 optional field + fallback 風格）

- `streams[]` 每個元素新增可選欄位 `camera_id`。解析順序（`config_manager.get_stream_configs()` 回傳的每個 stream dict 新增 `camera_id` 原始值，實際 fallback 鏈在 `main.py::build_stream_units()` 解出）：
  1. 該 stream 明確設定的 `camera_id`
  2. `label`（若有設定）
  3. `f"stream{idx}"`（`idx` 為該 stream 在清單中的序號，避免多鏡頭都沒設定時全部落到套件預設的 `'unknown'` 而互相覆蓋）
- 全域新增可選欄位 `camera_id`：供 `mode=video` 使用，沒設時預設 `"video"`。
- 全域新增可選欄位 `event_severity`：`{label: "critical" | "warning" | "info"}`，沒列在裡面的 label fallback `"warning"`。
- 全域新增可選欄位 `event_absence_tolerance`：int，預設 `2`。某個 (stream, label) 事件連續幾次推論都沒偵測到才視為真正結束（見下方「狀態機」）。

未宣告以上任何欄位時，全部套用預設值，現有 `config.yaml` 完全不受影響（不強迫既有部署遷移）。

### `inference_engine.py`：補上 label string

`InferenceEngine.infer()` 目前只回傳 `cls`（int）跟 `conf`，沒有 label 字串。ultralytics `Results` 物件有 `.names`（`{class_id: label_string}`，來自模型本身的類別定義）。在組裝 `detections` 時補一個 `"label": r.names.get(int(box.cls), str(int(box.cls)))` 欄位（找不到對照時 fallback 用 class id 字串，不讓整包偵測結果因為單一 class 沒名字而掛掉）。

### 新模組 `event_producer.py`（唯一的狀態機/整合 seam）

- 對外一個入口：`process_detections(stream_key, camera_id, detections, frame_w, frame_h, severity_map=None, tolerance=2)`。
  - `detections`：`[{"xyxy": [x1,y1,x2,y2], "cls": int, "conf": float, "label": str}, ...]`（像素座標，與 `main.py` 既有 `formatted_detections` 同格式，只是多了 `label`）。
  - 模組層級狀態 `_state: {(stream_key, label): {"event_ref": str, "absent": int}}`，比照 README 範例的 `_prev_detected` pattern，但用 `(stream_key, label)` 當 key（同一 stream 同時有多種違規 label 時，各自獨立追蹤生命週期，不會互相覆蓋彼此的 `event_ref`）。
  - 每次呼叫依目前偵測到的 label 集合跟 `_state` 既有 key 做差集：
    - label 首次出現（不在 `_state`）→ 建立新的 `event_ref`（格式 `f"{label}_{YYYYMMDD_HHMMSS_ffffff}"`），依序 `event_queue.put(EventStart(...))` 再 `event_queue.put(EventFrame(...))`。`EventStart.meta` 用全畫面 placeholder ROI `[[0,0],[1,0],[1,1],[0,1]]`（專案目前沒有 ROI/危險區域設定，見下方 Out of Scope）。`severity` 用 `severity_map.get(label, "warning")`。
    - label 持續出現（已在 `_state`）→ `absent` 計數歸零，只發 `EventFrame`。
    - `_state` 裡有、但這次沒偵測到的 label → `absent` 計數 +1；超過 `tolerance` 才真正 `event_queue.put(EventEnd(reason="no_longer_detected"))` 並從 `_state` 移除（未超過容忍值前，只是不發 frame，事件保持開啟，避免抽樣稀疏造成的單幀漏判就把一個持續事件切成好幾段）。
  - bbox 座標正規化：`x/frame_w`、`y/frame_h`、`w=(x2-x1)/frame_w`、`h=(y2-y1)/frame_h`（spec 的 `BboxDetection` 座標是 0~1 相對值）。

### `main.py` 整合

- 開頭設定 `argus_eventlog.writer.DEFAULT_PROG = "SafetyNano"`，避免跟其他消費專案（如 AIVision_GUI）共用同一台裝置時檔名互相覆蓋。
- `main()` 開頭建立唯一一個 `EventWriterService()` 並 `start()`；`KeyboardInterrupt` 時 `stop()`。不隨 config 熱重載重建（跟 `stream_units` 生命週期脫鉤，本來就只需要一個，見上方 bugfix 決策）。
- 抽出共用函式（解決現有 RTSP round-robin worker 與 video 模式主迴圈裡兩份幾乎一樣的 detection 格式化程式碼重複）：
  - `format_detections(raw_detections) -> list[dict]`：把 `engine.infer()` 回傳的原始 `detections`（`xyxy` 可能是巢狀 list/ndarray）轉成扁平的 `{"xyxy": [x1,y1,x2,y2], "cls": int, "conf": float, "label": str}`。
  - 兩個呼叫點（RTSP `_inference_worker`、video 模式主迴圈）都改用這個共用函式，再各自呼叫 `event_producer.process_detections(...)`，帶入各自 resolve 出來的 `camera_id`、`frame_w`/`frame_h`（`frame.shape[:2]`）、`config.get("event_severity", {})`、`config.get("event_absence_tolerance", 2)`。
- `build_stream_units()` 依上方 config schema 段落的 fallback 鏈，把每個 unit 的 `camera_id` 解出來存進 `unit["camera_id"]`。
- video 模式的 `camera_id` 直接 `config.get("camera_id") or "video"`。

### `requirements.txt`

新增一行 `-e C:\projects\innolux\argus-eventlog`（editable install，沿用 ADR-013 對 `ums-client` 的做法；`argus-eventlog` 也還沒發布成遠端 repo）。

## Testing Decisions

- `event_producer.py`：純函式狀態機，單元測試直接呼叫 `process_detections()` 多次模擬「出現→持續→消失」序列，斷言送進 `argus_eventlog.event_queue` 的物件序列（action 順序、`event_ref` 是否跨呼叫維持一致、容忍幀數內不提前 `end`、超過後才 `end`）。測試前後清空 `event_queue` 與模組層 `_state`（比照 `argus-eventlog/tests/test_writer.py` 的 `clean_queue` fixture 手法）。
- `inference_engine.py` 的 label 補齊：mock `ultralytics.YOLO`（`r.names` / `box.cls`），斷言 `infer()` 回傳的 detections 帶正確 `label`；對照不到的 class id fallback 用 id 字串本身。
- `config_manager.py`：延伸既有 `test_config_manager.py` 的 tempfile 模式，驗證 `streams[].camera_id`、全域 `camera_id`/`event_severity`/`event_absence_tolerance` 的讀取與預設值。
- `argus-eventlog` 本身：延伸 `tests/test_writer.py`，新增「單一 `EventWriterService` 實例、兩筆不同 `camera_id` 的 record」情境，斷言各自落在自己 `camera_id` 的資料夾（不是 service 初始化時的 `camera_id`）。

## Out of Scope

- ROI / 危險區域設定畫面（真正的 zone 概念、Web UI 畫框）：目前用全畫面 placeholder ROI 頂著，之後要做才需要新增設定 UI 與 config schema，獨立開一張 backlog ticket（見 `issues/07-roi-zone-config-screen-backlog.md`），這次不動。
- `EventContext`（MES 工號/產線/班別等業務上下文）：目前系統沒有對應的資料來源，先不接，`context=None`。
- SOP 專用欄位（`FrameStep`、`EventResult`、`subtype`）：這次的偵測是單純物件偵測，不是 SOP 步驟流程，不使用。
- Web UI 顯示「最近事件」列表：這次只處理事件輸出到檔案，不做前端呈現（跟 `ums-client` spec 一樣，UI 呈現不是本次架構決策範圍）。
- PyInstaller 打包時 `argus-eventlog` 本機路徑依賴能否正確被收進單一執行檔：留給部署階段驗證，非本次 spec 範圍（跟 ADR-013 對 `ums-client` 的既有風險註記一致）。

## Further Notes

- 需要新增 `docs/adr/ADR-014-argus-eventlog-integration.md`，格式比照 ADR-006/ADR-013，涵蓋：是否採用 `argus-eventlog`、事件生命週期狀態機設計、category/severity 對應策略、camera_id fallback 鏈、以及對 `argus-eventlog` 本身的 bugfix 決策。
