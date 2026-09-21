# 02 — 根目錄資產與輔助腳本歸檔 (Assets, Scripts & .gitignore Relocation)

Gitea Issue: #69
Type: task
Status: resolved
Blocked by: None

## Question
如何將根目錄大型測試影片移入 `assets/test_videos/`、微型測試 fixture 移入 `tests/data/`、輔助工具腳本移入 `scripts/`，並健全 `.gitignore` 確保臨時產物不污染版本庫，同時更新相關路徑引用？

## Tasks
- [x] 將根目錄大型影片（如 `00__Video_*.avi`）移入 `assets/test_videos/`。
- [x] 將小型測試用影音（如 `test.mp4`）移入 `tests/data/test.mp4`。
- [x] 將根目錄 `ask_and_report.bat` 與 `ask_and_report.sh` 移入 `scripts/`，並修正其內部執行路徑。
- [x] 更新 `.gitignore`，納入 `temp/`、`rtsp-test/`，並針對 `tests/data/` 影音加入例外追蹤白名單（`!tests/data/*.mp4`）。
- [x] 驗證現有腳本與測試中涉及搬遷檔案之路徑運作正常。

## Answer
1. **檔案歸檔與遷移**：
   - 建立 `assets/test_videos/`，將根目錄大型影音檔 `00__Video_20240505102430_000_CLOSE.avi` 移入。
   - 建立 `tests/data/`，將微型測試影音 `test.mp4` 移入 `tests/data/test.mp4`。
   - 將根目錄輔助腳本 `ask_and_report.bat` 與 `ask_and_report.sh` 移入 `scripts/` 目錄中。
2. **路徑引用與腳本修正**：
   - 更新 `scripts/ask_and_report.bat`（加入 `pushd "%~dp0\.."`、虛擬環境與全域 python 自動 fallback）與 `scripts/ask_and_report.sh`（加入 `cd "$ROOT_DIR"` 與 python 直譯器檢查），確保從 `scripts/` 目錄或任何位置執行皆能精確定位專案根目錄之 `report_issue.py`。
   - 更新 `config.yaml` 之 `video_path` 設定為 `assets/test_videos/00__Video_20240505102430_000_CLOSE.avi`。
3. **版本控制規則維護 (`.gitignore`)**：
   - 補齊 `temp/`、`rtsp-test/` 與 `*.egg-info/` 忽略規則。
   - 針對 `tests/data/` 測試資產加入反向例外追蹤白名單 `!tests/data/*.mp4`，確保大型影片排除之同時，必要之測試 fixture 能納入版本庫。
4. **驗證**：
   - 執行 `git check-ignore` 檢驗路徑規則全部符合預期。
   - 執行全量測試套件（`python -m pytest`）272 項測試全數通過（54.53s）。
