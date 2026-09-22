Type: research
Status: resolved

## Question

在 `onedir` 發布模式下，如何設計輕量化增量更新包（Delta Package）的製作與解壓覆蓋策略？
1. 增量更新包應包含哪些具體檔案？（例如：純 `argus` 模組 pyc/源碼、Web templates、靜態手冊，排除底層 `_internal/` 龐大庫）
2. 增量更新包預估壓縮後的體積大小為何？（能否控制在 1MB ~ 5MB 左右？）
3. CI/CD 打包流程中，如何自動化產出「完整安裝包（Full Bundle）」與「增量更新包（Delta Patch）」？

## Answer

### 1. 代碼解耦機制（解決 PyInstaller PYZ 優先載入障礙）
- **關鍵問題**：PyInstaller 預設將業務代碼編譯入 PYZ 歸檔並由 `PyiFrozenImporter` 優先載入，直接覆蓋磁碟 `.pyc` 會無效。
- **解耦架構**：
  - 在 `argus_predictor.spec` 中設定 `a.pure = [x for x in a.pure if not x[0].startswith('argus')]`，切斷 PYZ 對業務代碼的強綁定。
  - 在入口點加入 `sys.path.insert(0, os.path.join(sys._MEIPASS, 'argus.zip'))`，採用 Python 內建 `zipimport` 機制直接掛載 `_internal/argus.zip`（或 `_internal/argus/` 目錄）。

### 2. 增量更新包結構與排除邊界
- **包含內容**：
  - `_internal/argus.zip`（編譯後的 `argus` 模組 byte-code，約 100 KB）
  - `_internal/argus/web/templates/index.html`（Web UI 模板，約 50 KB）
  - `_internal/docs/user-manual/book/`（mdBook 離線手冊全站靜態檔案，約 2.3 MB）
  - `config.default.yaml`、`manifest.json` 與安全替換腳本。
- **嚴格排除內容**：
  - `_internal/torch/`、`cv2/`、`numpy/`、底層 C/C++ `.so` 動態庫與 Python 核心 runtime。

### 3. 體積測算結果
- **全應用層增量包（含完整手冊與截圖）**：未壓縮約 5.45 MB，gzip -9 壓縮後約 **2.3 MB ~ 2.6 MB**（完美落在 1MB ~ 5MB 目標區間）。
- **純代碼修復包（手冊未改動）**：壓縮後僅 **140 KB ~ 160 KB**。
- 相較於全量 Full Bundle（250MB+），體積縮減達 **99%**。

### 4. CI/CD 雙構件發布
- CI 流程一分為二：一邊產出全量 `argus_predictor-vX.Y.Z-arm64.tar.gz`（~250MB，初次安裝用），一邊提取純應用層資產封裝為 `argus_delta-vX.Y.Z-arm64.tar.gz`（~2.4MB，日常增量更新用）。

