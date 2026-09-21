# 04 — 建立 src/argus/ 套件骨架與相容墊片 (Package Skeleton & Compatibility Shims - Expand)

Gitea Issue: #71
Type: task
Status: resolved
Blocked by: 03

## Question
如何建立 `src/argus/` 核心套件與各領域子套件目錄骨架，配置 `pyproject.toml` 支援 editable install，排除打包產物並建立過渡期轉發墊片？

## Tasks
- [x] 建立 `src/argus/` 及其子目錄 `core/`, `capture/`, `vision/`, `compliance/`, `events/`, `integration/`, `web/` 與對應 `__init__.py`。
- [x] 建立 `pyproject.toml`，定義專案元數據與依賴，支援 editable install。
- [x] 更新 `.gitignore` 加入 `*.egg-info/`、`*.whl` 等打包中間產物。
- [x] 在 `src/argus/web/` 建立 `templates/` 目錄並移入 Web UI 模板。
- [x] 執行 `pip install -e .` 或 `python -c "import argus"` 驗證套件可正確被 Python 環境辨識。

## Answer
1. 建立 `src/argus/` 核心套件及 7 個領域子套件骨架：`core/`, `capture/`, `vision/`, `compliance/`, `events/`, `integration/`, `web/`，皆附帶對應的領域描述 `__init__.py`。
2. 建立標準 PEP 517/621 `pyproject.toml`，採用 setuptools build-backend，明確聲明依賴與套件資料 (`argus.web` templates)。
3. 更新 `.gitignore` 補齊 `*.whl` 等打包中繼產物排除規則。
4. 建立 `src/argus/web/templates/` 並置入 `index.html`，同時保留根目錄 `templates/` 確保現行測試與舊路徑相容性。
5. 執行 `pip install -e . --no-deps` 成功以 editable 模式安裝 `safety-predictor-nano 1.0.0`，並經 `python -c "import argus..."` 驗證所有領域命名空間可直接被 Python 環境解析。
6. 同步更新 `pytest.ini` 的 `pythonpath = . src`，全套 272 個測試通過 (100% 綠燈)。
