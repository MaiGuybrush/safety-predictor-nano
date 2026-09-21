# Effort: 專案目錄結構領域重整 (Directory Restructure)

## Destination

將 `safety-predictor-nano` 重整為遵循 DDD 領域分層與標準 `src/` Layout 的架構，收斂 34 個散落在根目錄的測試與 20+ 個核心業務模組，修復測試行程退出時因執行緒懸掛導致的 0% CPU 問題，保持 PyInstaller 單一二進位部署相容性與全套測試 100% 綠燈通過。

## Notes

- **Domain**: Argus Safety Predictor Nano（邊緣端 Raspberry Pi 5 目標偵測、Flask Web UI、PyInstaller ARM64 單一二進位執行檔）。
- **Issue Tracker**: 本專案遵循 `.scratch/directory-restructure/issues/` 之票券規範；Gitea 專案為 `guy.mai/safety-predictor-nano`，相關 Issues 為 [#68](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/68) ~ [#74](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/74)。
- **架構風格**: 採現代 Python `src/argus/` 結構，包含 `core/`, `capture/`, `vision/`, `compliance/`, `events/`, `integration/`, `web/`。
- **遷移策略**: 採 Expand–Contract 兩階段平滑遷移，根目錄保留過渡期 shims 與最終薄入口 `main.py`。
- **測試防死鎖**: 透過 `tests/conftest.py` 與 `pytest.ini` 導入執行緒清理與超時守護。

## Decisions so far

- 採用方案 B（兩階段漸進式遷移：先收斂測試與資產，再重構 `src/` 領域架構）。
- 保留根目錄薄入口 `main.py` 轉發至 `argus.main.main`，維持 CLI 與 PyInstaller 相容性。
- 更新 `.gitignore` 排除 `temp/`, `rtsp-test/`, `*.egg-info/`，並加入 `tests/data/` 測試資產白名單規則。
- [01 — 測試執行緒隔離與超時守護 (Pytest Teardown & Timeout Guard)](issues/01-pytest-teardown-and-timeout-guard.md) — 導入 `tests/conftest.py` 資源清理 fixture 與 5 秒退出守護看門狗，修復 `StreamHandler`/`ServerThread` daemon 屬性，徹底解決 0% CPU 懸掛問題。
- [02 — 根目錄資產與輔助腳本歸檔 (Assets, Scripts & .gitignore Relocation)](issues/02-assets-scripts-and-gitignore-relocation.md) — 大型影片歸檔至 `assets/test_videos/`，測試影音歸檔至 `tests/data/`，輔助回報腳本遷移至 `scripts/` 並支援相對路徑解析，補齊 `.gitignore` 排除規則與白名單。
- [03 — 測試套件全量收斂至 tests/ 與階層化整理 (Consolidate Tests into tests/)](issues/03-consolidate-tests-into-tests-dir.md) — 建立 `tests/unit/`, `tests/integration/`, `tests/e2e/`, `tests/fixtures/`，將 40 個測試檔案與 `mock_argus_agent.py` 全量分類歸檔，更新 `pytest.ini` 與模組搜尋路徑，全套 272 項測試全數綠燈通過。
- [04 — 建立 src/argus/ 套件骨架與相容墊片 (Package Skeleton & Compatibility Shims - Expand)](issues/04-package-skeleton-and-shims.md) — 建立 `src/argus/` 及 7 個領域子套件骨架與 `__init__.py`，配置 `pyproject.toml` 支援 editable install，建立 `src/argus/web/templates/`，通過全套 272 項測試。
- [05 — 領域業務模組搬遷與內部匯入重構 (Migrate Domain Modules)](issues/05-migrate-domain-modules.md) — 20+ 個核心模組遷移至 `src/argus/` 下 7 大領域子套件，內部引用全面改寫為 `argus.*` 命名空間，根目錄保留 18 個 `sys.modules` 相容墊片，全套 272 項測試全數綠燈通過。
- [06 — 測試與工具鏈調用點更新並刪除舊相容墊片 (Migrate Test Callers & Contract)](issues/06-migrate-test-callers-and-contract.md) — 全面更新 41 個測試檔案與 scripts 工具呼叫直接匯入 `argus.*` 領域模組，移除根目錄 17 個過渡期轉發墊片並建立標準薄入口 `main.py`，全套 272 項測試 100% 綠燈通過。
- [07 — 打包設定、建置腳本與領域文件同步 (PyInstaller Spec & Domain Docs Alignment)](issues/07-pyinstaller-spec-and-domain-docs.md) — 更新 `argus_predictor.spec`（pathex/entrypoint/datas/hiddenimports）、撰寫 ADR-018，並同步校正 `AGENTS.md` 與 `README.md`，全套 272 項測試持續 100% 綠燈通過。

## Fog

<!-- 當前所有規劃之核心架構與遷移切分已明確轉化為票券，無殘留模糊需求 -->

## Issues

- [x] [01 — 測試執行緒隔離與超時守護 (Pytest Teardown & Timeout Guard)](issues/01-pytest-teardown-and-timeout-guard.md) (Gitea [#68](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/68))
- [x] [02 — 根目錄資產與輔助腳本歸檔 (Assets, Scripts & .gitignore Relocation)](issues/02-assets-scripts-and-gitignore-relocation.md) (Gitea [#69](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/69))
- [x] [03 — 測試套件全量收斂至 tests/ 與階層化整理 (Consolidate Tests into tests/)](issues/03-consolidate-tests-into-tests-dir.md) (Gitea [#70](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/70))
- [x] [04 — 建立 src/argus/ 套件骨架與相容墊片 (Package Skeleton & Compatibility Shims - Expand)](issues/04-package-skeleton-and-shims.md) (Gitea [#71](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/71))
- [x] [05 — 領域業務模組搬遷與內部匯入重構 (Migrate Domain Modules)](issues/05-migrate-domain-modules.md) (Gitea [#72](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/72))
- [x] [06 — 測試與工具鏈調用點更新並刪除舊相容墊片 (Migrate Test Callers & Contract)](issues/06-migrate-test-callers-and-contract.md) (Gitea [#73](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/73))
- [x] [07 — 打包設定、建置腳本與領域文件同步 (PyInstaller Spec & Domain Docs Alignment)](issues/07-pyinstaller-spec-and-domain-docs.md) (Gitea [#74](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/74))
