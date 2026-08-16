# Handoff：導入 `ums-client` 到 safety-predictor-nano

> 交接文件。上一個 session 在 `AIVision_GUI` 專案裡把 UMS 模型清單/下載邏輯抽成獨立套件 `ums-client`，目的就是讓本專案能用。**本專案這次完全沒被改動**——這份文件是為了讓下一個 session 接續「怎麼把 ums-client 接進 safety-predictor-nano」這個規劃工作。

## 已完成的事（上一個 session，發生在別的目錄）

- 在 `c:\projects\innolux\AIVision_GUI\src\controllers\model_manager.py` 找到既有的 UMS API 呼叫邏輯（`UmsApiClient`），它本身不依賴 Qt。
- 把它抽成獨立、零依賴、無 Qt 的新 repo：`c:\projects\innolux\ums-client`。已安裝測試（6/6 通過），已確認 import 不會拉入 PySide6。
- `AIVision_GUI` 與 `safety-predictor-nano` 兩個現有專案本身都**沒有**被修改。

不重複貼細節，需要時直接看：
- 這次的規劃書（含所有設計決策與取捨理由）：`c:\Users\guybr\.claude\plans\snappy-seeking-glacier.md`
- 新套件文件：`c:\projects\innolux\ums-client\README.md`
- 新套件實作：`c:\projects\innolux\ums-client\src\ums_client\client.py`
- 原始 UMS API 規格文件：`c:\projects\innolux\AIVision_GUI\src\controllers\Client-EdgeApp-MyModels-API-Reference.md`

## ums-client 套件速覽（只列下一步用得到的事實）

- 安裝：`pip install -e c:\projects\innolux\ums-client`（目前只有本機路徑，尚未建遠端 repo）
- 用法：`UmsApiClient.from_env()`（讀 `UMS_BASE_URL` / `UMS_API_KEY`）→ `fetch_my_models()` → `download_version(version_id, dest_dir, progress_cb=None)`
- **刻意不含**：本機資料夾命名規則、`memo.txt`、CCD 部署等 AIVision_GUI 專屬慣例——這是跟使用者確認過的範圍排除（見規劃書「範圍確認」段落），因為 safety-predictor-nano 的模型載入方式跟 AIVision_GUI 完全不同（見下）。

## safety-predictor-nano 現況（跟模型載入相關）

- `config.yaml`：全域 `model_path` 欄位，`streams[].model` 可 per-stream override（見 `config_manager.py::get_stream_configs()`）。
- `inference_engine.py::InferenceEngine(model_path)`：用 `os.path.isdir(model_path)` 判斷 NCNN（資料夾）還是 PyTorch（`.pt` 檔案），直接丟給 `ultralytics.YOLO(model_path)`。
- `docs/adr/ADR-006`：per-stream model assignment（已接受）。
- `docs/adr/ADR-007`：相同 model_path 共用 `InferenceEngine` 實例快取（已接受）。整合時要注意快取 key 是 model_path 字串，模型下載後的路徑要跟這個快取機制相容。

## 已知的整合落差（未解決，這是下一步的主要工作）

1. **副檔名/格式不確定**：`ums_client.download_version()` 對非 zip 回應會存成固定檔名 `model.bin`，但 `ultralytics.YOLO()` 需要 `.pt` 副檔名或正確的 NCNN 資料夾結構才認得。這次沒有拿真實 API Key 實測過 UMS 伺服器實際回傳的檔案/壓縮包長相，不確定會落在哪一種情況。**下一步第一件事應該是用真實 UMS_API_KEY 手動跑一次 `fetch_my_models()` + `download_version()`，看實際拿到什麼，再決定要不要在 safety-predictor-nano 這邊加一層「依 artifact 內容判斷/重新命名副檔名」的邏輯。**
2. **下載觸發時機未決定**：safety-predictor-nano 是 headless、常駐在 RPi5 上的服務，沒有像 AIVision_GUI 那樣的桌面 GUI 讓使用者按「同步模型」。可能選項：開機時同步一次、cron/排程、或在既有 Flask Web UI 加一個同步端點/按鈕。這是需要跟使用者確認的產品決策，不是技術限制。
3. **`config.yaml` 寫回流程未設計**：模型下載完之後，`model_path`（或 `streams[].model`）要怎麼指向新路徑？`ConfigManager` 目前只有讀取邏輯（`load_config`/`get`/`get_stream_configs`），沒有寫入。是要自動改寫 `config.yaml`，還是下載完只印出路徑、由人工填？
4. **尚未落地成 ADR**：「是否/如何採用 ums-client」目前只存在於上一個 session 的對話與規劃書裡，還沒寫成本專案的 ADR。定案後應比照 `docs/adr/ADR-001` 到 `ADR-012` 的既有格式補一篇（見 `docs/adr/README.md` 的索引與新增流程）。

## 建議下一步順序

1. 用真實 `UMS_API_KEY` 手動跑一次 ums-client，解掉落差 1（實際格式問題）。
2. 針對落差 2、3 兩個開放問題，跟使用者對齊決定（建議用 grilling 或 `/plan` 而不是直接動手，避免又蓋出一個跟 AIVision_GUI 一樣、業務邏輯跟框架耦合在一起的實作）。
3. 定案後補一篇 ADR。
4. 照本專案既有的 test-first 慣例（已有 `test_config_manager.py`、`test_engine_cache.py` 等）實作整合。

## Suggested skills for next session

- **mattpocock-skills:grilling** 或 **`/plan`** — 先把上面「已知的整合落差」2、3 兩點跟使用者對齊，再動手，避免重蹈 AIVision_GUI 把下載邏輯跟 GUI 框架耦合在一起的覆轍。
- **mattpocock-skills:domain-modeling** — 定案後補一篇 ADR（本專案已有 12 篇既有 ADR 可參考格式，`docs/adr/README.md` 有索引與新增步驟）。
- **mattpocock-skills:tdd** — 本專案已經是 test-first 風格（一堆 `test_*.py`），新的整合邏輯應該延續這個慣例，不要打破。
