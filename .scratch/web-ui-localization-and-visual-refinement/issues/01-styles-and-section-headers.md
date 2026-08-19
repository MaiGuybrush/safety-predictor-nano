# 01 — 樣式系統與章節標題視覺強調升級 (Styles, Section Headers & Accent Badges)

**What to build:**
重構前端 CSS 樣式系統，新增左側科技發光飾條與 `.section-badge` 序號圓角徽章；將主面板框架標題（`系統參數設定`）、四大章節標題（`01 推論效能參數`、`02 全域模型來源配置`、`03 運作模式與串流清單`、`04 進階系統參數`）以及右側檢查器標題（`串流詳細設定`）全面移除中括號與雙斜線，換上全新結構化視覺呈現。

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] 新增 `.section-badge`、`.section-title-left` 與左側發光飾條（Cyber Accent Border）CSS 樣式。
- [ ] 將左側面板框線標題 `[ SYS_CONFIG_PARAMETERS ]` 改為 `系統參數設定`。
- [ ] 將章節 1 改為 `<span class="section-badge">01</span> 推論效能參數`。
- [ ] 將章節 2 改為 `<span class="section-badge">02</span> 全域模型來源配置`。
- [ ] 將章節 3 改為 `<span class="section-badge">03</span> 運作模式與串流清單`。
- [ ] 將章節 4 改為 `<span class="section-badge">04</span> 進階系統參數`。
- [ ] 將右側檢查器標題 `[ STREAM_DETAIL_INSPECTOR ]` 改為 `串流詳細設定`。
- [ ] 更新 `test_web_ui_config_save.py` 驗證標籤與 CSS 類別。
