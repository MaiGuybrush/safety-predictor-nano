# 02 — --onedir 封裝結構、安裝更新腳本 (install.sh) 與啟動腳本設計

Type: research
Status: resolved
Blocked by: None

## Question

針對方案 C (`--onedir`) 產生的 `argus_predictor/` 目錄與使用者手動執行情境，發布壓縮包（`.tar.gz`）應具備何種目錄層級結構？`install.sh` 與啟動 Shell 腳本（`run.sh` / `start.sh`）該如何撰寫，以處理初次安裝、解壓升級、動態保留使用者的 `config.yaml`、本機模型檔 `*.pt` 與日誌目錄，並確保 Linux 執行權限（`chmod +x`）正確？

## Investigation Scope

1. **封包結構規範**:
   - 探討上傳至平台的 `.tar.gz` 內層結構：是直接包含 `argus_predictor/` 目錄，抑或是包含安裝腳本與載荷？
   - 範例結構規劃：
     ```text
     argus_predictor-vX.Y.Z-arm64.tar.gz
     ├── install.sh             # 安裝/升級處理入口腳本
     ├── run.sh                 # 便於使用者日常啟動/守護的 Shell 腳本
     └── payload/               # 或直接為 argus_predictor/ 目錄
         ├── argus_predictor    # PyInstaller 產出之核心二進位
         ├── _internal/         # 依賴庫目錄（Python 3.10+ onedir 結構）
         ├── config.default.yaml# 預設配置範本（不得直接覆蓋使用者已自訂之 config.yaml）
         └── ...
     ```
2. **`install.sh` 邏輯實作規範**:
   - 初次安裝判斷：若目標目錄不存在，直接部署並自 `config.default.yaml` 產生初始 `config.yaml`。
   - 升級模式（Update）：
     - 偵測目標運行目錄。
     - 備份既有工作目錄至 `argus_predictor_bak/`。
     - 解壓覆蓋主程式與依賴二進位。
     - 智慧合併或保留既有 `config.yaml`、`models/` 模型權重檔與 `logs/` 歷史日誌，避免覆蓋造成資料遺失。
     - 自動設定 `chmod +x` 權限。
3. **啟動 Shell 腳本 (`run.sh`) 設計**:
   - 提供標準啟動命令封裝，設定必要環境變數（如 `LD_LIBRARY_PATH` 或工作目錄鎖定），避免使用者於非程式目錄下執行引發 ADR-005 之找不到 `config.yaml` 錯誤。

## Answer

1. **封包層級結構規範**：
   - 採用單一外層版本目錄防止 tar bomb：`argus_predictor-v{VERSION}-arm64.tar.gz`。
   - 外層包含 `install.sh`、`run.sh`、`version.txt` 與 `checksums.sha256`。
   - 核心載荷收攏於 `payload/`（內含 `argus_predictor` 主程式、`_internal/` 動態庫與靜態資源、出廠範本 `config.default.yaml` 與 `ums-api-config.json`）。

2. **安裝更新腳本 (`install.sh`)**：
   - **模式判定**：目標目錄若不存在 `argus_predictor` 則為 Fresh Install（建立初始 `config.yaml`）；若存在則為 Upgrade 模式。
   - **零資料遺失與自動備份**：升級時將運行目錄備份至 `argus_predictor_bak/`（`models/` 採 `cp -al` 硬連結秒級備份，不佔額外空間）；嚴格保留既有 `config.yaml`、`models/` 與 `logs/`，僅更新 `config.default.yaml` 供差異比對。
   - **非互動模式**：提供 `-y` / `--non-interactive` 旗標，自動終止舊 PID、置換目錄並自動賦予 `chmod +x` 權限，供 Ticket 03 背景更新排程直接呼叫。
   - **動態庫安全置換**：`_internal/` 採移至 `.old` 後建立新目錄的兩階段清理，避免直接覆蓋記憶體中載入的 `.so` 引發崩潰。

3. **啟動 Shell 腳本 (`run.sh`)**：
   - **工作目錄強制鎖定**：以 `realpath` 強制切換 CWD 至程式所在目錄，徹底遵循 ADR-005 避免找不到 `config.yaml` 錯誤。
   - **RPi 5 最佳化環境變數**：注入 `PYTHONUNBUFFERED=1`、`OPENCV_LOG_LEVEL=ERROR`、`OPENCV_FFMPEG_CAPTURE_OPTIONS="rtsp_transport;tcp"`、`OMP_NUM_THREADS=4`、`MALLOC_ARENA_MAX=2` 與 `LD_LIBRARY_PATH`。
   - **行程替換 (`exec`)**：使用 `exec ./argus_predictor "$@"` 取代 Shell 進程，完整轉發命令列引數並直通 POSIX 終止信號。

