Status: ready-for-human

# 07 — 【Backlog】ROI / 危險區域設定畫面

**What to build:** 目前 `EventMeta.roi`（spec 必填欄位）用整張畫面當 placeholder（`[[0,0],[1,0],[1,1],[0,1]]`），因為專案完全沒有 ROI / 危險區域的概念（純物件偵測，`config.yaml` 沒有 zone schema，Web UI 沒有畫框介面）。

真正要支援「畫一塊危險區域，只有物件進到這塊區域才算 zone_intrusion 事件」，至少需要：

- [ ] `config.yaml` schema 設計：per-stream 或全域的 ROI 多邊形定義（座標系統、跟 `streams[]` 的關係）
- [ ] Web UI 新增畫框介面（比照 `templates/index.html` 現有表單風格，新增 canvas 互動畫多邊形）
- [ ] `event_producer.py` 的 `EventMeta.roi` 改吃真實設定，而不是寫死 placeholder
- [ ] 判斷「偵測框是否落在 ROI 內」的幾何邏輯（目前系統完全沒有，需要新增）

**Blocked by:** None，但依賴性質上獨立、範疇夠大，不併進 `argus-eventlog-integration` 這次的實作範圍（見 `docs/adr/ADR-014-argus-eventlog-integration.md`「取捨與風險」段）。

**Status 說明：** `ready-for-human` —— 需要先決定 ROI 的產品需求（哪些 stream 需要、畫框互動的 UX 期望），不是單純規格明確的實作任務。

## Comments

- 建立於本次 `/grill-me`（argus-eventlog 整合）session，使用者要求把這個明確排除的範圍記錄成代辦 issue。
