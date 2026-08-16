# Handoff：`argus-eventlog` 整合 — 剩餘工作（issue 06 / 07）

> 交接文件。這次 session 透過 `/grill-me` 把 argus-eventlog 整合的設計定案並實作完成，01～05 號 ticket 都做完並 commit。這份文件只交接**還沒做完的部分**（06 的一項、07 全部），細節不重複貼，直接看下面列的檔案路徑。

## 已完成，不用重做（直接看這些，不要重新推導）

- Spec：`.scratch/argus-eventlog-integration/spec.md`
- ADR：`docs/adr/ADR-014-argus-eventlog-integration.md`
- Tickets：`.scratch/argus-eventlog-integration/issues/01`～`07`（01～05 `Status: done`，06 `Status: done (partial)`，07 `Status: ready-for-human`）
- Commits（都還沒 push）：
  - `safety-predictor-nano` `b33b232`：完整整合（`event_producer.py` 狀態機、config schema、`inference_engine.py` label、`main.py` 接線）
  - `argus-eventlog`（`c:\projects\innolux\argus-eventlog`）`ffb0fbb`：`EventWriterService._write()` 多鏡頭路由 bug 修正，版本 `0.1.0→0.1.1`

**注意：** safety-predictor-nano 裡還有一批**平行進行、尚未 commit** 的 ums-client 整合（`model_sync.py`、`docs/adr/ADR-013-ums-client-model-sync.md`、`.scratch/ums-client-integration/`，以及 `main.py`/`config_manager.py`/`web_ui.py`/`templates/index.html` 的部分改動），是另一個 session 同時在做的，這次刻意沒去動它、commit 時也切開了。不要假設它已經完成或有問題，單純跳過不要碰。

## 下一階段工作

### 1. Ticket 06 剩一項：真實 `.jsonl` 輸出驗證

`.scratch/argus-eventlog-integration/issues/06-tests-and-verification.md` 最後一項沒打勾——`best.pt` 被 gitignore，這台開發機沒有真實模型權重，`mode=video` 推不出偵測結果，沒辦法實際驗證輸出。

**要做的事：** 找一台有真實模型權重的機器（樹莓派或有 `best.pt` 的開發環境），跑 `main.py`（`mode=video` 或接一條真實/測試 RTSP 串流），看一眼 `recordings/<camera_id>/events/*.jsonl` 的實際內容，確認符合 `argus-eventlog/README.md` 的 ARGUS JSONL spec v0.0.1，事件生命週期（start → frame(s) → end）看起來合理。

### 2. Ticket 07：ROI / 危險區域設定畫面（全新功能，還沒開始）

`.scratch/argus-eventlog-integration/issues/07-roi-zone-config-screen-backlog.md`。現況：`event_producer.py` 的 `EventMeta.roi`（spec 必填）寫死全畫面 placeholder，因為這個專案完全沒有 ROI/危險區域概念——沒有 config schema、沒有 Web UI 畫框介面、沒有「偵測框是否在區域內」的幾何判斷邏輯。

範疇（ticket 裡列的，還沒細部設計）：
- `config.yaml` 的 per-stream 或全域 ROI 多邊形 schema
- Web UI 畫框互動介面（`templates/index.html` 目前完全沒有這種互動）
- `event_producer.py` 改吃真實 ROI 而不是 placeholder
- bbox 是否落在 ROI 內的幾何判斷（目前系統完全沒有）

Ticket 狀態是 `ready-for-human`，不是 `ready-for-agent`——ticket 本身就寫明需要先有產品/UX 決策（哪些 stream 需要、畫框互動的期望）才能動手。**建議下一個 session 第一件事是針對 ROI/危險區域再跑一次 `/grill-me`**（跟這次同樣的做法），把設計定案再寫程式，不要跳過設計直接實作。

## Suggested skills for next session

- **mattpocock-skills:grilling**（`/grill-me`）——先把 ROI/危險區域的產品決策談定，ticket 07 明確標示還沒 ready-for-agent。
- **mattpocock-skills:tdd**——ROI 設計定案後，schema/幾何判斷邏輯照本專案既有 test-first 風格（`test_event_producer.py`、`test_config_manager.py` 可參考 mock 注入手法）。
- **run**——ticket 06 手動驗證那步，實際跑一次 `main.py` 看輸出。
- **code-review**（`/code-review`）——ticket 07 做完、要合併前跑一次，畢竟同時動到 config schema、Web UI、事件輸出三塊。
