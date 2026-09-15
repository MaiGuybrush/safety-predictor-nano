# 03 — 打包規格更新、範例設定檔與使用者手冊同步

## Parent
#55 Feature: UMS 廠區化配置與網卡自動偵測機制
Gitea Ticket: #58

## What to build
更新 PyInstaller 二進位打包規格，將 ums-api-config.json 納入封裝清單；更新 config.yaml.example 展示 ums_fab 欄位並移除舊有 ums_base_urls 範例；同步更新 docs/user-manual/ 使用者操作手冊與相關說明截圖。

## Acceptance criteria
- [x] PyInstaller 打包指令與腳本加入 --add-data "ums-api-config.json:."。
- [x] config.yaml.example 正確展示 ums_fab 範例與註解說明，不再出現 ums_base_urls。
- [x] 更新 docs/user-manual/ 系統設定與 UMS 廠區章節內容，說明廠區選擇與開機網卡自動偵測特性。
- [x] 執行 mdBook 建置確保操作手冊能正常編譯無錯誤。

## Blocked by
- #57 (Ticket 02: Web UI 廠區下拉選單、唯讀端點預覽與連線測試整合)
