# 03 — Detail 檢查器與全螢幕 ROI 編輯連動與端到端驗證 (Detail Inspector ROI Integration & E2E Verification)

**What to build:** 
串接右下角「全螢幕 / 編輯 ROI 區域」快捷按鈕與 Canvas 多邊形編輯器，完成變更後的表單序列化寫入 `config.yaml`、即時熱重載與全套單元測試回歸驗證。

**Blocked by:** 02（Master-Detail 串流主清單與右下方單一串流編輯器）

**Status:** ready-for-agent

- [ ] 右下方顯示選中串流之當前 ROI 警戒區狀態（`[ ROI: ACTIVE (警戒區名稱) ]` 或 `[ ROI: INACTIVE ]`）。
- [ ] 串接右下方 `[ 全螢幕 / 編輯 ROI 區域 ]` 按鈕，點擊帶入當前選中串流 Index 直接開啟 Fullscreen Canvas 劃設 ROI 多邊形。
- [ ] ROI 保存後無縫返回工作台並即時更新右下方 ROI 狀態標籤。
- [ ] 提交表單時自動序列化 Master-Detail 所有串流資料為 `streams_json` 進行後端儲存。
- [ ] 執行全套單元測試，驗證 100vh 佈局與 Master-Detail 資料持久化無回歸。
