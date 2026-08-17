# 03 — Web UI 分區卡片與進階參數版面重構 (Web UI Layout & Advanced Parameters Section)

**What to build:** 
重構前端 HTML 與 CSS 版面結構，建立全域核心效能區、全域模型來源區、運作模式與來源區，以及可摺疊收合的「進階系統參數」（Heartbeat、UMS 連線設定、事件與日誌參數）區塊，維持高對比科技工控風格。

**Blocked by:** 02（結構化 Config 持久化與非破壞式寫入）

**Status:** ready-for-agent

- [ ] 重構 `templates/index.html` 之表單排版，建立四大分區卡片（全域推論、全域模型、模式與來源、進階參數）。
- [ ] 實作「進階系統參數 (ADVANCED_PARAMETERS)」摺疊區塊（Collapsible Accordion），預設收合並可點擊平滑展開。
- [ ] 整合進階欄位：UMS Base URL、UMS API Key（附密碼隱蔽切換）、Heartbeat 心跳開關/Port/間隔、事件消失容忍影格數與日誌檔名。
- [ ] 保持全域高對比深色工控主題風格（Neon Cyan/Green、清晰等寬字型排版與流暢微互動）。
- [ ] 驗證表單載入時能正確回填 `config.yaml` 中既有的進階參數值。
