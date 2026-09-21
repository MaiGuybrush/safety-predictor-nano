# 07 — 打包設定、建置腳本與領域文件同步 (PyInstaller Spec & Domain Docs Alignment)

Gitea Issue: #74
Type: task
Status: resolved
Blocked by: 06

## Question
如何更新 `argus_predictor.spec` 使其相容 `src/argus` 套件佈局，撰寫 ADR-018，並同步校正 `AGENTS.md` 與 `README.md`？

## Tasks
- [x] 更新 `argus_predictor.spec` 中的 entrypoint（指向 `src/argus/main.py`）、`pathex`（納入 `src`）與資源收集清單。
- [x] 撰寫 `docs/adr/ADR-018-modular-domain-directory-layout.md` 記錄目錄重構與領域劃分緣由。
- [x] 更新 `AGENTS.md`：校正 Key Directories、移除陳舊的「無測試框架」描述、更新 PyInstaller 打包參數。
- [x] 更新 `README.md` 說明最新的專案目錄結構與啟動方式。
- [x] 執行語法與乾跑測試，確保二進位打包規格符合 ARM64 建置要求。

## Answer
1. **PyInstaller Spec 更新 (`argus_predictor.spec`)**:
   - `Analysis` 入口點更新為 `['src/argus/main.py']`，並加入 `pathex=['src']`，確保二進位打包時原生解析 `argus` 命名空間。
   - `datas` 補齊 `('src/argus/web/templates', 'argus/web/templates')`、`('templates', 'templates')`、`('config.yaml', '.')`、`('ums-api-config.json', '.')`、`('docs/user-manual/book', 'docs/user-manual/book')`。
   - `hiddenimports` 全面收斂至 7 大領域模組（`argus.core.config_manager`, `argus.capture.*`, `argus.vision.*`, `argus.compliance.*`, `argus.events.*`, `argus.integration.*`, `argus.web.*`）。
   - 經 `python -m py_compile argus_predictor.spec` 語法檢驗完全正確。
2. **產出架構決策紀錄 (ADR-018)**:
   - 建立 [ADR-018：模組化領域目錄架構與測試套件分層重構 (Modular Domain Directory Layout & Test Suite Hierarchy)](file:///D:/Projects/argus/safety-predictor-nano/docs/adr/ADR-018-modular-domain-directory-layout.md)。
   - 詳細記錄情境問題、兩階段 Expand–Contract 遷移策略、7 大領域套件職責、測試分層與防懸掛看門狗設計，並更新 `docs/adr/README.md` 索引表。
3. **校正 `AGENTS.md` 領域指南**:
   - 更新 Architecture & Data Flow 路徑為 `src/argus/*`。
   - 更新 Key Directories 詳列 7 大領域套件、`tests/`、`scripts/`、`docs/`、`assets/`。
   - 移除陳舊的「無測試框架」描述，補充完整 Pytest 階層與 conftest 資源清理守護說明。
   - 更新 PyInstaller 打包指令與重要檔案清單。
4. **校正 `README.md` 開發與部署說明**:
   - 新增完整專案樹狀結構圖與職責簡介。
   - 於快速啟動說明中加入 `pip install -e .` 與 `pytest` 步驟。
   - 更新 PyInstaller 單一二進位與 `--onedir` 打包參數（納入 `--paths src` 與 `src/argus/main.py`），推薦直接使用 `pyinstaller argus_predictor.spec`。
5. **完整驗證**:
   - 執行全套 `pytest -q`，272 項測試 100% 綠燈通過（耗時 52.68 秒）。

