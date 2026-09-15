# 01 — 後端 UMS 廠區組態管理與網卡 IP 自動偵測引擎

## Parent
#55 Feature: UMS 廠區化配置與網卡自動偵測機制
Gitea Ticket: #56

## What to build
實作集中式 UMS API 組態檔讀取機制、網卡 IPv4 介面自動掃描與 domainDefine 網段前綴匹配演算法。當系統啟動初始化且設定檔未配置 ums_fab 時，自動偵測所在廠區（未命中則為 oa）並立即持久化寫回設定檔，同時清除舊有 ums_base_urls 欄位；ConfigManager 根據 ums_fab 透明提供端點清單。

## Acceptance criteria
- [x] 支援優先讀取外部 ums-api-config.json，封裝環境下自動 fallback 載入內建打包組態。
- [x] 提供網卡 IPv4 自動列舉與 domainDefine 比對邏輯，嚴格前綴匹配（prefix + '.'），多網卡命中取首個，皆未命中預設為 oa。
- [x] 啟動初始化若 ums_fab 缺失，自動偵測廠區並立即將 ums_fab 寫入 config.yaml，同時清理舊版 ums_base_urls。
- [x] ConfigManager.get_ums_base_urls() 能根據 ums_fab 正確映射取得端點列表。
- [x] 新增完整單元測試驗證自動偵測、持久化與端點解析邏輯。

## Blocked by
None — can start immediately.
