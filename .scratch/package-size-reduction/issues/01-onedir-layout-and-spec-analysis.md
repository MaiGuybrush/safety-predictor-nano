Type: research
Status: resolved

## Question

分析現有 `argus_predictor.spec` 與專案結構，探討從 PyInstaller `--onefile` 改為 `--onedir` 後的目錄布局契約：
1. 輸出目錄中哪些檔案與函式庫屬於底層 Base Runtime（如 `_internal/` 內的 Python、PyTorch、OpenCV、C++ 動態庫）？體積大約佔比為何？
2. 應用層的代碼（`argus/`）、前端模板（`src/argus/web/templates`）、設定檔（`config.yaml`）以及手冊（`docs/user-manual/book`）在 `onedir` 模式下是如何存放與被載入的？
3. 初次安裝包在 `onedir` 下以 tar.gz / zip 打包後的大小預估為何？

## Answer

### 1. Spec 規格與生成目錄結構
- 將 `argus_predictor.spec` 中的 `EXE(...)` 加入 `exclude_binaries=True`，並改以 `coll = COLLECT(...)` 聚合產出目錄 `dist/argus_predictor/`。
- PyInstaller 6.x 標準布局為：
  - `dist/argus_predictor/argus_predictor`（僅數十 KB 的引導二進位 ELF 檔）。
  - `dist/argus_predictor/_internal/`（存放所有 Python runtime、`.so` 動態函式庫、第三方套件與靜態資源）。

### 2. 路徑相容性驗證
- **`sys._MEIPASS`**：在 `onedir` 模式下依然存在，且自動指向 `_internal/` 目錄。
- 專案程式碼中對手冊 `MANUAL_DIR`、Flask `templates/`、`ums-api-config.json` 的路徑解析均依賴 `sys._MEIPASS`，**100% 無縫相容**。
- `recordings/` 與 `logs/` 則依賴 `sys.executable` 所在目錄，會自動生成於外部主目錄，不會寫入 `_internal/`。
- **注意項**：`config.yaml` 應作為外部出廠範本（`config.default.yaml`）獨立放置於主目錄，不可僅依賴打包進 `_internal/`，以符合 ADR-019 不可覆蓋使用者配置之安全規範。

### 3. 體積佔比分析（Raspberry Pi 5 ARM64 預估）
- **底層 Base Runtime（佔比 > 99.4%）**：
  - PyTorch (`torch`)：~750MB (壓縮後 ~180MB，佔 72%)
  - OpenCV (`cv2`)：~100MB (壓縮後 ~28MB，佔 9.6%)
  - NumPy / SciPy / PIL：~85MB (壓縮後 ~24MB，佔 8.2%)
  - Python / C++ 動態庫 / 其他：~85MB (壓縮後 ~23MB)
  - **初次安裝完整包體積**：未壓縮約 1.02 GB，tar.gz 壓縮後約 **256 MB**。
- **應用層與前端資源（佔比 < 0.6%）**：
  - `argus` 模組 Python 邏輯：~350 KB
  - Web UI Dashboard (`index.html`)：~210 KB
  - 離線手冊全站 (`docs/user-manual/book`)：~5.0 MB（若排除 Mermaid.js 僅 2.4 MB）
  - **應用層增量包體積**：未壓縮約 5.5 MB，壓縮後僅約 **1.5 ~ 1.6 MB**（若手冊未變動，純代碼僅 **150 KB**）。

