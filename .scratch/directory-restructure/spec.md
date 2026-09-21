# Spec: 專案目錄結構領域重整 (Directory Restructure)

## 概述
重整 `safety-predictor-nano` 專案目錄結構，遵循 DDD 領域驅動架構與現代 Python `src/` Layout。解決根目錄混亂、測試套件無序與行程退出死鎖等問題。

## 遷移目標架構
- `src/argus/`: 核心領域套件
  - `core/`: 組態管理與全域狀態
  - `capture/`: RTSP/影片串流擷取與解碼
  - `vision/`: YOLO/NCNN 推論封裝
  - `compliance/`: PPE 安全合規與規則引擎
  - `events/`: 事件生產、審計與診斷
  - `integration/`: UMS 平台介接與模型同步
  - `web/`: Web UI、MJPEG/SSE 串流與 REST API
- `tests/`: 階層化測試套件
  - `conftest.py` & `pytest.ini`: 資源自動清理與超時守護
  - `unit/`, `integration/`, `e2e/`, `fixtures/`, `data/`
- `scripts/`: 自動化運維與診斷腳本
- `assets/`: 大型測試媒體
- 根目錄維持乾淨：僅留 `main.py`（薄入口）、組態檔、`argus_predictor.spec`、文件與 `pyproject.toml`。

## 遷移策略
採用 **Expand–Contract** 兩階段漸進模式：
1. **Phase 1**: 收斂測試與資產，建立 `pytest.ini` 與執行緒隔離清理。
2. **Phase 2**: 建立 `src/argus` 套件骨架，轉移核心模組並改寫 import，最後移除過渡期轉發墊片並更新 PyInstaller 與文件。
