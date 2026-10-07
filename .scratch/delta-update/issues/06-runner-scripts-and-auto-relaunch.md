## Parent

#90 (自動更新功能需求)

## What to build

建立完整的外層守護機制。新增專案根目錄 `run.bat`，同步更新 `scripts/run.sh`，捕捉 Exit 42 時呼叫 `install.py` 執行置換並自動拉起新版；於 `main.py` 實作 `ARGUS_MANAGED_RUNNER` 環境變數感知與透明自動轉發（Auto-Relaunch），防止操作員繞過守護腳本。

## Acceptance criteria

- [ ] 根目錄新增 `run.bat`，提供 `ARGUS_MANAGED_RUNNER=1` 注入、捕捉 Exit 42 呼叫 `install.py --delta updates/staging`，以及崩潰時呼叫 `--rollback`
- [ ] 同步修訂 `scripts/run.sh`，注入 `ARGUS_MANAGED_RUNNER=1`，於 Exit 42 時呼叫 `install.py` 置換並重啟
- [ ] 於 `main.py` 入口檢測 `ARGUS_MANAGED_RUNNER`，若未託管且未帶 `--allow-direct` 則自動轉交 `run.bat` / `run.sh` 並退出當前進程
- [ ] 實測直接執行 `python main.py` 能成功自動委派至守護腳本運行

## Blocked by

- #91 (05 — 建立跨平台獨立安裝與回滾執行器 scripts/install.py)
