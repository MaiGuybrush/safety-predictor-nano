Status: ready-for-agent

# Spec: ums-client 整合 — 從 UMS 平台同步模型

> 承接 `docs/planning/ums-client-integration-handoff.md`。上一個 session 已在獨立 repo `c:\projects\innolux\ums-client` 產出零依賴、無 Qt 的 `UmsApiClient`；本 spec 只處理「怎麼把它接進 safety-predictor-nano」，`ums-client` 本身不在此次改動範圍內。

## Problem Statement

safety-predictor-nano 是常駐在 Raspberry Pi 5 上的 headless 服務，目前 `model_path` / `streams[].model` 只能指向裝置本機已存在的模型檔案（`.pt` 或 NCNN 資料夾）。要換模型，得先用其他方式把檔案手動搬到裝置上再改 `config.yaml`，沒有辦法直接從 UMS 平台的模型清單挑一個版本、讓裝置自己抓下來用。裝置沒有桌面 GUI，也沒有人現場盯著看下載進度。

## Solution

在 safety-predictor-nano 內新增一個模型同步模組，包在 `ums-client` 之上：讀取 `config.yaml` 裡「這個 stream / 全域要用哪個 UMS 模型」的宣告，向 UMS 平台抓清單、下載對應版本的 artifact，落地成 `InferenceEngine` 認得的格式，再把實際路徑寫回 `config.yaml`。裝置開機時自動跑一次；同時在既有 Flask Web UI 加一個手動觸發端點，供人隨時要求重新同步。寫回 `config.yaml` 後，交給既有的 `ConfigManager` mtime 輪詢熱重載機制（ADR-007）自然生效，不另外設計一條通知路徑。

## User Stories

1. As a 裝置維運人員, I want 在 `config.yaml` 用模型名稱宣告某個 stream 要用哪個 UMS 模型, so that 我不用手動把模型檔案搬到裝置上。
2. As a 裝置維運人員, I want 裝置開機時自動去 UMS 平台抓一次目前宣告的模型, so that 裝置重開機/更新後模型自動保持最新，不用我手動介入。
3. As a 裝置維運人員, I want 在 Web UI 按一個按鈕手動觸發重新同步, so that 我不用重開機就能立即套用 UMS 平台上新上傳的模型版本。
4. As a 裝置維運人員, I want 同步完成後 `config.yaml` 的 `model_path`/`streams[].model` 自動更新成下載後的實際路徑, so that 我不用自己去猜下載檔案放在哪、手動填路徑。
5. As a 裝置維運人員, I want 同步失敗（網路不通、UMS 平台掛掉、模型名稱打錯）時裝置仍用舊模型正常運作, so that 一次同步失敗不會讓正在跑的偵測服務停擺。
6. As a 裝置維運人員, I want 在 Web UI 看到最近一次同步的結果（成功/失敗、時間、訊息）, so that 我知道要不要進一步排查。
7. As a 開發者, I want 同步邏輯集中在單一模組、以可注入的 client 呼叫 UMS API, so that 我可以在不打真實網路的情況下測試同步邏輯。
8. As a 開發者, I want `ConfigManager` 提供「只更新特定 key」的寫回方法, so that 寫回時不會像 `web_ui.py::save_config()` 那樣把整份設定重建、意外丟失其他既有欄位。
9. As a 裝置維運人員, I want 沒有在 `config.yaml` 宣告 UMS 模型的 stream 完全不受同步邏輯影響, so that 現有「直接指定本機模型路徑」的用法可以繼續用，不用被強迫遷移。
10. As a 開發者, I want 下載回來若不是資料夾（NCNN）也不是 `.pt` 檔案時有一致的處理規則, so that `InferenceEngine` 不會因為副檔名對不上而載入失敗。
11. As a 裝置維運人員, I want 可以選擇要抓某模型的最新 Active 版本、或釘住特定版本號, so that 我可以避免 UMS 平台上傳新版本後裝置自動跳版造成非預期的行為變化。

## Implementation Decisions

### Config schema 新增（延續 ADR-006 的 optional field + fallback 風格）

- 全域新增可選欄位 `ums_model`：`{name: str, version: "latest" | int}`（`version` 省略時預設 `"latest"`，意即該模型目前狀態為 `Active` 的最新版本）。存在時視為 `model_path` 的同步來源；同步寫回時覆蓋 `model_path`。
- `streams[]` 每個元素新增可選欄位 `ums_model`，格式同上，覆蓋該 stream 的 `model`。不存在時該 stream 完全不受同步邏輯影響（沿用現有 `model` 欄位或 fallback 到全域 `model_path`，行為不變）。
- 未宣告任何 `ums_model` 時，同步模組視為 no-op（沒有同步目標），現有純本機路徑用法完全不受影響（User Story 9）。

### 新模組 `model_sync.py`（唯一的整合 seam）

- 對外只有一個入口：`sync_all(config_manager, client=None) -> SyncReport`。
  - `client` 未提供時預設用 `UmsApiClient.from_env()`；測試時由呼叫端注入假 client，不打真實網路（User Story 7）。
  - 內部步驟：解析 `config_manager` 目前 raw config 中所有 `ums_model` 宣告 → 去重（同一個 `(name, version)` 只抓一次）→ 對每個目標呼叫 `fetch_my_models()` 找到對應 `ModelInfo`、依 `version` 規則選 `ModelVersionInfo` → `download_version()` 落地到 `models/<model_name>/v<version_number>/` → 依下方「Artifact 格式判斷規則」得到最終可用路徑 → 呼叫 `ConfigManager` 的寫回方法，把路徑寫回對應的 `model_path` 或 `streams[i].model`。
  - 任何單一目標失敗（網路錯誤、UMS 回傳模型不存在、版本不存在）**不中斷其他目標**，收集進回傳的 `SyncReport`（成功/失敗清單 + 訊息），已存在的舊 `model_path`/`streams[].model` 維持不動（User Story 5）。`sync_all()` 本身不拋例外中止呼叫端。

### Artifact 格式判斷規則（對應 handoff 落差 1）

`ums_client.download_version()` 回傳值只有兩種形態：解壓後的資料夾，或單一檔案（非 zip 時固定叫 `model.bin`）。落地規則：

- 回傳值是資料夾 → 視為 NCNN 模型，原樣使用（`InferenceEngine` 用 `os.path.isdir()` 判斷，天然相容，不用改名）。
- 回傳值是檔案且副檔名已經是 `.pt` → 原樣使用。
- 回傳值是檔案但副檔名不是 `.pt`（目前已知情況：`model.bin`）→ 就地更名為 `<model_name>.pt`，因為 `inference_engine.py` 只認資料夾（NCNN）或會直接丟給 `ultralytics.YOLO()` 的路徑，非 zip 單檔目前唯一支援的格式即為 PyTorch checkpoint。
- 這條規則目前**未用真實 `UMS_API_KEY` 驗證過**（handoff 落差 1 尚未解掉）。第一張 ticket 應優先用真實金鑰跑一次 `fetch_my_models()` + `download_version()` 確認實際回傳形態，若跟本規則假設不符，回頭調整此邏輯即可——因為判斷點集中在 `model_sync.py` 一處，不會擴散到其他模組。

### `ConfigManager` 新增寫回能力

- 新增方法（例如 `update_model_paths(updates: dict)`，key 為 `"model_path"` 或 `"streams[<index>].model"` 這類可定位到單一欄位的識別方式，具體 key 格式由實作時依 `get_stream_configs()` 現有結構決定）：讀原始 `config.yaml` 全文 → 只修改指定欄位 → 寫回整份 yaml。**不**像 `web_ui.py::save_config()` 那樣從表單欄位重建整個 dict，避免遺失表單沒涵蓋的欄位（例如新加的 `ums_model`）（User Story 8）。
- 寫回後檔案 mtime 自然變動，既有 `check_for_updates()` 輪詢機制（ADR-007）會偵測到並觸發熱重載，不需要新增任何跨執行緒通知或訊號。

### 觸發點（對應 handoff 落差 2，決策：開機自動 + Web UI 手動，兩者都要）

- `main.py` 啟動流程中、建立 `stream_units`/`engine_cache` 之前，呼叫一次 `model_sync.sync_all()`（同步阻塞執行；裝置開機本來就要等模型載入，多等一次下載可接受）。同步結果寫回 `config.yaml` 後，沿用既有的「讀取 config → 建立 stream_units」流程，不需要特殊分支。
- `web_ui.py` 新增一個 POST 端點（例如 `/sync_models`，比照現有 `/model_info`、`/detections_feed` 的命名風格），呼叫同一個 `model_sync.sync_all()`，回傳 JSON 格式的 `SyncReport`（成功/失敗清單）。前端頁面加一個觸發按鈕（Further Notes 註記：本 spec 只定義端點與資料格式，樣板/按鈕的 HTML 只是既有 `templates/index.html` 的小增量，不獨立展開 UI 設計）。
- 兩個觸發點呼叫的是同一個 `model_sync.sync_all()`，沒有各自實作一份同步邏輯。

### 最近一次同步結果（User Story 6）

- `model_sync` 模組維護一個全域最近一次 `SyncReport`（比照 `web_ui.py` 現有 `MODEL_INFO`/`LATEST_DETECTIONS` 全域變數跨執行緒分享的既有慣例，見 AGENTS.md「State Management」一節），`/sync_models` 端點回傳當次結果，另可視需要加一個 GET 端點或併入既有 `/model_info` 回傳最近一次同步狀態（實作時二選一，不是本 spec 的強制決定點）。

## Testing Decisions

- 好測試只驗證外部行為（`sync_all()` 的輸入 config + mock UMS 回應 → config.yaml 實際被寫成什麼、`SyncReport` 內容），不斷言 `ums_client` 內部怎麼呼叫 HTTP。
- `model_sync.py`：用 `unittest.mock` 注入假 `UmsApiClient`（`fetch_my_models`/`download_version` 回傳假資料），不得打真實網路。Prior art：`test_engine_cache.py` 用 `@patch("main.InferenceEngine")` 這種注入手法。
- `ConfigManager.update_model_paths()`：用 `tempfile` 建立真實 yaml 檔案、寫回後重新讀檔驗證內容與既有未涉及欄位是否保留。Prior art：`test_config_manager.py` 的 `setUp`/`write_yaml` tempfile 模式，直接延伸。
- `/sync_models` 端點：用 Flask `test_client()`，mock 掉 `model_sync.sync_all()`，驗證回傳的 JSON 結構與狀態碼。Prior art：`test_sse_detections.py` 的 `web_ui.app.test_client()` 模式。
- Artifact 格式判斷規則（資料夾/`.pt`/需更名的單檔三種分支）獨立用單元測試覆蓋，不依賴真實下載。

## Out of Scope

- `ums-client` 套件本身的修改（已在另一個 repo 完成、已測試，此次視為外部依賴）。
- 用真實 `UMS_API_KEY` 實際驗證 UMS 伺服器回傳的 artifact 真實長相（這是第一張 ticket 的手動驗證步驟，不是可自動化測試的部分，但其結論可能回頭修正「Artifact 格式判斷規則」）。
- `AIVision_GUI` 是否改用 `ums-client`（獨立專案的獨立任務，見 `ums-client/README.md` 的「與 AIVision_GUI 的關係」一節）。
- Web UI 同步按鈕的視覺/互動設計細節（只定義端點與資料格式）。
- Cron/排程定期同步（本次決策是開機自動 + 手動端點，排程不在範圍內）。
- `ums-client` 尚未發布成遠端 repo（目前仍是 `pip install -e <本機路徑>`）；`requirements.txt`/部署腳本怎麼處理本機路徑依賴，留給實作時的 ticket 處理，非架構層決策。

## Further Notes

### 文件更新（本次 to-spec 討論結論）

- **不新增 `docs/prd/`**：本專案的 issue tracker 已改用 `.scratch/<feature>/spec.md`（見上個 commit「switch issue tracker to local markdown」與 `docs/agents/issue-tracker.md`），這份 spec.md 本身就取代舊有 PRD 角色，不重複產出一份 `docs/prd/ums_client_integration_prd.md`。
- **需要新增 ADR**：定案後（本次 to-spec 已把 handoff 落差 2、3 的開放問題定案）應比照 `docs/adr/ADR-001`~`ADR-012` 格式新增一篇，內容至少涵蓋：
  1. 是否採用 `ums-client`（決策：採用，零依賴/無 Qt，避免重刻 UMS API 呼叫邏輯）。
  2. Config schema 新增 `ums_model` 欄位的設計（可與 ADR-006 並列參照，同樣是 optional field + fallback 的風格）。
  3. 同步觸發時機（決策：開機自動 + Web UI 手動，兩者都要）。
  4. `config.yaml` 寫回機制與熱重載整合（決策：自動寫回 + 沿用 ADR-007 既有 mtime 輪詢，不新增通知路徑）。
  - 建議 ADR 檔名：`ADR-013-ums-client-model-sync.md`，`/to-tickets` 產出的最後一張 ticket 或獨立一張 ticket 負責補這篇（比照 handoff 建議順序「定案後補一篇 ADR」）。
- `AGENTS.md` 目前「Testing & QA」一節寫「Frameworks: None / 沒有測試框架」已經跟現況（一堆 `test_*.py` 用 `unittest`）不符，是既有文件債，不在本次範圍內一併修正，但實作 agent 若有餘力可以順手更新一行。

### 部署面注意事項（非架構決策，實作時留意）

- `ums-client` 目前只能 `pip install -e <本機路徑>`，PyInstaller 打包（`AGENTS.md` 的 Build/Deploy 段落）時要確認這個本機依賴能不能正確被收進單一執行檔（`--collect-all` 目前只列了 `ultralytics`、`flask`）。
- Raspberry Pi 5 headless 環境下開機同步屬於阻塞式網路呼叫，若 UMS 平台無回應，`sync_all()` 應在合理 timeout 內失敗並讓開機流程繼續（`ums_client.UmsApiClient` 建構子已有 `timeout` 參數，預設 30 秒，可沿用）。
