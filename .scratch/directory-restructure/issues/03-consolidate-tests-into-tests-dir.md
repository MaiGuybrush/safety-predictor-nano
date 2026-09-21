# 03 — 測試套件全量收斂至 tests/ 與階層化整理 (Consolidate Tests into tests/)

Gitea Issue: #70
Type: task
Status: resolved
Blocked by: 01, 02

## Question
如何將根目錄 30+ 個 `test_*.py` 搬移至 `tests/`，依領域維度組織為 `tests/unit/`、`tests/integration/`、`tests/e2e/` 與 `tests/fixtures/`，並更新相對路徑引用，確保全數測試綠燈通過？

## Tasks
- [x] 於 `tests/` 建立 `unit/`, `integration/`, `e2e/`, `fixtures/` 子目錄。
- [x] 將根目錄的所有 `test_*.py` 測試檔案依領域職責搬移至對應子目錄。
- [x] 將 `mock_argus_agent.py` 移入 `tests/fixtures/` 並更新相關測試的 import 與使用。
- [x] 更新搬遷後測試中的相對檔案路徑（如 `config.yaml`、測試資源等）。
- [x] 執行 `pytest` 驗證所有測試全數通過且進程正常結束。

## Answer
1. **目錄結構建立與模組初始化**：
   - 在 `tests/` 下建立四個階層子目錄：`unit/`、`integration/`、`e2e/`、`fixtures/`。
   - 分別在各子目錄建立 `__init__.py`，使測試套件模組結構化，避免跨目錄命名空間污染與衝突。

2. **全量測試與 Fixture 搬遷歸檔**：
   - 將根目錄 34 個 `test_*.py` 與原 `tests/` 下 6 個測試，共 40 個測試檔案分類搬移：
     - `tests/e2e/` (4 個)：`test_e2e_issue_reporting.py`, `test_e2e_pts_snapshots_retention.py`, `test_web_ui_floating_save_e2e.py`, `test_compliance_e2e.py`。
     - `tests/integration/` (14 個)：Web UI API 端點、串流傳輸（MJPEG/SSE）、Heartbeat 服務整合、執行期韌性恢復等測試。
     - `tests/unit/` (22 個)：演算法、配置管理、日誌、推論引擎封裝、UMS 客戶端等單元測試。
   - 將模擬伺服器 `mock_argus_agent.py` 遷移至 `tests/fixtures/mock_argus_agent.py`，並於 `tests/fixtures/__init__.py` 提供匯出。

3. **環境路徑與組態設定調整**：
   - 更新 `pytest.ini`，設定 `testpaths = tests` 與 `pythonpath = .`，確保全域正確定位測試目錄與根目錄模組。
   - 更新 `tests/conftest.py`，加入專案根目錄至 `sys.path` 頂端防護。
   - 更新搬遷至二級子目錄測試中的 `sys.path` 相對路徑由 `..` 改為 `../..`。

4. **驗證**：
   - 執行 `python -m pytest`，全套 272 項測試在 `tests/` 階層結構下全數通過（272 passed, 48.26s），進程順暢退出無懸掛。
