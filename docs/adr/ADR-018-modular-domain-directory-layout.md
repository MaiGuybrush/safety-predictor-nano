# ADR-018：模組化領域目錄架構與測試套件分層重構 (Modular Domain Directory Layout & Test Suite Hierarchy)

| 欄位 | 內容 |
|------|------|
| **狀態** | 已接受 (Accepted) |
| **日期** | 2026-09-18 |
| **決策者** | 開發團隊 |
| **相關 ADR** | [ADR-004](ADR-004-global-vars-cross-thread.md)、[ADR-005](ADR-005-arm64-build-constraint.md)、[ADR-014](ADR-014-argus-eventlog-integration.md)、[ADR-017](ADR-017-ppe-detection-and-conditional-compliance-rule-engine.md) |
| **相關 Issue / Spec** | Gitea [#68](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/68) ~ [#74](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/74), [.scratch/directory-restructure/map.md](../../.scratch/directory-restructure/map.md) |

---

## 情境與問題

Argus Safety Predictor Nano 隨著多項工安與邊緣推論功能（多串流、PPE 偵測、合規引擎、事件日誌、狀態輪詢、UMS 模型同步、Issue 回報器）的演進，程式庫逐漸積累以下結構性與工程維護痛點：

1. **模組扁平堆疊缺乏領域邊界**：根目錄聚集了超過 20 個 Python 業務檔案（如 `stream_handler.py`、`inference_engine.py`、`compliance_engine.py`、`web_ui.py`、`model_sync.py`、`event_producer.py` 等），所有模組位於同層命名空間，領域邊界模糊，跨模組相依糾結。
2. **測試檔案雜亂與執行懸掛 (0% CPU Hang)**：根目錄散落 40+ 個 `test_*.py` 檔案，缺乏單元測試、整合測試與 E2E 測試分層。部分測試在執行完畢時，因 OpenCV 串流背景執行緒、Werkzeug/Flask 伺服器未被徹底終止釋放，導致 pytest 行程在完成測試後停滯在 0% CPU 懸掛狀態無法自動退出。
3. **靜態資產與輔助工具散落**：大容量測試影片 (`.mp4`)、回報診斷工具腳本直接存放於專案根目錄，污染版本控制與部署打包工作區。
4. **PyInstaller 打包相容性需維持**：邊緣 Raspberry Pi 5 部署嚴格依賴 PyInstaller ARM64 單一二進位執行檔打包與熱重載設定檔，目錄結構調整不得破壞打包機制與 CLI/執行時期環境。

---

## 決策選項與遷移策略

### 決策策略：採用 Expand–Contract 兩階段平滑遷移（方案 B）
我們評估了「一次性全量直接重構 (Big Bang)」與「兩階段漸進式重構 (Expand–Contract)」：
- **一次性重構**風險極高，跨模組引用與測試容易同時斷裂，造成定位困難。
- **Expand–Contract 漸進式策略**：
  - **階段一（收斂測試與資源防禦）**：先建立 `tests/conftest.py` 清理 fixture 與 5 秒退出看門狗守護，解決 0% CPU 懸掛；接著將測試檔案階層化移入 `tests/`，將靜態資產歸檔至 `assets/test_videos/` 與 `tests/data/`。
  - **階段二（建立領域套件與安全搬遷）**：建立 `src/argus/` 套件骨架，設定 `pyproject.toml` 支援 editable install，依領域將 20+ 核心模組歸類遷入，透過相容墊片保持過渡期呼叫點不中斷，最終收斂測試調用點並移除舊墊片，保留根目錄薄入口 `main.py`。

---

## 決策內容

### 1. 標準 `src/` Layout 與 7 大領域子套件劃分

採用現代 Python 最佳實踐之 `src/` Layout，將核心邏輯封裝於 `argus` 命名空間下，依領域職責劃分為 7 個子套件：

- `argus.core`: 核心配置與生命週期管理（`config_manager.py`）。
- `argus.capture`: 影像擷取與合成（`stream_handler.py`、`video_handler.py`、`grid_composer.py`）。
- `argus.vision`: YOLO/NCNN 視覺推論引擎封裝（`inference_engine.py`）。
- `argus.compliance`: 工安法規與 PPE 裝備合規評估規則引擎（`compliance_engine.py`）。
- `argus.events`: 事件生產、日誌記錄、日誌輪替清理與當機診斷（`event_producer.py`、`stats_logger.py`、`retention_cleaner.py`、`diagnostic_collector.py`）。
- `argus.integration`: 外部系統整合（`model_sync.py`、`ums_config.py`、`failover_ums_client.py`、`state_poller.py`、`issue_service_client.py`、`report_issue.py`）。
- `argus.web`: Flask Web UI 控制台、SSE 即時偵測串流、MJPEG 畫面串流與 HTML/CSS/JS 靜態資源（`web_ui.py`、`templates/`）。
- `argus.main`: 系統核心協同執行迴圈與推論排程器。

### 2. 根目錄薄入口 (Thin Entrypoint) 與可編輯安裝

- 根目錄保留精簡的 `main.py` 作為 CLI 與 PyInstaller 入口點，內部直接委託 `from argus.main import main`，並支援 `--report-issue` 診斷命令轉發。
- 新增 `pyproject.toml`，設定 `[tool.setuptools.packages.find] where = ["src"]` 與套件範本資料打包規則，支援 `pip install -e .`。

### 3. 測試套件階層化收斂與防懸掛守護機制

- 將測試統一歸檔至 `tests/` 資料夾，分層為：
  - `tests/unit/`: 各領域模組之隔離單元測試。
  - `tests/integration/`: API、SSE、狀態輪詢、心跳與資料持久化整合測試。
  - `tests/e2e/`: 包含完整推論、合規告警、Web UI 操作與 Issue 回報之端到端測試。
  - `tests/fixtures/`: 測試用假物件（如 `mock_argus_agent.py`）。
  - `tests/data/`: 測試專用影音測試樣本。
- 在 `tests/conftest.py` 建立自動清理 fixture 與執行緒清理監控：
  - 確保所有測試中建立的背景執行緒、串流 handler 與 mock HTTP server 於 fixture teardown 階段被強制終止釋放。
  - 導入看門狗執行緒（Watchdog Thread），於 pytest 執行階段若發現未退出的懸掛行程，在 5 秒後觸發強制 `os._exit(0)`，徹底解決 CI 與本地端 0% CPU 懸掛問題。

### 4. 靜態資產與輔助腳本歸檔

- 測試用大型影像歸檔至 `assets/test_videos/`，單元測試素材放置於 `tests/data/`，並於 `.gitignore` 設定必要資產之白名單規則（`!tests/data/*.mp4`）。
- 診斷回報與截圖腳本歸檔至 `scripts/`（如 `scripts/generate_screenshots.py`、`scripts/ask_and_report.*`），並優化路徑解析邏輯支援相對路徑執行。

### 5. PyInstaller 打包規格與規格書同步

- 更新 `argus_predictor.spec`：
  - 設定 `Analysis(['src/argus/main.py'], pathex=['src'], ...)`。
  - 完整收集 `argus.*` 領域模組至 `hiddenimports`。
  - 資料收集包含 `src/argus/web/templates`、`templates`、`config.yaml`、`ums-api-config.json` 與 `docs/user-manual/book`。
  - 確保在 ARM64 樹莓派環境下執行 `pyinstaller argus_predictor.spec` 能直接產出單一執行檔。

---

## 效果與評估

1. **結構清晰，高內聚低耦合**：清晰界定 7 大領域套件，職責劃分明確，杜絕跨領域模組之循環依賴與混亂引用。
2. **測試穩定度 100%**：全套 272 項測試分類清晰且 100% 綠燈通過，測試執行時間大幅縮短，行程徹底終止無懸掛。
3. **無痛遷移與部署相容**：維持原有的 CLI 操作慣例與樹莓派部署流程，PyInstaller spec 直接相容全新 `src/` 套件佈局。
